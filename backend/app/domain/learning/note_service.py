import json
import logging
import uuid
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.domain.learning.entities import Note, NoteFolder, NoteSection
from app.domain.learning.note_generation import (
    ExtractedNotes,
    build_notes_prompt,
    generate_notes_heuristic,
    parse_llm_notes,
)
from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import DomainEvent, EventBus

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def load_chunks(media_id: str, workspace_id: Optional[str] = None) -> List[dict]:
    """Load canonical transcript chunks for a media asset from SQLite."""
    if not engine or not Session or not select:
        return []
    try:
        from app.infrastructure.db.models import TranscriptChunkTable

        with Session(engine) as session:
            stmt = (
                select(TranscriptChunkTable)
                .where(TranscriptChunkTable.media_id == media_id)
                .order_by(TranscriptChunkTable.chunk_index)
            )
            records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
            return [
                {
                    "id": r.id,
                    "media_id": r.media_id,
                    "workspace_id": r.workspace_id,
                    "text": r.text,
                    "start_time": r.start_time,
                    "end_time": r.end_time,
                    "chunk_index": r.chunk_index,
                }
                for r in records
            ]
    except Exception as exc:
        logger.warning("load_chunks failed for media_id=%s — %s", media_id, exc)
        return []


def _json_loads_or_list(value) -> List[str]:
    if not value:
        return []
    if isinstance(value, list):
        return value
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, list) else []
    except Exception:
        return [p.strip() for p in str(value).split(",") if p.strip()]


class NoteService:
    """Domain service orchestrating structured study note generation, immutable
    versioning, and persistence grounded in transcript chunks and knowledge graphs."""

    def __init__(
        self,
        graph_service: Optional[KnowledgeGraphService] = None,
        ai_service_bus: Optional[AIServiceBus] = None,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self.graph_service = graph_service or KnowledgeGraphService()
        self.ai_service_bus = ai_service_bus
        self.event_bus = event_bus

    # ------------------------------------------------------------------
    # Versioning & Persistence helpers
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    def create_folder(self, workspace_id: str, name: str) -> NoteFolder:
        from app.infrastructure.db.models import NoteFolderTable

        now = datetime.utcnow()
        record = NoteFolderTable(
            id=f"folder_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            name=name.strip(),
            created_at=now,
            updated_at=now,
        )
        with Session(engine) as session:
            session.add(record)
            session.commit()
            session.refresh(record)
        return NoteFolder(
            id=record.id,
            workspace_id=record.workspace_id,
            name=record.name,
            note_count=0,
            created_at=record.created_at,
            updated_at=record.updated_at,
        )

    def list_folders(self, workspace_id: str) -> List[NoteFolder]:
        from app.infrastructure.db.models import NoteFolderTable, NoteTable

        with Session(engine) as session:
            statement = (
                select(NoteFolderTable)
                .where(NoteFolderTable.workspace_id == workspace_id)
                .order_by(NoteFolderTable.created_at)
            )
            records = self._scalars(session, statement)
            note_records = self._scalars(
                session,
                select(NoteTable).where(NoteTable.workspace_id == workspace_id),
            )
            counts = {}
            for note in note_records:
                if note.folder_id:
                    counts[note.folder_id] = counts.get(note.folder_id, 0) + 1
            return [
                NoteFolder(
                    id=record.id,
                    workspace_id=record.workspace_id,
                    name=record.name,
                    note_count=counts.get(record.id, 0),
                    created_at=record.created_at,
                    updated_at=record.updated_at,
                )
                for record in records
            ]

    def rename_folder(self, folder_id: str, name: str) -> Optional[NoteFolder]:
        from app.infrastructure.db.models import NoteFolderTable, NoteTable

        with Session(engine) as session:
            statement = select(NoteFolderTable).where(NoteFolderTable.id == folder_id)
            record = session.scalars(statement).first() if hasattr(session, "scalars") else session.exec(statement).first()
            if not record:
                return None
            record.name = name.strip()
            record.updated_at = datetime.utcnow()
            note_count = len(
                self._scalars(
                    session,
                    select(NoteTable).where(NoteTable.folder_id == folder_id),
                )
            )
            session.add(record)
            session.commit()
            return NoteFolder(
                id=record.id,
                workspace_id=record.workspace_id,
                name=record.name,
                note_count=note_count,
                created_at=record.created_at,
                updated_at=record.updated_at,
            )

    def delete_folder(self, folder_id: str) -> bool:
        from app.infrastructure.db.models import NoteFolderTable, NoteSectionTable, NoteTable

        with Session(engine) as session:
            folder_stmt = select(NoteFolderTable).where(NoteFolderTable.id == folder_id)
            folder = session.scalars(folder_stmt).first() if hasattr(session, "scalars") else session.exec(folder_stmt).first()
            if not folder:
                return False
            notes = self._scalars(session, select(NoteTable).where(NoteTable.folder_id == folder_id))
            for note in notes:
                sections = self._scalars(
                    session,
                    select(NoteSectionTable).where(NoteSectionTable.note_id == note.id),
                )
                for section in sections:
                    session.delete(section)
                session.delete(note)
            session.delete(folder)
            session.commit()
            return True

    def create_manual_note(
        self,
        workspace_id: str,
        title: str = "Untitled Note",
        folder_id: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Note:
        from app.infrastructure.db.models import NoteFolderTable, NoteTable

        now = datetime.utcnow()
        with Session(engine) as session:
            if folder_id:
                folder_stmt = select(NoteFolderTable).where(
                    NoteFolderTable.id == folder_id,
                    NoteFolderTable.workspace_id == workspace_id,
                )
                folder = session.scalars(folder_stmt).first() if hasattr(session, "scalars") else session.exec(folder_stmt).first()
                if not folder:
                    raise ValueError("Folder not found in workspace")
            record = NoteTable(
                id=f"note_{uuid.uuid4().hex}",
                workspace_id=workspace_id,
                folder_id=folder_id,
                content=content,
                title=title.strip() or "Untitled Note",
                version=1,
                status="ready",
                created_at=now,
                updated_at=now,
            )
            session.add(record)
            session.commit()
            note_id = record.id
        return self.get_note(note_id)

    def update_note(self, note_id: str, changes: dict) -> Optional[Note]:
        from app.infrastructure.db.models import NoteFolderTable, NoteTable

        with Session(engine) as session:
            statement = select(NoteTable).where(NoteTable.id == note_id)
            record = session.scalars(statement).first() if hasattr(session, "scalars") else session.exec(statement).first()
            if not record:
                return None

            if "folder_id" in changes and changes["folder_id"]:
                folder_stmt = select(NoteFolderTable).where(
                    NoteFolderTable.id == changes["folder_id"],
                    NoteFolderTable.workspace_id == record.workspace_id,
                )
                folder = session.scalars(folder_stmt).first() if hasattr(session, "scalars") else session.exec(folder_stmt).first()
                if not folder:
                    raise ValueError("Folder not found in workspace")

            if "title" in changes:
                record.title = (changes["title"] or "").strip() or "Untitled Note"
            if "content" in changes:
                record.content = changes["content"]
            if "folder_id" in changes:
                record.folder_id = changes["folder_id"]
            record.updated_at = datetime.utcnow()
            session.add(record)
            session.commit()
        return self.get_note(note_id)

    def delete_note(self, note_id: str) -> bool:
        from app.infrastructure.db.models import NoteSectionTable, NoteTable

        with Session(engine) as session:
            statement = select(NoteTable).where(NoteTable.id == note_id)
            note = session.scalars(statement).first() if hasattr(session, "scalars") else session.exec(statement).first()
            if not note:
                return False
            sections = self._scalars(
                session,
                select(NoteSectionTable).where(NoteSectionTable.note_id == note_id),
            )
            for section in sections:
                session.delete(section)
            session.delete(note)
            session.commit()
            return True

    def attach_audio(self, note_id: str, media_id: str) -> Optional[Note]:
        from app.infrastructure.db.models import MediaItemTable, NoteTable

        with Session(engine) as session:
            note_stmt = select(NoteTable).where(NoteTable.id == note_id)
            note = session.scalars(note_stmt).first() if hasattr(session, "scalars") else session.exec(note_stmt).first()
            if not note:
                return None
            media_stmt = select(MediaItemTable).where(
                MediaItemTable.id == media_id,
                MediaItemTable.workspace_id == note.workspace_id,
            )
            media = session.scalars(media_stmt).first() if hasattr(session, "scalars") else session.exec(media_stmt).first()
            if not media:
                raise ValueError("Audio media not found in note workspace")
            note.media_id = media_id
            note.updated_at = datetime.utcnow()
            session.add(note)
            session.commit()
        return self.get_note(note_id)

    def _latest_version(self, workspace_id: str, media_id: Optional[str] = None) -> int:
        if not engine or not Session or not select:
            return 0
        try:
            from app.infrastructure.db.models import NoteTable

            with Session(engine) as session:
                stmt = select(NoteTable).where(NoteTable.workspace_id == workspace_id)
                if media_id:
                    stmt = stmt.where(NoteTable.media_id == media_id)
                records = self._scalars(session, stmt)
                if not records:
                    return 0
                return max(int(getattr(r, "version", 1) or 1) for r in records)
        except Exception:
            return 0

    def _upsert_note_record(
        self,
        note_id: str,
        workspace_id: str,
        title: str,
        version: int,
        status: str,
        media_id: Optional[str] = None,
        summary: Optional[str] = None,
        action_items: Optional[List[str]] = None,
    ) -> None:
        if not engine or not Session or not select:
            return
        try:
            from app.infrastructure.db.models import NoteTable

            with Session(engine) as session:
                stmt = select(NoteTable).where(NoteTable.id == note_id)
                existing = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                if existing:
                    existing.title = title
                    existing.version = version
                    existing.status = status
                    existing.media_id = media_id
                    existing.summary = summary
                    existing.action_items_json = json.dumps(action_items) if action_items else None
                    existing.updated_at = datetime.utcnow()
                    session.add(existing)
                else:
                    session.add(
                        NoteTable(
                            id=note_id,
                            workspace_id=workspace_id,
                            media_id=media_id,
                            title=title,
                            summary=summary,
                            version=version,
                            status=status,
                            action_items_json=json.dumps(action_items) if action_items else None,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                    )
                session.commit()
        except Exception as exc:
            logger.warning("NoteService._upsert_note_record failed — %s", exc)

    def _persist_sections(
        self,
        note_id: str,
        workspace_id: str,
        media_id: Optional[str],
        sections: List[ExtractedNotes],
    ) -> int:
        if not engine or not Session or not select:
            return 0
        try:
            from app.infrastructure.db.models import NoteSectionTable

            with Session(engine) as session:
                # Delete any existing sections for this note_id
                stmt = select(NoteSectionTable).where(NoteSectionTable.note_id == note_id)
                existing = self._scalars(session, stmt)
                for rec in existing:
                    session.delete(rec)
                session.commit()

                count = 0
                for idx, sec in enumerate(sections):
                    sec_id = f"sec_{note_id}_{idx}"
                    session.add(
                        NoteSectionTable(
                            id=sec_id,
                            note_id=note_id,
                            workspace_id=workspace_id,
                            heading=sec.heading,
                            body=sec.body,
                            key_takeaways_json=json.dumps(sec.key_takeaways) if sec.key_takeaways else None,
                            start_time=sec.start_time,
                            end_time=sec.end_time,
                            source_chunk_ids=json.dumps(sec.source_chunk_ids) if sec.source_chunk_ids else None,
                            order_index=idx,
                            created_at=datetime.utcnow(),
                        )
                    )
                    count += 1
                session.commit()
                return count
        except Exception as exc:
            logger.warning("NoteService._persist_sections failed — %s", exc)
            return 0

    # ------------------------------------------------------------------
    # AI Generation
    # ------------------------------------------------------------------
    async def _generate_with_llm(
        self,
        chunks: List[dict],
        concepts: Optional[List[dict]] = None,
        custom_instruction: Optional[str] = None,
    ) -> Optional[ExtractedNotes]:
        if not self.ai_service_bus:
            logger.warning("NoteService: ai_service_bus is None — falling back to heuristic.")
            return None
        try:
            text_capability = self.ai_service_bus.get_text_capability()
        except Exception as exc:
            logger.warning("NoteService: failed to resolve text capability — %s", exc)
            return None

        prompt = build_notes_prompt(chunks, concepts, custom_instruction=custom_instruction)
        try:
            gen_res = await text_capability.generate(
                TextGenerationRequest(
                    prompt=prompt,
                    temperature=0.3,
                    max_tokens=4096,
                )
            )
        except Exception as exc:
            logger.warning("NoteService: LLM generate() raised — %s", exc)
            return None

        parsed = parse_llm_notes(gen_res.text)
        if not parsed:
            logger.warning(
                "NoteService: parse_llm_notes returned None (raw text len=%d). Falling back to heuristic.",
                len(gen_res.text or ""),
            )
        return parsed

    def _concept_dicts(self, workspace_id: str) -> List[dict]:
        try:
            concepts = self.graph_service.get_concepts(workspace_id)
            return [
                {
                    "id": c.id,
                    "name": c.name,
                    "description": c.description,
                    "source_chunk_ids": getattr(c, "source_chunk_ids", []),
                }
                for c in concepts
            ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Core Public Interface
    # ------------------------------------------------------------------
    async def generate_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        title: Optional[str] = None,
        custom_instruction: Optional[str] = None,
        force_new_version: bool = False,
    ) -> Note:
        """Generate structured study notes for a workspace / media asset.

        Notes are immutable: re-generating with ``force_new_version=True`` produces
        a new ``Note vN+1`` rather than mutating the existing one.
        """
        target_key = media_id or workspace_id

        def update_job(stage: str, progress: int, message: str, status: str = "generating") -> None:
            try:
                self.graph_service.upsert_artifact_job(
                    job_id=f"notes_{workspace_id}_{target_key}",
                    workspace_id=workspace_id,
                    artifact_type="notes",
                    target_key=target_key,
                    status=status,
                    stage=stage,
                    progress=progress,
                    message=message,
                )
            except Exception as exc:
                logger.warning("Failed to update artifact job status — %s", exc)

        latest = self._latest_version(workspace_id, media_id)
        cached = self.get_workspace_note(workspace_id, media_id=media_id, version=latest)
        if cached and cached.status == "ready" and not force_new_version:
            return cached

        version = latest + 1
        note_id = f"note_{workspace_id}_{target_key}_v{version}"
        note_title = title or f"Study Notes (v{version})"
        self._upsert_note_record(note_id, workspace_id, note_title, version, "generating", media_id=media_id)

        update_job("collect_context", 20, "Collecting transcript chunks and concepts...")

        chunks: List[dict] = []
        if media_id:
            chunks = load_chunks(media_id, workspace_id)
        else:
            # If no media_id specified, collect all chunks for the workspace
            try:
                from app.infrastructure.db.models import TranscriptChunkTable

                with Session(engine) as session:
                    stmt = (
                        select(TranscriptChunkTable)
                        .where(TranscriptChunkTable.workspace_id == workspace_id)
                        .order_by(TranscriptChunkTable.media_id, TranscriptChunkTable.chunk_index)
                    )
                    records = self._scalars(session, stmt)
                    chunks = [
                        {
                            "id": r.id,
                            "media_id": r.media_id,
                            "workspace_id": r.workspace_id,
                            "text": r.text,
                            "start_time": r.start_time,
                            "end_time": r.end_time,
                            "chunk_index": r.chunk_index,
                        }
                        for r in records
                    ]
            except Exception:
                chunks = []

        if not chunks:
            update_job("failed", 0, "No transcript chunks available for note generation.", status="failed")
            self._upsert_note_record(note_id, workspace_id, note_title, version, "failed", media_id=media_id)
            raise ValueError(f"No transcript chunks found for workspace '{workspace_id}' (media_id={media_id})")

        concepts = self._concept_dicts(workspace_id)

        update_job("llm_generation", 50, "Synthesizing comprehensive notes with AI model...")
        extracted: Optional[ExtractedNotes] = await self._generate_with_llm(chunks, concepts, custom_instruction=custom_instruction)
        if not extracted or not extracted.sections:
            extracted = generate_notes_heuristic(chunks, concepts, version=version)

        update_job("persist", 85, "Saving structured sections and action items...")
        final_title = title or extracted.title or note_title
        self._upsert_note_record(
            note_id=note_id,
            workspace_id=workspace_id,
            title=final_title,
            version=version,
            status="ready",
            media_id=media_id,
            summary=extracted.summary,
            action_items=extracted.action_items,
        )
        self._persist_sections(note_id, workspace_id, media_id, extracted.sections)

        update_job("ready", 100, "Notes ready.", status="ready")

        if self.event_bus:
            try:
                await self.event_bus.publish(
                    DomainEvent(
                        event_type="NoteGeneratedEvent",
                        aggregate_id=note_id,
                        payload={
                            "note_id": note_id,
                            "workspace_id": workspace_id,
                            "media_id": media_id,
                            "version": version,
                            "section_count": len(extracted.sections),
                        },
                    )
                )
            except Exception as exc:
                logger.warning("Failed to publish NoteGeneratedEvent — %s", exc)

        return self.get_note(note_id)

    async def generate_note_content(
        self,
        note_id: str,
        custom_instruction: Optional[str] = None,
    ) -> Note:
        """Generate and persist AI sections on an existing workspace note."""
        note = self.get_note(note_id)
        if not note:
            raise ValueError("Note not found")
        if not note.media_id:
            raise ValueError("Attach transcribed audio before generating notes")

        target_key = note.media_id

        def update_job(stage: str, progress: int, message: str, status: str = "generating") -> None:
            try:
                self.graph_service.upsert_artifact_job(
                    job_id=f"notes_{note.workspace_id}_{target_key}",
                    workspace_id=note.workspace_id,
                    artifact_type="notes",
                    target_key=target_key,
                    status=status,
                    stage=stage,
                    progress=progress,
                    message=message,
                )
            except Exception as exc:
                logger.warning("Failed to update artifact job status — %s", exc)

        self._upsert_note_record(
            note.id,
            note.workspace_id,
            note.title,
            note.version,
            "generating",
            media_id=note.media_id,
        )
        update_job("collect_context", 20, "Collecting transcript chunks and concepts...")
        chunks = load_chunks(note.media_id, note.workspace_id)
        if not chunks:
            self._upsert_note_record(
                note.id,
                note.workspace_id,
                note.title,
                note.version,
                "failed",
                media_id=note.media_id,
            )
            update_job("failed", 0, "No transcript chunks available for note generation.", status="failed")
            raise ValueError("No transcript chunks found for the attached audio")

        concepts = self._concept_dicts(note.workspace_id)
        update_job("llm_generation", 50, "Synthesizing comprehensive notes with AI model...")
        extracted = await self._generate_with_llm(
            chunks,
            concepts,
            custom_instruction=custom_instruction,
        )
        if not extracted or not extracted.sections:
            extracted = generate_notes_heuristic(chunks, concepts, version=note.version)

        update_job("persist", 85, "Saving structured sections and action items...")
        self._upsert_note_record(
            note.id,
            note.workspace_id,
            note.title,
            note.version,
            "ready",
            media_id=note.media_id,
            summary=extracted.summary,
            action_items=extracted.action_items,
        )
        self._persist_sections(note.id, note.workspace_id, note.media_id, extracted.sections)
        update_job("ready", 100, "Notes ready.", status="ready")
        return self.get_note(note.id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get_note(self, note_id: str) -> Optional[Note]:
        if not engine or not Session or not select:
            return None
        try:
            from app.infrastructure.db.models import NoteSectionTable, NoteTable

            with Session(engine) as session:
                stmt = select(NoteTable).where(NoteTable.id == note_id)
                n = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                if not n:
                    return None

                sec_stmt = (
                    select(NoteSectionTable)
                    .where(NoteSectionTable.note_id == note_id)
                    .order_by(NoteSectionTable.order_index)
                )
                sec_records = self._scalars(session, sec_stmt)
                sections = [
                    NoteSection(
                        id=s.id,
                        note_id=s.note_id,
                        workspace_id=s.workspace_id,
                        heading=s.heading,
                        body=s.body,
                        key_takeaways=_json_loads_or_list(getattr(s, "key_takeaways_json", None)),
                        media_id=n.media_id,
                        start_time=s.start_time,
                        end_time=s.end_time,
                        source_chunk_ids=_json_loads_or_list(getattr(s, "source_chunk_ids", None)),
                        order_index=s.order_index,
                        created_at=s.created_at,
                    )
                    for s in sec_records
                ]

                return Note(
                    id=n.id,
                    workspace_id=n.workspace_id,
                    title=n.title,
                    folder_id=getattr(n, "folder_id", None),
                    content=getattr(n, "content", None),
                    summary=n.summary,
                    media_id=n.media_id,
                    version=n.version,
                    status=n.status,
                    action_items=_json_loads_or_list(getattr(n, "action_items_json", None)),
                    sections=sections,
                    created_at=n.created_at,
                    updated_at=n.updated_at,
                )
        except Exception as exc:
            logger.warning("NoteService.get_note failed — %s", exc)
            return None

    def list_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        unorganized: bool = False,
    ) -> List[Note]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import NoteTable

            with Session(engine) as session:
                stmt = select(NoteTable).where(NoteTable.workspace_id == workspace_id)
                if media_id:
                    stmt = stmt.where(NoteTable.media_id == media_id)
                if folder_id:
                    stmt = stmt.where(NoteTable.folder_id == folder_id)
                elif unorganized:
                    stmt = stmt.where(NoteTable.folder_id.is_(None))
                stmt = stmt.order_by(NoteTable.updated_at.desc())
                records = self._scalars(session, stmt)
                return [
                    Note(
                        id=n.id,
                        workspace_id=n.workspace_id,
                        title=n.title,
                        folder_id=getattr(n, "folder_id", None),
                        content=getattr(n, "content", None),
                        summary=n.summary,
                        media_id=n.media_id,
                        version=n.version,
                        status=n.status,
                        action_items=_json_loads_or_list(getattr(n, "action_items_json", None)),
                        created_at=n.created_at,
                        updated_at=n.updated_at,
                    )
                    for n in records
                ]
        except Exception:
            return []

    def get_workspace_note(
        self, workspace_id: str, media_id: Optional[str] = None, version: int = 1
    ) -> Optional[Note]:
        if version <= 0:
            return None
        target_key = media_id or workspace_id
        note_id = f"note_{workspace_id}_{target_key}_v{version}"
        return self.get_note(note_id)

    def get_note_sections(self, note_id: str) -> List[NoteSection]:
        note = self.get_note(note_id)
        return note.sections if note else []
