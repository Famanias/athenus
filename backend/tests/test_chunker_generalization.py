import asyncio
import pytest
from app.domain.ai.capabilities import IEmbeddingCapability
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.chunker import SemanticChunker
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.events.event_bus import DomainEvent, EventBus
from app.services.workers.embedding_worker import EmbeddingWorker


class MockEmbeddingCapability(IEmbeddingCapability):
    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * 384 for _ in texts]

    async def embed_query(self, query: str) -> list[float]:
        return [0.1] * 384


def test_chunk_document_pages():
    chunker = SemanticChunker()
    pages = [
        {"page_number": 1, "text": "Page 1 intro text", "page_type": "text", "section_title": "Intro"},
        {"page_number": 2, "text": "Page 2 detailed analysis", "page_type": "text", "section_title": "Analysis"},
    ]

    units = chunker.chunk_document_pages(pages, document_id="doc_100", workspace_id="ws_main")

    assert len(units) == 2
    assert units[0].source_id == "doc_100"
    assert units[0].location["type"] == "document"
    assert units[0].location["page"] == 1
    assert units[0].location["section"] == "Intro"
    assert units[1].location["page"] == 2
    assert units[1].location["section"] == "Analysis"


def test_embedding_worker_handle_document_parsed():
    async def _run():
        from app.domain.ai.model_registry import ModelRegistry
        from app.domain.ai.provider_router import ProviderRouter
        bus = EventBus()
        reg = ModelRegistry()
        router = ProviderRouter(reg)
        ai_bus = AIServiceBus(reg, router)
        ai_bus.register_embedding_adapter("sentence_transformers", MockEmbeddingCapability())
        vector_store = EmbeddedQdrantVectorStoreAdapter(path=":memory:")

        worker = EmbeddingWorker(event_bus=bus, ai_service_bus=ai_bus, vector_store=vector_store)

        indexed_events = []

        async def _on_indexed(event: DomainEvent):
            indexed_events.append(event)

        bus.subscribe("ChunksIndexedEvent", _on_indexed)

        parse_event = DomainEvent(
            event_type="DocumentParsedEvent",
            aggregate_id="doc_200",
            payload={
                "document_id": "doc_200",
                "workspace_id": "ws_test",
                "file_path": "test.pdf",
                "file_format": "pdf",
                "pages": [
                    {"page_number": 1, "text": "Scanned Page OCR Text", "page_type": "scanned", "section_title": "Page 1"}
                ],
                "total_pages": 1,
            },
        )

        await bus.publish(parse_event)

        assert len(indexed_events) == 1
        assert indexed_events[0].event_type == "ChunksIndexedEvent"
        assert indexed_events[0].payload["chunk_count"] == 1

    asyncio.run(_run())
