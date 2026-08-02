import asyncio
import os
import pytest
from app.domain.ai.capabilities import TranscriptSegmentDTO
from app.domain.knowledge.chunker import SemanticChunker
from app.infrastructure.events.event_bus import EventBus, DomainEvent
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.whisper_adapter import FasterWhisperSTTAdapter
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.services.workers.transcript_worker import TranscriptWorker
from app.services.workers.embedding_worker import EmbeddingWorker
from fastapi.testclient import TestClient
from app.main import app

def test_semantic_chunker():
    chunker = SemanticChunker(target_word_count=10)
    segments = [
        TranscriptSegmentDTO(start_time=0.0, end_time=5.0, text="Artificial intelligence is transforming education."),
        TranscriptSegmentDTO(start_time=5.0, end_time=10.0, text="Local first architectures preserve privacy and data control.")
    ]
    chunks = chunker.chunk_transcript(segments, media_id="m1", workspace_id="w1")
    assert len(chunks) >= 1
    assert chunks[0].start_time == 0.0
    assert chunks[0].end_time == 10.0

def test_worker_pipeline_end_to_end(tmp_path):
    async def _async_test():
        bus = EventBus()
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        ai_bus = AIServiceBus(registry, router)
        ai_bus.register_stt_adapter("faster_whisper", FasterWhisperSTTAdapter())
        ai_bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

        t_worker = TranscriptWorker(bus, ai_bus)
        e_worker = EmbeddingWorker(bus, ai_bus)

        events_captured = []
        async def capture_indexed(event: DomainEvent):
            events_captured.append(event)

        bus.subscribe("ChunksIndexedEvent", capture_indexed)

        # Create dummy video file
        dummy_file = tmp_path / "sample.mp4"
        dummy_file.write_text("dummy video content")

        await bus.publish(DomainEvent(
            event_type="MediaUploadedEvent",
            aggregate_id="test_media_1",
            payload={"media_id": "test_media_1", "workspace_id": "ws1", "file_path": str(dummy_file)}
        ))

        assert len(events_captured) == 1
        assert events_captured[0].event_type == "ChunksIndexedEvent"
        assert events_captured[0].payload["media_id"] == "test_media_1"

    asyncio.run(_async_test())

def test_media_upload_endpoint():
    client = TestClient(app)
    files = {"file": ("test.mp4", b"video binary content", "video/mp4")}
    data = {"workspace_id": "ws_test", "title": "Test Video Title"}
    
    response = client.post("/api/v1/media/upload", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert "media_id" in res_data
    assert res_data["title"] == "Test Video Title"
