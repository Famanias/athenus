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
            artifact_type = next_job.get("artifact_type", "ingestion")

            if artifact_type == "rechunk_ingestion":
                await self._execute_rechunk_migration(job_id, media_id, workspace_id)
                asyncio.create_task(self.process_next_job())
                return

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
                asyncio.create_task(self.process_next_job())
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
                message="Ingestion complete. Knowledge graph and vector index ready.",
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
                        ArtifactJobTable.artifact_type.in_(["ingestion", "rechunk_ingestion"]),
                        ArtifactJobTable.status == "queued",
                    )
                    .order_by(ArtifactJobTable.created_at.asc())
                )
                records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                if records:
                    top = records[0]
                    return {
                        "id": top.id,
                        "media_id": top.target_key,
                        "workspace_id": top.workspace_id,
                        "artifact_type": top.artifact_type,
                    }
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

    def _backfill_fts5(self) -> None:
        """Fast FTS5 Backfill on boot to index any chunks missing from FTS5 table."""
        if not engine or not Session:
            return
        try:
            from sqlalchemy import text
            with Session(engine) as session:
                session.execute(text("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS transcript_chunks_fts USING fts5(
                        chunk_id UNINDEXED,
                        workspace_id UNINDEXED,
                        text
                    );
                """))
                session.execute(text("""
                    INSERT INTO transcript_chunks_fts(chunk_id, workspace_id, text)
                    SELECT tc.id, tc.workspace_id, tc.text
                    FROM transcript_chunks tc
                    LEFT JOIN transcript_chunks_fts fts ON tc.id = fts.chunk_id
                    WHERE fts.chunk_id IS NULL;
                """))
                session.commit()
        except Exception as e:
            print("FTS5 BACKFILL ERROR:", e)

    def _enqueue_legacy_rechunk_jobs(self) -> None:
        """Scans media_items for legacy documents with whole-page chunks and enqueues rechunk_ingestion jobs."""
        if not engine or not Session:
            return
        try:
            from sqlalchemy import text
            from app.infrastructure.db.models import MediaItemTable, ArtifactJobTable
            with Session(engine) as session:
                legacy_media_ids = session.execute(text("""
                    SELECT DISTINCT tc.media_id
                    FROM transcript_chunks tc
                    JOIN media_items m ON tc.media_id = m.id
                    WHERE (m.media_type = 'document' OR m.file_path LIKE '%.pdf' OR m.file_path LIKE '%.docx' OR tc.media_id LIKE 'doc_%')
                      AND (tc.word_count > 500 OR tc.id NOT LIKE '%_sub_%')
                """)).scalars().all()

                for media_id in legacy_media_ids:
                    job_id = f"rechunk_{media_id}"
                    existing_job = session.get(ArtifactJobTable, job_id)
                    if not existing_job or existing_job.status in ["queued", "failed"]:
                        media = session.get(MediaItemTable, media_id)
                        workspace_id = media.workspace_id if media else "default"
                        if not existing_job:
                            job = ArtifactJobTable(
                                id=job_id,
                                workspace_id=workspace_id,
                                artifact_type="rechunk_ingestion",
                                target_key=media_id,
                                status="queued",
                                stage="queued",
                                progress=0,
                                message="Queued for legacy chunk migration...",
                                created_at=datetime.utcnow(),
                                updated_at=datetime.utcnow(),
                            )
                            session.add(job)
                        else:
                            existing_job.status = "queued"
                            existing_job.stage = "queued"
                            existing_job.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

    async def _execute_rechunk_migration(self, job_id: str, media_id: str, workspace_id: str) -> None:
        """Idempotently re-chunk legacy document into ~500-word sub-chunks and re-index in SQLite & FTS5."""
        self._update_job_status(
            job_id=job_id,
            status="processing",
            stage="rechunk_ingestion",
            progress=20,
            message="Re-chunking legacy document into ~500-word sub-chunks...",
        )
        try:
            from sqlalchemy import text
            from app.domain.knowledge.chunker import SemanticChunker
            chunker = SemanticChunker()
            from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

            with Session(engine) as session:
                media_item = session.get(MediaItemTable, media_id)
                if media_item and (getattr(media_item, "media_type", "") in ["video", "audio"] or (media_item.file_path and media_item.file_path.endswith((".mp4", ".mkv", ".mov", ".mp3", ".wav")))):
                    self._update_job_status(
                        job_id=job_id,
                        status="completed",
                        stage="ready",
                        progress=100,
                        message="Legacy migration skipped (video/audio media).",
                    )
                    return

                chunks = session.execute(
                    select(TranscriptChunkTable).where(TranscriptChunkTable.media_id == media_id)
                ).scalars().all()

                is_already_subchunked = any(c.word_count <= 500 or "_sub_" in c.id for c in chunks)
                if is_already_subchunked and len(chunks) > 1:
                    self._update_job_status(
                        job_id=job_id,
                        status="completed",
                        stage="ready",
                        progress=100,
                        message="Legacy migration complete (document already sub-chunked).",
                    )
                    return

                pages = []
                for idx, c in enumerate(chunks, 1):
                    pages.append({"page": idx, "text": c.text, "section": f"Page {idx}"})

                if not pages:
                    media_item = session.get(MediaItemTable, media_id)
                    if media_item and media_item.file_path:
                        from app.infrastructure.adapters.anydoc_adapter import AnyDocDocumentParsingAdapter
                        from app.domain.ai.capabilities import DocumentParsingRequest
                        adapter = AnyDocDocumentParsingAdapter()
                        res = await adapter.parse_document(DocumentParsingRequest(file_path=media_item.file_path))
                        pages = res.pages

                if pages:
                    session.execute(text("DELETE FROM transcript_chunks WHERE media_id = :mid"), {"mid": media_id})
                    try:
                        session.execute(text("DELETE FROM transcript_chunks_fts WHERE chunk_id LIKE :prefix"), {"prefix": f"{media_id}%"})
                    except Exception:
                        pass
                    session.commit()

                    units = chunker.chunk_document_pages(pages, document_id=media_id, workspace_id=workspace_id)
                    
                    for u in units:
                        chunk_row = TranscriptChunkTable(
                            id=u.id,
                            media_id=u.source_id,
                            workspace_id=u.workspace_id,
                            text=u.text,
                            start_time=u.location.get("page", 1),
                            end_time=u.location.get("page", 1),
                            chunk_index=u.chunk_index,
                            word_count=len(u.text.split()),
                            created_at=datetime.utcnow()
                        )
                        session.add(chunk_row)
                    session.commit()

                    self._backfill_fts5()

            self._update_job_status(
                job_id=job_id,
                status="completed",
                stage="ready",
                progress=100,
                message="Legacy migration complete. Sub-chunks indexed into FTS5.",
            )
        except Exception as err:
            self._update_job_status(
                job_id=job_id,
                status="failed",
                stage="failed",
                progress=0,
                message="Legacy re-chunking migration failed.",
                error_message=str(err),
            )

    def boot_recovery(self) -> None:
        """Recover stale or stranded queued jobs and execute FTS5 backfill + legacy migration on server boot."""
        if not engine or not Session or not select:
            return

        # 1. Fast FTS5 Backfill
        self._backfill_fts5()

        # 2. Legacy Document Re-Chunk Queue Routing
        self._enqueue_legacy_rechunk_jobs()

        # 3. Recover queued/reserved/processing jobs & clean up stale non-document rechunk jobs
        try:
            from app.infrastructure.db.models import ArtifactJobTable, MediaItemTable
            with Session(engine) as session:
                stale_rechunks = session.execute(
                    select(ArtifactJobTable).where(ArtifactJobTable.artifact_type == "rechunk_ingestion")
                ).scalars().all()
                for job in stale_rechunks:
                    media = session.get(MediaItemTable, job.target_key)
                    if media and (getattr(media, "media_type", "") in ["video", "audio"] or (media.file_path and media.file_path.endswith((".mp4", ".mkv", ".mov", ".mp3", ".wav")))):
                        job.status = "completed"
                        job.stage = "ready"
                        job.progress = 100

                stmt = select(ArtifactJobTable).where(
                    ArtifactJobTable.artifact_type.in_(["ingestion", "rechunk_ingestion"]),
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
