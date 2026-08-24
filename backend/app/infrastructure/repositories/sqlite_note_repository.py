import json
from datetime import datetime
from typing import List, Optional

from app.domain.learning.entities import Note, NoteFolder, NoteSection
from app.domain.learning.note_repository import TranscriptChunkRecord
from app.infrastructure.db.models import (
    MediaItemTable,
    NoteFolderTable,
    NoteSectionTable,
    NoteTable,
    TranscriptChunkTable,
)
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def _decode_list(value: object) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        decoded = json.loads(str(value))
        return [str(item) for item in decoded] if isinstance(decoded, list) else []
    except (TypeError, ValueError, json.JSONDecodeError):
        return [part.strip() for part in str(value).split(",") if part.strip()]


class SqliteNoteRepository:
    """SQLite adapter for the note persistence seam."""

    @staticmethod
    def _all(session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    @staticmethod
    def _first(session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).first()
        return session.exec(statement).first()

    def _sections(self, session, note_id: str, media_id: Optional[str]) -> List[NoteSection]:
        rows = self._all(
            session,
            select(NoteSectionTable)
            .where(NoteSectionTable.note_id == note_id)
            .order_by(NoteSectionTable.order_index),
        )
        return [
            NoteSection(
                id=row.id,
                note_id=row.note_id,
                workspace_id=row.workspace_id,
                heading=row.heading,
                body=row.body,
                key_takeaways=_decode_list(getattr(row, "key_takeaways_json", None)),
                media_id=media_id,
                start_time=row.start_time,
                end_time=row.end_time,
                source_chunk_ids=_decode_list(getattr(row, "source_chunk_ids", None)),
                order_index=row.order_index,
                created_at=row.created_at,
            )
            for row in rows
        ]

    def _to_note(self, session, row, include_sections: bool = True) -> Note:
        sections = self._sections(session, row.id, row.media_id) if include_sections else []
        return Note(
            id=row.id,
            workspace_id=row.workspace_id,
            title=row.title,
            folder_id=getattr(row, "folder_id", None),
            content=getattr(row, "content", None),
            summary=row.summary,
            media_id=row.media_id,
            version=row.version,
            status=row.status,
            action_items=_decode_list(getattr(row, "action_items_json", None)),
            sections=sections,
            generation_method=getattr(row, "generation_method", "llm") or "llm",
            fallback_reason=getattr(row, "fallback_reason", None),
            provider_id=getattr(row, "provider_id", None),
            model_id=getattr(row, "model_id", None),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    def save_folder(self, folder: NoteFolder) -> NoteFolder:
        with Session(engine) as session:
            row = session.get(NoteFolderTable, folder.id)
            if row is None:
                row = NoteFolderTable(
                    id=folder.id,
                    workspace_id=folder.workspace_id,
                    name=folder.name,
                    created_at=folder.created_at,
                    updated_at=folder.updated_at,
                )
            else:
                row.name = folder.name
                row.updated_at = folder.updated_at
            session.add(row)
            session.commit()
        return folder

    def get_folder(self, folder_id: str) -> Optional[NoteFolder]:
        with Session(engine) as session:
            row = session.get(NoteFolderTable, folder_id)
            if row is None:
                return None
            note_count = len(
                self._all(session, select(NoteTable).where(NoteTable.folder_id == folder_id))
            )
            return NoteFolder(
                id=row.id,
                workspace_id=row.workspace_id,
                name=row.name,
                note_count=note_count,
                created_at=row.created_at,
                updated_at=row.updated_at,
            )

    def list_folders(self, workspace_id: str) -> List[NoteFolder]:
        with Session(engine) as session:
            rows = self._all(
                session,
                select(NoteFolderTable)
                .where(NoteFolderTable.workspace_id == workspace_id)
                .order_by(NoteFolderTable.created_at),
            )
            notes = self._all(
                session, select(NoteTable).where(NoteTable.workspace_id == workspace_id)
            )
            counts = {}
            for note in notes:
                if note.folder_id:
                    counts[note.folder_id] = counts.get(note.folder_id, 0) + 1
            return [
                NoteFolder(
                    id=row.id,
                    workspace_id=row.workspace_id,
                    name=row.name,
                    note_count=counts.get(row.id, 0),
                    created_at=row.created_at,
                    updated_at=row.updated_at,
                )
                for row in rows
            ]

    def delete_folder(self, folder_id: str) -> bool:
        with Session(engine) as session:
            folder = session.get(NoteFolderTable, folder_id)
            if folder is None:
                return False
            notes = self._all(session, select(NoteTable).where(NoteTable.folder_id == folder_id))
            for note in notes:
                sections = self._all(
                    session,
                    select(NoteSectionTable).where(NoteSectionTable.note_id == note.id),
                )
                for section in sections:
                    session.delete(section)
            session.flush()
            for note in notes:
                session.delete(note)
            session.flush()
            session.delete(folder)
            session.commit()
            return True

    def save_note(self, note: Note) -> Note:
        with Session(engine) as session:
            row = session.get(NoteTable, note.id)
            values = {
                "workspace_id": note.workspace_id,
                "folder_id": note.folder_id,
                "content": note.content,
                "media_id": note.media_id,
                "title": note.title,
                "summary": note.summary,
                "version": note.version,
                "status": note.status,
                "action_items_json": json.dumps(note.action_items) if note.action_items else None,
                "generation_method": note.generation_method,
                "fallback_reason": note.fallback_reason,
                "provider_id": note.provider_id,
                "model_id": note.model_id,
                "updated_at": note.updated_at,
            }
            if row is None:
                row = NoteTable(id=note.id, created_at=note.created_at, **values)
            else:
                for name, value in values.items():
                    setattr(row, name, value)
            session.add(row)
            session.commit()
        if note.sections:
            self.replace_sections(note.id, note.sections)
        return note

    def get_note(self, note_id: str) -> Optional[Note]:
        with Session(engine) as session:
            row = session.get(NoteTable, note_id)
            return self._to_note(session, row) if row is not None else None

    def list_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        unorganized: bool = False,
    ) -> List[Note]:
        with Session(engine) as session:
            statement = select(NoteTable).where(NoteTable.workspace_id == workspace_id)
            if media_id is not None:
                statement = statement.where(NoteTable.media_id == media_id)
            if folder_id is not None:
                statement = statement.where(NoteTable.folder_id == folder_id)
            elif unorganized:
                statement = statement.where(NoteTable.folder_id.is_(None))
            rows = self._all(session, statement.order_by(NoteTable.updated_at.desc()))
            return [self._to_note(session, row, include_sections=False) for row in rows]

    def delete_note(self, note_id: str) -> bool:
        with Session(engine) as session:
            note = session.get(NoteTable, note_id)
            if note is None:
                return False
            sections = self._all(
                session,
                select(NoteSectionTable).where(NoteSectionTable.note_id == note_id),
            )
            for section in sections:
                session.delete(section)
            session.flush()
            session.delete(note)
            session.commit()
            return True

    def replace_sections(self, note_id: str, sections: List[NoteSection]) -> int:
        with Session(engine) as session:
            existing = self._all(
                session,
                select(NoteSectionTable).where(NoteSectionTable.note_id == note_id),
            )
            for row in existing:
                session.delete(row)
            session.flush()
            for section in sections:
                session.add(
                    NoteSectionTable(
                        id=section.id,
                        note_id=section.note_id,
                        workspace_id=section.workspace_id,
                        heading=section.heading,
                        body=section.body,
                        key_takeaways_json=(
                            json.dumps(section.key_takeaways)
                            if section.key_takeaways
                            else None
                        ),
                        start_time=section.start_time,
                        end_time=section.end_time,
                        source_chunk_ids=(
                            json.dumps(section.source_chunk_ids)
                            if section.source_chunk_ids
                            else None
                        ),
                        order_index=section.order_index,
                        created_at=section.created_at,
                    )
                )
            session.commit()
        return len(sections)

    def media_belongs_to_workspace(self, media_id: str, workspace_id: str) -> bool:
        with Session(engine) as session:
            media = session.get(MediaItemTable, media_id)
            return media is not None and media.workspace_id == workspace_id

    def list_transcript_chunks(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
    ) -> List[TranscriptChunkRecord]:
        with Session(engine) as session:
            statement = select(TranscriptChunkTable).where(
                TranscriptChunkTable.workspace_id == workspace_id
            )
            if media_id is not None:
                statement = statement.where(TranscriptChunkTable.media_id == media_id)
            statement = statement.order_by(
                TranscriptChunkTable.media_id, TranscriptChunkTable.chunk_index
            )
            rows = self._all(session, statement)
            return [
                {
                    "id": row.id,
                    "media_id": row.media_id,
                    "workspace_id": row.workspace_id,
                    "text": row.text,
                    "start_time": row.start_time,
                    "end_time": row.end_time,
                    "chunk_index": row.chunk_index,
                }
                for row in rows
            ]
