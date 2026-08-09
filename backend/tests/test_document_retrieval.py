import asyncio
import pytest

from app.domain.ai.capabilities import IEmbeddingCapability
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever


class MockEmbeddingCapability(IEmbeddingCapability):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return [0.1] * 384


def test_qdrant_document_filtering():
    async def _run():
        adapter = EmbeddedQdrantVectorStoreAdapter(path=":memory:")

        # Upsert video chunk and document chunk into memory adapter
        payloads = [
            {
                "chunk_id": "video_chunk_1",
                "media_id": "vid_101",
                "workspace_id": "ws_test",
                "source_type": "video",
                "text": "Video spoken content about neural networks",
                "start_time": 10.0,
                "end_time": 20.0,
            },
            {
                "chunk_id": "doc_chunk_1",
                "media_id": "doc_202",
                "document_id": "doc_202",
                "workspace_id": "ws_test",
                "source_type": "pdf",
                "text": "PDF document content about backpropagation mathematics",
                "page_number": 5,
                "section_title": "Backprop Proof",
            },
        ]
        vectors = [[0.1] * 384, [0.1] * 384]
        ids = ["00000000-0000-0000-0000-000000000001", "00000000-0000-0000-0000-000000000002"]

        await adapter.upsert(ids=ids, vectors=vectors, payloads=payloads)

        # Search filtered strictly by document_id="doc_202"
        doc_hits = await adapter.search(
            query_vector=[0.1] * 384,
            limit=5,
            filter_workspace_id="ws_test",
            filter_document_id="doc_202",
            filter_source_type="pdf",
        )

        assert len(doc_hits) == 1
        assert doc_hits[0]["payload"]["chunk_id"] == "doc_chunk_1"
        assert doc_hits[0]["payload"]["source_type"] == "pdf"

    asyncio.run(_run())


def test_multi_stage_retriever_document_flow():
    async def _run():
        reg = ModelRegistry()
        router = ProviderRouter(reg)
        ai_bus = AIServiceBus(reg, router)
        ai_bus.register_embedding_adapter("sentence_transformers", MockEmbeddingCapability())

        vector_store = EmbeddedQdrantVectorStoreAdapter(path=":memory:")
        payloads = [
            {
                "chunk_id": "doc_chunk_1",
                "media_id": "doc_303",
                "document_id": "doc_303",
                "workspace_id": "ws_retrieval",
                "source_type": "pdf",
                "text": "Gradient descent optimization proof details on page 12.",
                "page_number": 12,
                "section_title": "Optimization Chapter",
            }
        ]
        await vector_store.upsert(
            ids=["00000000-0000-0000-0000-000000000003"],
            vectors=[[0.1] * 384],
            payloads=payloads,
        )

        retriever = MultiStageRetriever(ai_service_bus=ai_bus, vector_store=vector_store)

        ctx = await retriever.execute_retrieval(
            query="What is the optimization proof?",
            workspace_id="ws_retrieval",
            document_id="doc_303",
            source_type="pdf",
            current_page=12,
        )

        assert ctx.document_id == "doc_303"
        assert ctx.source_type == "pdf"
        assert "[Document Page 12 (Optimization Chapter)]" in ctx.assembled_prompt
        assert "Gradient descent optimization proof details" in ctx.assembled_prompt
        assert "[Active Document Context]" in ctx.assembled_prompt

    asyncio.run(_run())
