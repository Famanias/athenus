import asyncio
import pytest
import uuid
from sqlalchemy import create_engine, text
try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

from app.domain.ingestion.persistent_ingestion_queue import PersistentIngestionWorker
from app.infrastructure.events.event_bus import EventBus, DomainEvent
from app.domain.telemetry.telemetry_service import TelemetryService
from app.services.workers.transcript_worker import TranscriptWorker
from app.domain.ai.capabilities import ISpeechToTextCapability, SpeechToTextRequest, SpeechToTextResponse, TranscriptSegmentDTO
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus


class MockAudioExtractor:
    async def extract_audio(self, media_path: str, output_wav_path: str) -> None:
        pass


class MockSTTAdapter(ISpeechToTextCapability):
    async def transcribe(self, request: SpeechToTextRequest) -> SpeechToTextResponse:
        return SpeechToTextResponse(
            text="Mock video transcript content for test.",
            segments=[
                TranscriptSegmentDTO(start_time=0.0, end_time=5.0, text="Mock video transcript content for test.")
            ],
            language_detected="en",
        )


def test_video_media_excluded_from_legacy_rechunk():
    """Verify that video media items with transcript chunks are NOT queued for legacy re-chunking."""
    bus = EventBus()
    worker = PersistentIngestionWorker(bus)

    from app.infrastructure.db.session import engine
    if not engine:
        return

    from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable, ArtifactJobTable

    media_id = f"vid_test_{uuid.uuid4().hex[:8]}"
    with Session(engine) as session:
        session.execute(text("DELETE FROM artifact_jobs;"))
        session.commit()

        # Create a test video media item
        media_vid = MediaItemTable(
            id=media_id,
            workspace_id="ws_test",
            title="Sample Lecture Video",
            file_path="C:/media/sample.mp4",
            media_type="video",
            status="completed"
        )
        session.add(media_vid)

        # Create a video transcript chunk (without _sub_ in ID)
        chunk_vid = TranscriptChunkTable(
            id=f"{media_id}_chunk_0",
            media_id=media_id,
            workspace_id="ws_test",
            text="Hello class, today we discuss quantum entanglement.",
            start_time=0.0,
            end_time=15.0,
            chunk_index=0,
            word_count=550
        )
        session.add(chunk_vid)
        session.commit()

    # Execute legacy rechunk scanning
    worker._enqueue_legacy_rechunk_jobs()

    with Session(engine) as session:
        rechunk_job = session.get(ArtifactJobTable, f"rechunk_{media_id}")
        # Video media item MUST NOT be queued for document rechunking
        assert rechunk_job is None or rechunk_job.status != "queued"


def test_video_ingestion_queue_progress_beyond_5_percent(tmp_path):
    """Verify video ingestion job is processed sequentially by worker and progresses beyond 5%."""
    async def _test():
        bus = EventBus()
        telemetry = TelemetryService(bus)
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        ai_bus = AIServiceBus(registry, router)
        ai_bus.register_stt_adapter("faster_whisper", MockSTTAdapter())

        transcript_worker = TranscriptWorker(bus, ai_bus, audio_extractor=MockAudioExtractor())
        worker = PersistentIngestionWorker(bus)

        dummy_file = tmp_path / "lecture.mp4"
        dummy_file.write_text("dummy video binary")

        from app.infrastructure.db.session import engine
        from app.infrastructure.db.models import MediaItemTable, ArtifactJobTable

        media_id = f"vid_prog_{uuid.uuid4().hex[:8]}"
        with Session(engine) as session:
            session.execute(text("DELETE FROM artifact_jobs;"))
            media_vid = MediaItemTable(
                id=media_id,
                workspace_id="ws_test",
                title="Physics Lecture Video",
                file_path=str(dummy_file),
                media_type="video",
                status="uploaded"
            )
            session.add(media_vid)
            session.commit()

        # Enqueue video media item
        res = worker.enqueue_media(
            media_id=media_id,
            workspace_id="ws_test",
            file_path=str(dummy_file)
        )
        assert res["job_id"] == f"ingestion_{media_id}"

        # Poll queue worker until job moves out of initial 5% state
        job = None
        for _ in range(20):
            await asyncio.sleep(0.05)
            with Session(engine) as session:
                job = session.get(ArtifactJobTable, f"ingestion_{media_id}")
                if job and job.progress >= 60:
                    break

        assert job is not None
        # Job MUST transition out of initial queued (5%) state into processing (60% transcription)
        assert job.status == "processing"
        assert job.progress >= 60
        assert job.stage == "transcription"

        # Simulate ConceptGraphUpdatedEvent to mark completion
        await bus.publish(DomainEvent(
            event_type="ConceptGraphUpdatedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "workspace_id": "ws_test"}
        ))
        await asyncio.sleep(0.1)

        with Session(engine) as session:
            job_completed = session.get(ArtifactJobTable, f"ingestion_{media_id}")
            assert job_completed.status == "completed"
            assert job_completed.progress == 100

    asyncio.run(_test())
