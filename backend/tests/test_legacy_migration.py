import asyncio
import pytest
from sqlalchemy import text
from app.infrastructure.db.session import engine, init_db
from app.domain.ingestion.persistent_ingestion_queue import PersistentIngestionWorker
from app.infrastructure.events.event_bus import event_bus

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy.orm import Session
    from sqlalchemy import select

from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable, ArtifactJobTable


def test_fts5_backfill_and_legacy_migration():
    async def _test():
        init_db()
        worker = PersistentIngestionWorker(event_bus)

        # Insert a dummy media item and legacy whole-page chunk
        media_id = "doc_legacy_test_1"
        workspace_id = "ws_legacy_test"

        with Session(engine) as session:
            # Cleanup past test runs
            session.execute(text("DELETE FROM transcript_chunks WHERE media_id = :mid"), {"mid": media_id})
            try:
                session.execute(text("DELETE FROM transcript_chunks_fts WHERE chunk_id LIKE :prefix"), {"prefix": f"{media_id}%"})
            except Exception:
                pass
            session.execute(text("DELETE FROM artifact_jobs WHERE target_key = :mid"), {"mid": media_id})
            session.execute(text("DELETE FROM media_items WHERE id = :mid"), {"mid": media_id})
            session.commit()

            # Add media item
            item = MediaItemTable(
                id=media_id,
                workspace_id=workspace_id,
                title="Legacy Document Test.pdf",
                file_path="test_path.pdf",
                media_type="document",
                status="ready"
            )
            session.add(item)

            # Add legacy chunk (large word_count > 500, page 1)
            chunk = TranscriptChunkTable(
                id=f"{media_id}_page_1",
                media_id=media_id,
                workspace_id=workspace_id,
                text="Legacy document page text with multi-paragraph content. " * 50,
                start_time=1,
                end_time=1,
                chunk_index=0,
                word_count=600
            )
            session.add(chunk)
            session.commit()

        # Run boot recovery which triggers FTS5 backfill + legacy re-chunking job creation
        worker.boot_recovery()
        await asyncio.sleep(0.1)

        # Verify FTS5 backfill executed
        with Session(engine) as session:
            fts_count = session.execute(
                text("SELECT count(*) FROM transcript_chunks_fts WHERE chunk_id = :cid"),
                {"cid": f"{media_id}_page_1"}
            ).scalar()
            assert fts_count >= 1, "Expected legacy chunk to be backfilled into FTS5"

            # Verify rechunk_ingestion job created in ArtifactJobTable
            job = session.get(ArtifactJobTable, f"rechunk_{media_id}")
            assert job is not None, "Expected rechunk_ingestion job to be enqueued"

    asyncio.run(_test())
