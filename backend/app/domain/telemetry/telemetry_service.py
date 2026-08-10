from datetime import datetime
from typing import Any, Dict, Optional

from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import DomainEvent, EventBus

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

INGESTION_STAGES: Dict[str, dict] = {
    "queued": {"progress": 5, "message": "Enqueued in persistent ingestion queue..."},
    "audio_extraction": {"progress": 25, "message": "Extracting 16kHz mono WAV audio track..."},
    "transcription": {"progress": 60, "message": "Transcribing speech using Faster-Whisper ASR..."},
    "chunking": {"progress": 75, "message": "Chunking transcript text..."},
    "vector_indexing": {"progress": 85, "message": "Storing vector embeddings in Qdrant..."},
    "collect_context": {"progress": 90, "message": "Retrieving context for graph extraction..."},
    "llm_generation": {"progress": 95, "message": "Extracting domain concepts with LLM..."},
    "ready": {"progress": 100, "message": "Ingestion complete."},
    "completed": {"progress": 100, "message": "Ingestion complete."},
    "failed": {"progress": 0, "message": "Ingestion failed."},
}


class TelemetryService:
    """Centralized Single System of Record Telemetry Service.

    Subscribes to pipeline domain events and updates SQLite ``ArtifactJobTable``
    directly. Eliminates state drift between RAM caches and SQLite persistence.
    """

    def __init__(self, event_bus: Optional[EventBus] = None) -> None:
        self.event_bus = event_bus
        if self.event_bus:
            self._register_subscribers()

    def _register_subscribers(self) -> None:
        if not self.event_bus:
            return
        self.event_bus.subscribe("ProcessingStartedEvent", self.handle_processing_started)
        self.event_bus.subscribe("StageProgressEvent", self.handle_stage_progress)
        self.event_bus.subscribe("TranscriptCompletedEvent", self.handle_transcript_completed)
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)
        self.event_bus.subscribe("ProcessingFailedEvent", self.handle_processing_failed)
        self.event_bus.subscribe("ConceptGraphUpdatedEvent", self.handle_concept_graph_updated)

    def record_progress(
        self,
        media_id: str,
        workspace_id: str,
        stage: str,
        progress: Optional[int] = None,
        message: Optional[str] = None,
        status: str = "processing",
        error: Optional[str] = None,
    ) -> None:
        """Record stage progress in SQLite ``ArtifactJobTable``."""
        if not engine or not Session:
            return

        meta = INGESTION_STAGES.get(stage, {})
        calculated_progress = progress if progress is not None else meta.get("progress", 50)
        calculated_message = message or meta.get("message", f"Processing {stage}...")

        job_id = f"ingestion_{media_id}"
        try:
            from app.infrastructure.db.models import ArtifactJobTable
            with Session(engine) as session:
                job = session.get(ArtifactJobTable, job_id)
                if not job:
                    job = ArtifactJobTable(
                        id=job_id,
                        workspace_id=workspace_id,
                        artifact_type="ingestion",
                        target_key=media_id,
                        status=status,
                        stage=stage,
                        progress=calculated_progress,
                        message=calculated_message,
                        error_message=error,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(job)
                else:
                    # Telemetry State Guard: Never regress an active processing/completed job back to queued (5%)
                    if job.status in ["processing", "completed"] and status == "queued":
                        return
                    job.status = status
                    job.stage = stage
                    job.progress = max(job.progress or 0, calculated_progress) if status == "processing" else calculated_progress
                    job.message = calculated_message
                    if error:
                        job.error_message = error
                    job.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

    async def handle_processing_started(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        stage = event.payload.get("stage", "audio_extraction")
        message = event.payload.get("message")
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage=stage,
            status="processing",
            message=message,
        )

    async def handle_stage_progress(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        stage = event.payload.get("stage", "transcription")
        progress = event.payload.get("progress")
        message = event.payload.get("message")
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage=stage,
            progress=progress,
            message=message,
            status="processing",
        )

    async def handle_transcript_completed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage="transcription",
            progress=60,
            message="Speech transcription completed.",
            status="processing",
        )

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        chunk_count = event.payload.get("chunk_count", 0)
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage="vector_indexing",
            progress=85,
            message=f"Indexed {chunk_count} transcript chunks into Embedded Qdrant.",
            status="processing",
        )

    async def handle_concept_graph_updated(self, event: DomainEvent) -> None:
        media_id = event.payload.get("media_id") or event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage="ready",
            progress=100,
            message="Video ingestion & Knowledge Graph extraction complete.",
            status="completed",
        )

    async def handle_processing_failed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        failed_stage = event.payload.get("stage", "failed")
        raw_err = event.payload.get("error", "Ingestion failed.")
        self.record_progress(
            media_id=media_id,
            workspace_id=workspace_id,
            stage=failed_stage,
            progress=0,
            status="failed",
            message=f"Pipeline processing failed at {failed_stage}.",
            error=str(raw_err),
        )
