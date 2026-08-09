import asyncio
from datetime import datetime
import json
from typing import Any, Dict, List, Optional

from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import EventBus, DomainEvent

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class PersistentIngestionWorker:
    """Sequential Global Hardware Ingestion Queue Worker.

    Uses SQLite ``ArtifactJobTable`` as the canonical source of truth for crash recovery.
    Ensures heavy ASR, chunk embedding, and Knowledge Graph extraction jobs execute
    sequentially one video at a time, preventing hardware resource lockups.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self._lock = asyncio.Lock()
        self._is_processing = False

        # Subscribe to completion and failure events to unlock the queue
        self.event_bus.subscribe("ConceptGraphUpdatedEvent", self._handle_job_completed)
        self.event_bus.subscribe("ProcessingFailedEvent", self._handle_job_failed)

    def enqueue_media(self, media_id: str, workspace_id: str, file_path: str) -> dict:
        """Create or update a persistent ingestion job row in SQLite."""
        if not engine or not Session:
            return {"job_id": f"ingestion_{media_id}", "status": "queued"}

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
                        status="queued",
                        stage="queued",
                        progress=0,
                        message="Queued behind active video ingestion jobs...",
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    )
                    session.add(job)
                else:
                    job.status = "queued"
                    job.stage = "queued"
                    job.progress = 0
                    job.message = "Re-queued for processing..."
                    job.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

        # Trigger processing loop asynchronously
        asyncio.create_task(self.process_next_job())
        return {"job_id": job_id, "status": "queued"}

    async def process_next_job(self) -> None:
        """Poll SQLite for the next queued job and execute sequentially."""
        if self._lock.locked():
            return

        async with self._lock:
            next_job = self._fetch_next_queued_job()
            if not next_job:
                return

            job_id, media_id, workspace_id = next_job["id"], next_job["media_id"], next_job["workspace_id"]

            # Mark job as RESERVED / PROCESSING
            self._update_job_status(
                job_id=job_id,
                status="processing",
                stage="audio_extraction",
                progress=10,
                message="Processing audio extraction & ASR pipeline...",
            )

            # Fetch media item from DB
            media_item = self._get_media_item(media_id)
            if not media_item or not media_item.file_path:
                self._update_job_status(
                    job_id=job_id,
                    status="failed",
                    stage="failed",
                    progress=0,
                    message="Media file not found on disk.",
                    error_message="Missing file path.",
                )
                return

            file_path = media_item.file_path
            is_document = (
                getattr(media_item, "media_type", "") == "document"
                or media_id.startswith("doc_")
            )

            if is_document:
                self._update_job_status(
                    job_id=job_id,
                    status="processing",
                    stage="document_parsing",
                    progress=10,
                    message="Parsing document structure (AnyDoc)...",
                )
                await self.event_bus.publish(
                    DomainEvent(
                        event_type="DocumentUploadedEvent",
                        aggregate_id=media_id,
                        payload={
                            "media_id": media_id,
                            "workspace_id": workspace_id,
                            "file_path": file_path,
                        },
                    )
                )
            else:
                self._update_job_status(
                    job_id=job_id,
                    status="processing",
                    stage="audio_extraction",
                    progress=10,
                    message="Processing audio extraction & ASR pipeline...",
                )
                await self.event_bus.publish(
                    DomainEvent(
                        event_type="MediaUploadedEvent",
                        aggregate_id=media_id,
                        payload={
                            "media_id": media_id,
                            "workspace_id": workspace_id,
                            "file_path": file_path,
                        },
                    )
                )

    async def _handle_job_completed(self, event: DomainEvent) -> None:
        media_id = event.payload.get("media_id") or event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")
        if media_id:
            job_id = f"ingestion_{media_id}"
            self._update_job_status(
                job_id=job_id,
                status="completed",
                stage="ready",
                progress=100,
                message="Video ingestion & Knowledge Graph extraction complete.",
            )
        # Process next video in queue
        asyncio.create_task(self.process_next_job())

    async def _handle_job_failed(self, event: DomainEvent) -> None:
        media_id = event.payload.get("media_id") or event.aggregate_id
        error = event.payload.get("error", "Ingestion processing failed.")
        if media_id:
            job_id = f"ingestion_{media_id}"
            self._update_job_status(
                job_id=job_id,
                status="failed",
                stage="failed",
                progress=0,
                message="Ingestion processing failed.",
                error_message=error,
            )
        # Process next video in queue
        asyncio.create_task(self.process_next_job())

    def _fetch_next_queued_job(self) -> Optional[dict]:
        if not engine or not Session or not select:
            return None
        try:
            from app.infrastructure.db.models import ArtifactJobTable
            with Session(engine) as session:
                stmt = (
                    select(ArtifactJobTable)
                    .where(
                        ArtifactJobTable.artifact_type == "ingestion",
                        ArtifactJobTable.status == "queued",
                    )
                    .order_by(ArtifactJobTable.created_at.asc())
                )
                records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                if records:
                    top = records[0]
                    return {"id": top.id, "media_id": top.target_key, "workspace_id": top.workspace_id}
        except Exception:
            pass
        return None

    def _update_job_status(
        self,
        job_id: str,
        status: str,
        stage: str,
        progress: int,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if not engine or not Session:
            return
        try:
            from app.infrastructure.db.models import ArtifactJobTable
            with Session(engine) as session:
                job = session.get(ArtifactJobTable, job_id)
                if job:
                    job.status = status
                    job.stage = stage
                    job.progress = progress
                    if message:
                        job.message = message
                    if error_message:
                        job.error_message = error_message
                    job.updated_at = datetime.utcnow()
                    session.commit()
        except Exception:
            pass

    def _get_media_item(self, media_id: str) -> Optional[Any]:
        if not engine or not Session:
            return None
        try:
            from app.infrastructure.db.models import MediaItemTable
            with Session(engine) as session:
                return session.get(MediaItemTable, media_id)
        except Exception:
            pass
        return None

    def _get_media_file_path(self, media_id: str) -> Optional[str]:
        if not engine or not Session:
            return None
        try:
            from app.infrastructure.db.models import MediaItemTable
            with Session(engine) as session:
                item = session.get(MediaItemTable, media_id)
                if item:
                    return item.file_path
        except Exception:
            pass
        return None

    def boot_recovery(self) -> None:
        """Recover stale or stranded queued jobs on server boot."""
        if not engine or not Session or not select:
            return
        try:
            from app.infrastructure.db.models import ArtifactJobTable
            with Session(engine) as session:
                stmt = select(ArtifactJobTable).where(
                    ArtifactJobTable.artifact_type == "ingestion",
                    ArtifactJobTable.status.in_(["queued", "reserved", "processing"]),
                )
                records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                for job in records:
                    job.status = "queued"
                    job.stage = "queued"
                    job.message = "Re-queued on system recovery..."
                    job.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass
        asyncio.create_task(self.process_next_job())
