from typing import Any, Dict, List, Optional
from app.application.repositories.media_repository import MediaRepository
from app.domain.media.entities import MediaItem, MediaType, ProcessingStatus
from app.infrastructure.db.models import MediaItemTable, TranscriptSegmentTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class SqliteMediaRepository(MediaRepository):
    """SQLite-backed concrete implementation of MediaRepository."""

    def upsert(self, item: MediaItem) -> None:
        if not engine or not Session:
            return
        m_type_str = item.media_type.value if isinstance(item.media_type, MediaType) else str(item.media_type)
        m_status_str = item.status.value if isinstance(item.status, ProcessingStatus) else str(item.status)

        with Session(engine) as session:
            db_item = session.get(MediaItemTable, item.id)
            if not db_item:
                db_item = MediaItemTable(
                    id=item.id,
                    workspace_id=item.workspace_id,
                    title=item.title,
                    file_path=item.file_path,
                    media_type=m_type_str,
                    file_size_bytes=item.file_size_bytes,
                    duration_seconds=item.duration_seconds,
                    status=m_status_str,
                    error_message=item.error_message,
                )
                session.add(db_item)
            else:
                db_item.workspace_id = item.workspace_id
                db_item.title = item.title
                db_item.file_path = item.file_path
                db_item.media_type = m_type_str
                db_item.file_size_bytes = item.file_size_bytes
                db_item.duration_seconds = item.duration_seconds
                db_item.status = m_status_str
                db_item.error_message = item.error_message
            session.commit()

    def get(self, media_id: str) -> Optional[MediaItem]:
        if not engine or not Session:
            return None
        with Session(engine) as session:
            db_item = session.get(MediaItemTable, media_id)
            if not db_item:
                return None

            try:
                status_enum = ProcessingStatus(db_item.status)
            except ValueError:
                status_enum = ProcessingStatus.PENDING

            try:
                media_type_enum = MediaType(db_item.media_type)
            except ValueError:
                media_type_enum = MediaType.VIDEO

            return MediaItem(
                id=db_item.id,
                workspace_id=db_item.workspace_id,
                title=db_item.title,
                file_path=db_item.file_path,
                media_type=media_type_enum,
                file_size_bytes=db_item.file_size_bytes,
                duration_seconds=db_item.duration_seconds,
                status=status_enum,
                error_message=db_item.error_message,
            )

    def update_status(
        self,
        media_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None
    ) -> None:
        if not engine or not Session:
            return
        m_status_str = status.value if isinstance(status, ProcessingStatus) else str(status)
        with Session(engine) as session:
            db_item = session.get(MediaItemTable, media_id)
            if db_item:
                db_item.status = m_status_str
                if error_message is not None:
                    db_item.error_message = error_message
                session.commit()

    def save_transcript(self, media_id: str, segments: List[Dict[str, Any]]) -> None:
        if not engine or not Session or not select:
            return
        with Session(engine) as session:
            existing_statement = select(TranscriptSegmentTable).where(TranscriptSegmentTable.media_id == media_id)
            existing_records = session.scalars(existing_statement).all() if hasattr(session, "scalars") else session.exec(existing_statement).all()
            for record in existing_records:
                session.delete(record)
            
            for seg in segments:
                segment_record = TranscriptSegmentTable(
                    media_id=media_id,
                    start_time=float(seg.get("start_time", 0.0)),
                    end_time=float(seg.get("end_time", 0.0)),
                    text=str(seg.get("text", "")),
                )
                session.add(segment_record)
            session.commit()

    def get_transcript(self, media_id: str) -> List[Dict[str, Any]]:
        if not engine or not Session or not select:
            return []
        with Session(engine) as session:
            statement = select(TranscriptSegmentTable).where(TranscriptSegmentTable.media_id == media_id).order_by(TranscriptSegmentTable.start_time)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            return [
                {"start_time": r.start_time, "end_time": r.end_time, "text": r.text}
                for r in records
            ]

    def list_by_workspace(self, workspace_id: str) -> List[MediaItem]:
        if not engine or not Session or not select:
            return []
        with Session(engine) as session:
            statement = select(MediaItemTable).where(MediaItemTable.workspace_id == workspace_id)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            result = []
            for db_item in records:
                try:
                    status_enum = ProcessingStatus(db_item.status)
                except ValueError:
                    status_enum = ProcessingStatus.PENDING

                try:
                    media_type_enum = MediaType(db_item.media_type)
                except ValueError:
                    media_type_enum = MediaType.VIDEO

                result.append(
                    MediaItem(
                        id=db_item.id,
                        workspace_id=db_item.workspace_id,
                        title=db_item.title,
                        file_path=db_item.file_path,
                        media_type=media_type_enum,
                        file_size_bytes=db_item.file_size_bytes,
                        duration_seconds=db_item.duration_seconds,
                        status=status_enum,
                        error_message=db_item.error_message,
                    )
                )
            return result
