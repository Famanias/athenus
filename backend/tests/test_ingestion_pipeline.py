import asyncio
import os
import uuid
import pytest
from app.domain.ai.capabilities import (
    ISpeechToTextCapability,
    SpeechToTextRequest,
    SpeechToTextResponse,
    TranscriptSegmentDTO,
)
from app.domain.knowledge.chunker import SemanticChunker
from app.infrastructure.events.event_bus import EventBus, DomainEvent
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.services.workers.transcript_worker import TranscriptWorker
from app.services.workers.embedding_worker import EmbeddingWorker
from fastapi.testclient import TestClient
from app.main import app
from app.application.events.progress_store import ProgressStore
from app.application.repositories.sqlite_media_repository import SqliteMediaRepository
from app.bootstrap.event_subscribers import register_media_subscribers
from app.domain.media.entities import MediaItem, MediaType, ProcessingStatus
from app.infrastructure.db.models import MediaItemTable, TranscriptSegmentTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

class MockSTTAdapter(ISpeechToTextCapability):
    async def transcribe(self, request: SpeechToTextRequest) -> SpeechToTextResponse:
        return SpeechToTextResponse(
            text="Mock transcript content for development testing.",
            segments=[
                TranscriptSegmentDTO(start_time=0.0, end_time=5.0, text="Mock transcript content"),
                TranscriptSegmentDTO(start_time=5.0, end_time=10.0, text="for development testing."),
            ],
            language_detected="en",
        )


class MockAudioExtractor:
    async def extract_audio(self, input_path: str, output_path: str) -> None:
        return None

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
        ai_bus.register_stt_adapter("faster_whisper", MockSTTAdapter())
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


def test_video_transcript_is_persisted_and_returned_by_api(tmp_path):
    media_id = f"media_transcript_regression_{uuid.uuid4().hex}"
    media_path = tmp_path / f"{media_id}.mp4"
    media_path.write_bytes(b"test video")
    repository = SqliteMediaRepository()
    repository.upsert(
        MediaItem(
            id=media_id,
            workspace_id="default",
            title="Transcript regression fixture",
            file_path=str(media_path),
            media_type=MediaType.VIDEO,
            status=ProcessingStatus.PENDING,
        )
    )

    async def run_pipeline() -> None:
        bus = EventBus()
        register_media_subscribers(bus, repository, ProgressStore())
        registry = ModelRegistry()
        ai_bus = AIServiceBus(registry, ProviderRouter(registry))
        ai_bus.register_stt_adapter("faster_whisper", MockSTTAdapter())
        TranscriptWorker(bus, ai_bus, audio_extractor=MockAudioExtractor())
        await bus.publish(
            DomainEvent(
                event_type="MediaUploadedEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": "default",
                    "file_path": str(media_path),
                },
            )
        )

    try:
        asyncio.run(run_pipeline())

        response = TestClient(app).get(f"/api/v1/media/{media_id}/transcript")

        assert response.status_code == 200
        assert response.json() == {
            "media_id": media_id,
            "full_text": "Mock transcript content for development testing.",
            "segments": [
                {"start_time": 0.0, "end_time": 5.0, "text": "Mock transcript content"},
                {"start_time": 5.0, "end_time": 10.0, "text": "for development testing."},
            ],
        }
    finally:
        with Session(engine) as session:
            segments = session.scalars(
                select(TranscriptSegmentTable).where(
                    TranscriptSegmentTable.media_id == media_id
                )
            ).all()
            for segment in segments:
                session.delete(segment)
            media = session.get(MediaItemTable, media_id)
            if media is not None:
                session.delete(media)
            session.commit()

def test_media_upload_endpoint():
    client = TestClient(app)
    files = {"file": ("test.mp4", b"video binary content", "video/mp4")}
    data = {"workspace_id": "ws_test", "title": "Test Video Title"}
    
    response = client.post("/api/v1/media/upload", files=files, data=data)
    assert response.status_code == 200
    res_data = response.json()
    assert "media_id" in res_data
    assert res_data["title"] == "Test Video Title"
    media_id = res_data["media_id"]

    # Test status endpoint
    status_resp = client.get(f"/api/v1/media/{media_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["media_id"] == media_id

    # Test transcript endpoint
    tr_resp = client.get(f"/api/v1/media/{media_id}/transcript")
    assert tr_resp.status_code == 200
    tr_data = tr_resp.json()
    assert tr_data["media_id"] == media_id

def test_media_repository_and_progress_store():
    from app.application.repositories.media_repository import InMemoryMediaRepository
    from app.application.events.progress_store import ProgressStore
    from app.domain.media.entities import MediaItem, ProcessingStatus, MediaType

    repo = InMemoryMediaRepository()
    store = ProgressStore()

    item = MediaItem(id="m_test", workspace_id="ws1", title="Test", file_path="/tmp/test.mp4", status=ProcessingStatus.PENDING)
    repo.upsert(item)
    assert repo.get("m_test").title == "Test"

    repo.update_status("m_test", ProcessingStatus.COMPLETED)
    assert repo.get("m_test").status == ProcessingStatus.COMPLETED

    segments = [{"start_time": 0.0, "end_time": 5.0, "text": "Hello world"}]
    repo.save_transcript("m_test", segments)
    assert repo.get_transcript("m_test") == segments

    snap = store.record_stage_progress("m_test", "audio_extraction", 50, "Extracting audio...")
    assert snap["overall_progress"] == 50
    assert store.snapshot("m_test")["current_stage"] == "audio_extraction"

