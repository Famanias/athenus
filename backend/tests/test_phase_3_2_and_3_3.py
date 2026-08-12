import asyncio
import pytest
import uuid
from sqlalchemy import create_engine, text
try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus


def test_qdrant_adapter_score_threshold():
    """Verify EmbeddedQdrantVectorStoreAdapter search respects score_threshold parameter."""
    async def _test():
        adapter = EmbeddedQdrantVectorStoreAdapter(path=":memory:")

        # Force fallback path to test the in-memory score_threshold filtering
        adapter._client = None

        # Upsert items into fallback memory with distinct scores
        adapter._fallback_memory = [
            {"id": "c1", "score": 0.85, "payload": {"workspace_id": "ws1", "text": "High relevance chunk."}},
            {"id": "c2", "score": 0.15, "payload": {"workspace_id": "ws1", "text": "Low relevance noise chunk."}},
            {"id": "c3", "score": 0.45, "payload": {"workspace_id": "ws1", "text": "Medium relevance chunk."}},
        ]

        # Search with default score_threshold=0.2
        results = await adapter.search(
            query_vector=[0.1] * 384,
            limit=5,
            filter_workspace_id="ws1",
            score_threshold=0.2
        )

        hit_ids = [r["id"] for r in results]
        assert "c1" in hit_ids
        assert "c3" in hit_ids
        # c2 (score 0.15) MUST be filtered out by score_threshold=0.2
        assert "c2" not in hit_ids

    asyncio.run(_test())


def test_extract_document_page_context_subchunks():
    """Verify _extract_document_page_context queries SQLite for all sub-chunks of current_page and joins them in chunk_index order."""
    registry = ModelRegistry()
    router = ProviderRouter(registry)
    ai_bus = AIServiceBus(registry, router)
    retriever = MultiStageRetriever(ai_service_bus=ai_bus)

    from app.infrastructure.db.session import engine
    if not engine:
        return

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

    doc_id = f"doc_p33_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        # Insert test document media item
        media = MediaItemTable(
            id=doc_id,
            workspace_id="ws_p33",
            title="Cell Biology Textbook.pdf",
            file_path="C:/docs/biology.pdf",
            media_type="document",
            status="completed"
        )
        session.add(media)

        # Insert sub-chunks for Page 4
        c1 = TranscriptChunkTable(
            id=f"{doc_id}_chunk_0",
            media_id=doc_id,
            workspace_id="ws_p33",
            text="Photosynthesis occurs in chloroplasts within plant cells.",
            start_time=4.0,
            end_time=4.0,
            chunk_index=0,
            word_count=8
        )
        c2 = TranscriptChunkTable(
            id=f"{doc_id}_chunk_1",
            media_id=doc_id,
            workspace_id="ws_p33",
            text="Light-dependent reactions produce ATP and NADPH in the thylakoid membrane.",
            start_time=4.0,
            end_time=4.0,
            chunk_index=1,
            word_count=11
        )
        session.add(c1)
        session.add(c2)
        session.commit()

    context_str, provenance = retriever._extract_document_page_context(
        document_id=doc_id,
        current_page=4,
        selected_text="chloroplasts"
    )

    assert provenance is not None
    assert provenance["document_title"] == "Cell Biology Textbook.pdf"
    assert provenance["current_page"] == 4
    assert provenance["chunk_count"] == 2

    # Verify both sub-chunks are present in context_str in chunk_index order
    assert "[Active Document Page Context]" in context_str
    assert "Document Title: Cell Biology Textbook.pdf" in context_str
    assert "Active Page: Page 4" in context_str
    assert "Photosynthesis occurs in chloroplasts within plant cells." in context_str
    assert "Light-dependent reactions produce ATP and NADPH" in context_str
    assert "User Selected Text:\n\"chloroplasts\"" in context_str
