import asyncio
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)

from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.exceptions import (
    LLMProviderError,
    LLMProviderAuthError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMProviderBadRequestError,
)
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.domain.learning.entities import Note, NoteFolder, NoteSection
from app.domain.learning.note_generation import (
    ExtractedNotes,
    build_notes_prompt,
    generate_notes_heuristic,
    parse_llm_notes,
)
from app.domain.learning.note_repository import InMemoryNoteRepository, NoteRepository
from app.infrastructure.events.event_bus import DomainEvent, EventBus

@dataclass
class ExtractedNotesResult:
    extracted: Optional[ExtractedNotes]
    generation_method: str = "llm"  # "llm" | "heuristic"
    fallback_reason: Optional[str] = None
    provider_id: Optional[str] = None
    model_id: Optional[str] = None

class NoteService:
    """Domain service orchestrating structured study note generation, immutable
    versioning, and persistence grounded in transcript chunks and knowledge graphs."""

    def __init__(
        self,
        graph_service: Optional[KnowledgeGraphService] = None,
        ai_service_bus: Optional[AIServiceBus] = None,
        event_bus: Optional[EventBus] = None,
        repository: Optional[NoteRepository] = None,
    ) -> None:
        self.graph_service = graph_service or KnowledgeGraphService()
        self.ai_service_bus = ai_service_bus
        self.event_bus = event_bus
        self.repository = repository or InMemoryNoteRepository()

    # ------------------------------------------------------------------
    # Versioning & Persistence helpers
    # ------------------------------------------------------------------
    def create_folder(self, workspace_id: str, name: str) -> NoteFolder:
        now = datetime.utcnow()
        folder = NoteFolder(
            id=f"folder_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            name=name.strip(),
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_folder(folder)

    def list_folders(self, workspace_id: str) -> List[NoteFolder]:
        return self.repository.list_folders(workspace_id)

    def rename_folder(self, folder_id: str, name: str) -> Optional[NoteFolder]:
        folder = self.repository.get_folder(folder_id)
        if folder is None:
            return None
        folder.name = name.strip()
        folder.updated_at = datetime.utcnow()
        self.repository.save_folder(folder)
        return self.repository.get_folder(folder_id)

    def delete_folder(self, folder_id: str) -> bool:
        return self.repository.delete_folder(folder_id)

    def create_manual_note(
        self,
        workspace_id: str,
        title: str = "Untitled Note",
        folder_id: Optional[str] = None,
        content: Optional[str] = None,
    ) -> Note:
        if folder_id:
            folder = self.repository.get_folder(folder_id)
            if folder is None or folder.workspace_id != workspace_id:
                raise ValueError("Folder not found in workspace")
        now = datetime.utcnow()
        note = Note(
            id=f"note_{uuid.uuid4().hex}",
            workspace_id=workspace_id,
            folder_id=folder_id,
            content=content,
            title=title.strip() or "Untitled Note",
            version=1,
            status="ready",
            generation_method="manual",
            created_at=now,
            updated_at=now,
        )
        return self.repository.save_note(note)

    def update_note(self, note_id: str, changes: dict) -> Optional[Note]:
        note = self.repository.get_note(note_id)
        if note is None:
            return None
        if "folder_id" in changes and changes["folder_id"]:
            folder = self.repository.get_folder(changes["folder_id"])
            if folder is None or folder.workspace_id != note.workspace_id:
                raise ValueError("Folder not found in workspace")
        if "title" in changes:
            note.title = (changes["title"] or "").strip() or "Untitled Note"
        if "content" in changes:
            note.content = changes["content"]
        if "folder_id" in changes:
            note.folder_id = changes["folder_id"]
        note.updated_at = datetime.utcnow()
        return self.repository.save_note(note)

    def delete_note(self, note_id: str) -> bool:
        return self.repository.delete_note(note_id)

    def attach_audio(self, note_id: str, media_id: str) -> Optional[Note]:
        note = self.repository.get_note(note_id)
        if note is None:
            return None
        if not media_id.startswith("note_audio_") and not self.repository.media_belongs_to_workspace(
            media_id, note.workspace_id
        ):
            raise ValueError("Audio media not found in note workspace")
        note.media_id = media_id
        note.updated_at = datetime.utcnow()
        return self.repository.save_note(note)

    def _latest_version(self, workspace_id: str, media_id: Optional[str] = None) -> int:
        records = self.repository.list_notes(workspace_id, media_id=media_id)
        if not records:
            return 0
        return max(int(record.version or 1) for record in records)

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
        generation_method: str = "llm",
        fallback_reason: Optional[str] = None,
        provider_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> None:
        try:
            existing = self.repository.get_note(note_id)
            now = datetime.utcnow()
            note = existing or Note(
                id=note_id,
                workspace_id=workspace_id,
                title=title,
                created_at=now,
            )
            note.title = title
            note.version = version
            note.status = status
            note.media_id = media_id
            note.summary = summary
            note.action_items = action_items or []
            note.generation_method = generation_method
            note.fallback_reason = fallback_reason
            note.provider_id = provider_id
            note.model_id = model_id
            note.updated_at = now
            self.repository.save_note(note)
        except Exception as exc:
            logger.warning("NoteService._upsert_note_record failed — %s", exc)

    def _persist_sections(
        self,
        note_id: str,
        workspace_id: str,
        media_id: Optional[str],
        sections: List[ExtractedNotes],
    ) -> int:
        try:
            records = [
                NoteSection(
                    id=f"sec_{note_id}_{idx}",
                    note_id=note_id,
                    workspace_id=workspace_id,
                    heading=section.heading,
                    body=section.body,
                    key_takeaways=section.key_takeaways,
                    media_id=media_id,
                    start_time=section.start_time,
                    end_time=section.end_time,
                    source_chunk_ids=section.source_chunk_ids,
                    order_index=idx,
                    created_at=datetime.utcnow(),
                )
                for idx, section in enumerate(sections)
            ]
            return self.repository.replace_sections(note_id, records)
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
    ) -> ExtractedNotesResult:
        if not self.ai_service_bus:
            logger.warning("NoteService: ai_service_bus is None — falling back to heuristic.")
            return ExtractedNotesResult(extracted=None, generation_method="heuristic", fallback_reason="no_ai_bus")

        try:
            text_capability = self.ai_service_bus.get_text_capability()
        except Exception as exc:
            logger.warning("NoteService: failed to resolve text capability — %s", exc)
            return ExtractedNotesResult(extracted=None, generation_method="heuristic", fallback_reason="capability_resolution_error")

        provider_id = getattr(text_capability, "provider_id", None)
        model_id = None
        if hasattr(text_capability, "_resolve_model"):
            try:
                model_id = text_capability._resolve_model()
            except Exception:
                model_id = getattr(text_capability, "default_model", None)
        elif hasattr(text_capability, "default_model"):
            model_id = getattr(text_capability, "default_model", None)

        prompt = build_notes_prompt(chunks, concepts, custom_instruction=custom_instruction)
        max_attempts = 3
        last_reason = "generation_failed"

        for attempt in range(1, max_attempts + 1):
            try:
                gen_res = await text_capability.generate(
                    TextGenerationRequest(
                        prompt=prompt,
                        temperature=0.3,
                        max_tokens=4096,
                    )
                )
                parsed = parse_llm_notes(gen_res.text)
                if parsed and parsed.sections:
                    logger.info(
                        "NoteService: LLM note generation succeeded (provider=%s, model=%s, sections=%d, attempt=%d)",
                        provider_id, model_id, len(parsed.sections), attempt,
                    )
                    return ExtractedNotesResult(
                        extracted=parsed,
                        generation_method="llm",
                        fallback_reason=None,
                        provider_id=provider_id,
                        model_id=model_id,
                    )
                else:
                    logger.warning(
                        "NoteService: parse_llm_notes returned invalid or empty sections (raw text len=%d, attempt=%d).",
                        len(gen_res.text or ""), attempt,
                    )
                    last_reason = "parse_error"
                    break
            except LLMProviderRateLimitError as exc:
                last_reason = "rate_limit"
                retry_after = exc.retry_after or min(1.5 * (2 ** (attempt - 1)), 6.0)
                logger.warning(
                    "NoteService: LLM rate limited (attempt %d/%d, retry_after=%.1fs) — %s",
                    attempt, max_attempts, retry_after, exc,
                )
                if attempt < max_attempts:
                    await asyncio.sleep(retry_after)
                    continue
            except LLMProviderTimeoutError as exc:
                last_reason = "timeout"
                logger.warning("NoteService: LLM generation timeout (attempt %d/%d) — %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    await asyncio.sleep(1.0)
                    continue
            except LLMProviderUnavailableError as exc:
                last_reason = "provider_unavailable"
                logger.warning("NoteService: LLM provider unavailable (attempt %d/%d) — %s", attempt, max_attempts, exc)
                if attempt < max_attempts:
                    await asyncio.sleep(1.5)
                    continue
            except LLMProviderAuthError as exc:
                last_reason = "auth_error"
                logger.warning("NoteService: LLM provider auth error — %s", exc)
                break
            except LLMProviderBadRequestError as exc:
                last_reason = "bad_request"
                logger.warning("NoteService: LLM provider rejected request — %s", exc)
                break
            except Exception as exc:
                last_reason = "provider_error"
                logger.warning("NoteService: LLM generate() raised unexpected exception — %s", exc)
                break

        return ExtractedNotesResult(
            extracted=None,
            generation_method="heuristic",
            fallback_reason=last_reason,
            provider_id=provider_id,
            model_id=model_id,
        )

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

        chunks = self.repository.list_transcript_chunks(workspace_id, media_id)

        if not chunks:
            update_job("failed", 0, "No transcript chunks available for note generation.", status="failed")
            self._upsert_note_record(note_id, workspace_id, note_title, version, "failed", media_id=media_id)
            raise ValueError(f"No transcript chunks found for workspace '{workspace_id}' (media_id={media_id})")

        concepts = self._concept_dicts(workspace_id)

        update_job("llm_generation", 50, "Synthesizing comprehensive notes with AI model...")
        result = await self._generate_with_llm(chunks, concepts, custom_instruction=custom_instruction)
        if result.extracted and result.extracted.sections:
            extracted = result.extracted
            generation_method = "llm"
            fallback_reason = None
        else:
            extracted = generate_notes_heuristic(chunks, concepts, version=version)
            generation_method = "heuristic"
            fallback_reason = result.fallback_reason or "heuristic_fallback"

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
            generation_method=generation_method,
            fallback_reason=fallback_reason,
            provider_id=result.provider_id,
            model_id=result.model_id,
        )
        self._persist_sections(note_id, workspace_id, media_id, extracted.sections)

        job_msg = "Notes ready." if generation_method == "llm" else f"Notes ready (heuristic fallback: {fallback_reason})."
        update_job("ready", 100, job_msg, status="ready")

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
                            "generation_method": generation_method,
                            "fallback_reason": fallback_reason,
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
        if not note.media_id and not (note.content and note.content.strip()):
            raise ValueError("Add note content or record audio before generating notes")

        target_key = note.media_id or note.id

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
        chunks = (
            self.repository.list_transcript_chunks(note.workspace_id, note.media_id)
            if note.media_id
            else []
        )
        if not chunks and note.content and note.content.strip():
            chunks = [
                {
                    "id": f"chunk_manual_{note.id}",
                    "media_id": note.media_id or f"manual_{note.id}",
                    "workspace_id": note.workspace_id,
                    "text": note.content.strip(),
                    "start_time": None,
                    "end_time": None,
                    "chunk_index": 0,
                }
            ]
        if not chunks:
            self._upsert_note_record(
                note.id,
                note.workspace_id,
                note.title,
                note.version,
                "failed",
                media_id=note.media_id,
            )
            update_job("failed", 0, "No content or transcript chunks available for note generation.", status="failed")
            raise ValueError("No content or transcript chunks available for note generation")

        concepts = self._concept_dicts(note.workspace_id)
        update_job("llm_generation", 50, "Synthesizing comprehensive notes with AI model...")
        result = await self._generate_with_llm(
            chunks,
            concepts,
            custom_instruction=custom_instruction,
        )
        if result.extracted and result.extracted.sections:
            extracted = result.extracted
            generation_method = "llm"
            fallback_reason = None
        else:
            extracted = generate_notes_heuristic(chunks, concepts, version=note.version)
            generation_method = "heuristic"
            fallback_reason = result.fallback_reason or "heuristic_fallback"

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
            generation_method=generation_method,
            fallback_reason=fallback_reason,
            provider_id=result.provider_id,
            model_id=result.model_id,
        )
        self._persist_sections(note.id, note.workspace_id, note.media_id, extracted.sections)
        job_msg = "Notes ready." if generation_method == "llm" else f"Notes ready (heuristic fallback: {fallback_reason})."
        update_job("ready", 100, job_msg, status="ready")
        return self.get_note(note.id)

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get_note(self, note_id: str) -> Optional[Note]:
        return self.repository.get_note(note_id)

    def list_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        unorganized: bool = False,
    ) -> List[Note]:
        return self.repository.list_notes(
            workspace_id,
            media_id=media_id,
            folder_id=folder_id,
            unorganized=unorganized,
        )

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
