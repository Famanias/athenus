import asyncio
import uuid
import pytest
from app.domain.ai.service_bus import AIServiceBus
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever


def test_workspace_isolation_query_filtering():
    async def _run_test():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

        vector_store = EmbeddedQdrantVectorStoreAdapter(path="./data/test_qdrant_isolation", collection_name="test_isolation_chunks")
        retriever = MultiStageRetriever(bus, vector_store=vector_store)

        embedding_cap = bus.get_embedding_capability()

        # 1. Prepare vectors for Workspace CS
        cs_texts = [
            "Gradient descent optimizes neural network parameters using loss function partial derivatives.",
            "Backpropagation computes the gradient of loss with respect to weight parameters."
        ]
        cs_vectors = await embedding_cap.embed_texts(cs_texts)
        cs_ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, "cs_c1")),
            str(uuid.uuid5(uuid.NAMESPACE_URL, "cs_c2"))
        ]
        cs_payloads = [
            {"chunk_id": "cs_c1", "workspace_id": "workspace_cs", "media_id": "med_cs", "text": cs_texts[0], "start_time": 0.0, "end_time": 10.0},
            {"chunk_id": "cs_c2", "workspace_id": "workspace_cs", "media_id": "med_cs", "text": cs_texts[1], "start_time": 10.0, "end_time": 20.0},
        ]
        await vector_store.upsert(ids=cs_ids, vectors=cs_vectors, payloads=cs_payloads)

        # 2. Prepare vectors for Workspace History
        history_texts = [
            "Julius Caesar crossed the Rubicon river in 49 BC leading to the Roman Civil War.",
            "The Roman Senate appointed Caesar dictator perpetual before the Ides of March."
        ]
        history_vectors = await embedding_cap.embed_texts(history_texts)
        history_ids = [
            str(uuid.uuid5(uuid.NAMESPACE_URL, "hist_c1")),
            str(uuid.uuid5(uuid.NAMESPACE_URL, "hist_c2"))
        ]
        history_payloads = [
            {"chunk_id": "hist_c1", "workspace_id": "workspace_history", "media_id": "med_hist", "text": history_texts[0], "start_time": 0.0, "end_time": 10.0},
            {"chunk_id": "hist_c2", "workspace_id": "workspace_history", "media_id": "med_hist", "text": history_texts[1], "start_time": 10.0, "end_time": 20.0},
        ]
        await vector_store.upsert(ids=history_ids, vectors=history_vectors, payloads=history_payloads)

        # 3. Direct Qdrant search with workspace_id filter for CS
        cs_query_vector = await embedding_cap.embed_query("Julius Caesar Roman Senate")
        cs_dense_hits = await vector_store.search(query_vector=cs_query_vector, limit=10, filter_workspace_id="workspace_cs")
        cs_texts_returned = [h["payload"]["text"] for h in cs_dense_hits if "payload" in h]

        # Assert zero Roman history text returned when searching workspace_cs
        for text in cs_texts_returned:
            assert "Julius Caesar" not in text
            assert "Roman Senate" not in text

        # 4. Direct Qdrant search for workspace_history with workspace_id filter
        hist_query_vector = await embedding_cap.embed_query("Gradient descent neural network")
        hist_dense_hits = await vector_store.search(query_vector=hist_query_vector, limit=10, filter_workspace_id="workspace_history")
        hist_texts_returned = [h["payload"]["text"] for h in hist_dense_hits if "payload" in h]

        # Assert zero CS text returned when searching workspace_history
        for text in hist_texts_returned:
            assert "Gradient descent" not in text
            assert "neural network" not in text

        # 5. Search workspace_cs for Gradient Descent -> Assert CS vectors ARE returned
        valid_cs_hits = await vector_store.search(query_vector=hist_query_vector, limit=10, filter_workspace_id="workspace_cs")
        assert len(valid_cs_hits) > 0
        assert any("Gradient descent" in h["payload"]["text"] for h in valid_cs_hits)

    asyncio.run(_run_test())
