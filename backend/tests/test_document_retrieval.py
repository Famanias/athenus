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
    import uuid
    doc_id = f"doc_retrieval_{uuid.uuid4().hex[:8]}"

    async def _run():
        reg = ModelRegistry()
        router = ProviderRouter(reg)
        ai_bus = AIServiceBus(reg, router)
        ai_bus.register_embedding_adapter("sentence_transformers", MockEmbeddingCapability())

        vector_store = EmbeddedQdrantVectorStoreAdapter(path=":memory:")
        payloads = [
            {
                "chunk_id": f"{doc_id}_chunk_1",
                "media_id": doc_id,
                "document_id": doc_id,
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

        # Insert media item + transcript chunk into SQLite so _extract_document_page_context finds them
        from app.infrastructure.db.session import engine
        from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

        if engine:
            try:
                from sqlmodel import Session as DBSession
            except ImportError:
                from sqlalchemy.orm import Session as DBSession

            with DBSession(engine) as session:
                media = MediaItemTable(
                    id=doc_id,
                    workspace_id="ws_retrieval",
                    title="Optimization Textbook.pdf",
                    file_path="/docs/optimization.pdf",
                    media_type="document",
                    status="completed"
                )
                session.add(media)
                chunk = TranscriptChunkTable(
                    id=f"{doc_id}_chunk_0",
                    media_id=doc_id,
                    workspace_id="ws_retrieval",
                    text="Gradient descent optimization proof details on page 12.",
                    start_time=12.0,
                    end_time=12.0,
                    chunk_index=0,
                    word_count=9
                )
                session.add(chunk)
                session.commit()

        retriever = MultiStageRetriever(ai_service_bus=ai_bus, vector_store=vector_store)

        ctx = await retriever.execute_retrieval(
            query="What is the optimization proof?",
            workspace_id="ws_retrieval",
            document_id=doc_id,
            source_type="pdf",
            current_page=12,
        )

        assert ctx.document_id == doc_id
        assert ctx.source_type == "pdf"
        assert "[Active Document" in ctx.assembled_prompt
        assert "Gradient descent optimization proof details" in ctx.assembled_prompt

    asyncio.run(_run())
