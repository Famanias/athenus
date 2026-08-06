import json
import uuid
from datetime import datetime
from typing import List, Optional

from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.domain.learning.entities import (
    Flashcard,
    FlashcardCard,
    FlashcardDeck,
    FlashcardReview,
)
from app.domain.learning.flashcard_generation import (
    ExtractedFlashcard,
    build_flashcard_prompt,
    generate_flashcards_heuristic,
    parse_llm_flashcards,
)
from app.domain.learning.sm2 import sm2_review
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import DomainEvent, EventBus

try:
    # pyrefly: ignore [missing-import]
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def load_chunks(media_id: str, workspace_id: str) -> List[dict]:
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
    except Exception:
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
        return [p for p in str(value).split(",") if p]


class FlashcardService:
    """On-demand, permanently-cached, versioned flashcard decks grounded in the
    canonical knowledge graph with SM-2 spaced repetition scheduling."""

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
    # Deck persistence & versioning
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    def _latest_version(self, workspace_id: str) -> int:
        if not engine or not Session or not select:
            return 0
        try:
            from app.infrastructure.db.models import FlashcardDeckTable
            with Session(engine) as session:
                stmt = select(FlashcardDeckTable).where(
                    FlashcardDeckTable.workspace_id == workspace_id
                )
                records = self._scalars(session, stmt)
                versions = [r.version or 1 for r in records]
                return max(versions, default=0)
        except Exception:
            return 0

    def _upsert_deck(
        self,
        deck_id: str,
        workspace_id: str,
        name: str,
        version: int,
        status: str,
        card_count: int = 0,
        media_ids: Optional[List[str]] = None,
        concept_ids: Optional[List[str]] = None,
    ) -> None:
        if not engine or not Session:
            return
        try:
            from app.infrastructure.db.models import FlashcardDeckTable
            with Session(engine) as session:
                deck = session.get(FlashcardDeckTable, deck_id)
                if deck:
                    deck.status = status
                    deck.card_count = card_count
                    deck.updated_at = datetime.utcnow()
                else:
                    deck = FlashcardDeckTable(
                        id=deck_id,
                        workspace_id=workspace_id,
                        name=name,
                        version=version,
                        status=status,
                        media_ids=",".join(media_ids) if media_ids else None,
                        concept_ids=",".join(concept_ids) if concept_ids else None,
                        card_count=card_count,
                    )
                    session.add(deck)
                session.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Card generation
    # ------------------------------------------------------------------
    async def _generate_with_llm(self, concepts: List[dict], chunks: List[dict]) -> List[ExtractedFlashcard]:
        if not self.ai_service_bus:
            return []
        try:
            text_capability = self.ai_service_bus.get_text_capability()
        except Exception:
            return []
        try:
            gen_res = await text_capability.generate(
                TextGenerationRequest(
                    prompt=build_flashcard_prompt(concepts, chunks),
                    temperature=0.4,
                    max_tokens=2048,
                )
            )
        except Exception:
            return []
        parsed = parse_llm_flashcards(gen_res.text)
        return parsed or []

    def _concept_dicts(self, workspace_id: str) -> List[dict]:
        concepts = self.graph_service.get_concepts(workspace_id)
        return [
            {
                "id": c.id,
                "name": c.name,
                "description": c.description,
                "source_chunk_ids": c.source_chunk_ids,
                "media_id": c.media_id,
                "start_time": c.start_time,
                "end_time": c.end_time,
            }
            for c in concepts
        ]

    async def generate_deck(
        self,
        workspace_id: str,
        name: str = "Auto-generated",
        max_cards: int = 40,
        force_new_version: bool = False,
    ) -> FlashcardDeck:
        """Generate (or reuse a cached) versioned flashcard deck for a workspace.

        Decks are immutable: re-generating with ``force_new_version`` produces a
        new ``Deck vN+1`` rather than mutating the existing one. A cached ``ready``
        deck is returned on subsequent calls.

        Version regeneration performs a fresh AI generation request using concept
        and transcript chunk rotation instead of cloning previous version cards.
        """
        def update_job(stage: str, progress: int, message: str, status: str = "generating") -> None:
            self.graph_service.upsert_artifact_job(
                job_id=f"flashcards_{workspace_id}",
                workspace_id=workspace_id,
                artifact_type="flashcards",
                target_key=workspace_id,
                status=status,
                stage=stage,
                progress=progress,
                message=message,
            )

        concept_dicts = self._concept_dicts(workspace_id)
        if not concept_dicts:
            raise ValueError(f"No concepts indexed for workspace {workspace_id}")

        latest = self._latest_version(workspace_id)
        cached = self.get_workspace_deck(workspace_id, version=latest)
        if cached and cached.status == "ready" and not force_new_version:
            return cached

        version = latest + 1
        deck_id = f"deck_{workspace_id}_v{version}"
        self._upsert_deck(
            deck_id, workspace_id, name, version, "generating",
        )

        update_job("collect_context", 20, "Collecting concepts and transcript chunks...")

        media_ids: List[str] = []
        concept_ids: List[str] = []
        for c in concept_dicts:
            concept_ids.append(c["id"])
            if c.get("media_id") and c["media_id"] not in media_ids:
                media_ids.append(c["media_id"])

        all_chunks: List[dict] = []
        for media_id in media_ids:
            all_chunks.extend(load_chunks(media_id, workspace_id))
        # Deduplicate chunks by id
        seen: set = set()
        chunks = [c for c in all_chunks if not (c["id"] in seen or seen.add(c["id"]))]

        if force_new_version and version > 1:
            selected_concepts, prompt_chunks = self._rotate_concepts_and_chunks(
                workspace_id, concept_dicts, chunks, version
            )
        else:
            selected_concepts = concept_dicts[:12]
            prompt_chunks = chunks

        update_job("llm_generation", 50, "Generating cards with AI model...")
        cards = await self._generate_with_llm(selected_concepts, prompt_chunks)
        if not cards:
            cards = generate_flashcards_heuristic(selected_concepts, prompt_chunks, max_cards=max_cards)

        update_job("persist", 85, "Saving cards to database...")
        saved_count = self._persist_cards(
            deck_id, workspace_id, version, cards, concept_dicts
        )
        self._upsert_deck(
            deck_id, workspace_id, name, version, "ready",
            card_count=saved_count,
            media_ids=media_ids,
            concept_ids=concept_ids,
        )
        update_job("ready", 100, "Deck ready.", status="ready")
        return self.get_deck(deck_id)

    def _concept_coverage(self, workspace_id: str) -> dict:
        """Map concept_id -> number of cards already generated across all prior
        deck versions for the workspace."""
        coverage: dict = {}
        if not engine or not Session or not select:
            return coverage
        try:
            from app.infrastructure.db.models import FlashcardTable
            with Session(engine) as session:
                stmt = select(FlashcardTable).where(FlashcardTable.workspace_id == workspace_id)
                records = self._scalars(session, stmt)
                for r in records:
                    if r.concept_id:
                        coverage[r.concept_id] = coverage.get(r.concept_id, 0) + 1
        except Exception:
            pass
        return coverage

    def _rotate_concepts_and_chunks(
        self,
        workspace_id: str,
        concept_dicts: List[dict],
        chunks: List[dict],
        version: int,
        max_concepts: int = 12,
    ):
        """Rotate concept selection toward the least-covered concepts and sample
        transcript chunks from a version-based offset for fresh LLM context."""
        coverage = self._concept_coverage(workspace_id)
        ranked = sorted(
            concept_dicts,
            key=lambda c: (coverage.get(c["id"], 0), c["name"]),
        )
        selected_concepts = ranked[:max_concepts] or ranked
        if chunks:
            offset = (version - 1) % len(chunks)
            rotated_chunks = chunks[offset:] + chunks[:offset]
        else:
            rotated_chunks = chunks
        return selected_concepts, rotated_chunks

    async def evolve_workspace_deck(
        self,
        workspace_id: str,
        new_concept_ids: List[str],
        name: str = "Auto-evolved Deck",
        target_budget: int = 20,
    ) -> Optional[FlashcardDeck]:
        """Evolve workspace deck when new concepts are merged into the Knowledge Graph."""
        if not new_concept_ids:
            return self.get_workspace_deck(workspace_id)

        all_concept_dicts = self._concept_dicts(workspace_id)
        if not all_concept_dicts:
            return None

        new_concepts = [c for c in all_concept_dicts if c["id"] in new_concept_ids]
        if not new_concepts:
            return self.get_workspace_deck(workspace_id)

        from app.domain.learning.concept_importance_allocator import (
            ConceptImportanceAllocator,
            ConceptNodeDTO,
            RelationDTO,
        )
        allocator = ConceptImportanceAllocator()
        
        triples = self.graph_service.get_workspace_triples(workspace_id)
        relation_dtos = [RelationDTO(source_concept=t[0], target_concept=t[2]) for t in triples if len(t) >= 3]
        concept_dtos = [ConceptNodeDTO(id=c["id"], name=c["name"]) for c in new_concepts]

        allocations = allocator.calculate_allocations(concept_dtos, relation_dtos, total_budget=target_budget)

        media_ids: List[str] = []
        for c in new_concepts:
            if c.get("media_id") and c["media_id"] not in media_ids:
                media_ids.append(c["media_id"])

        all_chunks: List[dict] = []
        for media_id in media_ids:
            all_chunks.extend(load_chunks(media_id, workspace_id))
        seen: set = set()
        chunks = [c for c in all_chunks if not (c["id"] in seen or seen.add(c["id"]))]

        new_extracted_cards = await self._generate_with_llm(new_concepts, chunks)
        if not new_extracted_cards:
            new_extracted_cards = generate_flashcards_heuristic(new_concepts, chunks, max_cards=target_budget)

        latest_version = self._latest_version(workspace_id)
        new_version = latest_version + 1
        new_deck_id = f"deck_{workspace_id}_v{new_version}"
        self._upsert_deck(new_deck_id, workspace_id, name, new_version, "generating")

        new_cards_count = self._persist_cards(new_deck_id, workspace_id, new_version, new_extracted_cards, new_concepts)
        total_card_count = new_cards_count

        all_concept_ids = [c["id"] for c in all_concept_dicts]
        all_media_ids = list(set([c.get("media_id") for c in all_concept_dicts if c.get("media_id")]))

        self._upsert_deck(
            new_deck_id, workspace_id, name, new_version, "ready",
            card_count=total_card_count,
            media_ids=all_media_ids,
            concept_ids=all_concept_ids,
        )
        return self.get_deck(new_deck_id)

    def _persist_cards(
        self,
        deck_id: str,
        workspace_id: str,
        version: int,
        cards: List[ExtractedFlashcard],
        concepts: List[dict],
    ) -> int:
        if not engine or not Session:
            return 0
        concept_by_name = {c["name"].lower(): c for c in concepts}
        saved = 0
        try:
            from app.infrastructure.db.models import FlashcardTable
            with Session(engine) as session:
                for card in cards:
                    concept = concept_by_name.get((card.concept or "").lower(), {})
                    if not concept and concepts:
                        concept = concepts[saved % len(concepts)]
                    card_id = f"card_{deck_id}_{uuid.uuid4().hex[:8]}"
                    session.add(
                        FlashcardTable(
                            id=card_id,
                            deck_id=deck_id,
                            workspace_id=workspace_id,
                            concept_id=concept.get("id"),
                            card_type=card.card_type,
                            front=card.front,
                            back=card.back,
                            cloze_text=card.cloze_text,
                            options_json=json.dumps(card.options) if card.options else None,
                            media_id=card.media_id or concept.get("media_id"),
                            source_chunk_ids=",".join(card.source_chunk_ids or concept.get("source_chunk_ids", [])) or None,
                            start_time=card.start_time if card.start_time is not None else concept.get("start_time"),
                            end_time=card.end_time if card.end_time is not None else concept.get("end_time"),
                        )
                    )
                    saved += 1
                session.commit()
        except Exception:
            return 0
        return saved

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------
    def get_deck(self, deck_id: str) -> Optional[FlashcardDeck]:
        if not engine or not Session:
            return None
        try:
            from app.infrastructure.db.models import FlashcardDeckTable
            with Session(engine) as session:
                rec = session.get(FlashcardDeckTable, deck_id)
                if not rec:
                    return None
                return self._deck_from_db(rec)
        except Exception:
            return None

    def get_workspace_deck(self, workspace_id: str, version: Optional[int] = None) -> Optional[FlashcardDeck]:
        if not engine or not Session or not select:
            return None
        try:
            from app.infrastructure.db.models import FlashcardDeckTable
            with Session(engine) as session:
                stmt = select(FlashcardDeckTable).where(
                    FlashcardDeckTable.workspace_id == workspace_id
                )
                if version is not None:
                    stmt = stmt.where(FlashcardDeckTable.version == version)
                stmt = stmt.order_by(FlashcardDeckTable.version.desc())
                rec = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                if not rec:
                    return None
                return self._deck_from_db(rec)
        except Exception:
            return None

    def list_decks(self, workspace_id: str) -> List[FlashcardDeck]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import FlashcardDeckTable
            with Session(engine) as session:
                stmt = (
                    select(FlashcardDeckTable)
                    .where(FlashcardDeckTable.workspace_id == workspace_id)
                    .order_by(FlashcardDeckTable.version.desc())
                )
                records = self._scalars(session, stmt)
                return [self._deck_from_db(r) for r in records]
        except Exception:
            return []

    def get_deck_cards(self, deck_id: str) -> List[FlashcardCard]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import FlashcardTable
            with Session(engine) as session:
                stmt = select(FlashcardTable).where(FlashcardTable.deck_id == deck_id)
                records = self._scalars(session, stmt)
                return [self._card_from_db(r) for r in records]
        except Exception:
            return []

    @staticmethod
    def _deck_from_db(rec) -> FlashcardDeck:
        return FlashcardDeck(
            id=rec.id,
            workspace_id=rec.workspace_id,
            name=rec.name,
            version=rec.version or 1,
            status=rec.status,
            media_ids=_json_loads_or_list(rec.media_ids),
            concept_ids=_json_loads_or_list(rec.concept_ids),
            card_count=rec.card_count or 0,
            created_at=rec.created_at,
            updated_at=rec.updated_at,
        )

    @staticmethod
    def _card_from_db(rec) -> FlashcardCard:
        return FlashcardCard(
            id=rec.id,
            deck_id=rec.deck_id,
            workspace_id=rec.workspace_id,
            card_type=rec.card_type,
            front=rec.front,
            back=rec.back,
            cloze_text=rec.cloze_text,
            options=_json_loads_or_list(rec.options_json),
            concept_id=rec.concept_id,
            media_id=rec.media_id,
            source_chunk_ids=_json_loads_or_list(rec.source_chunk_ids),
            start_time=rec.start_time,
            end_time=rec.end_time,
            ease_factor=rec.ease_factor,
            interval_days=rec.interval_days,
            repetitions=rec.repetitions,
            next_review_at=None,
        )

    # ------------------------------------------------------------------
    # SM-2 review scheduling
    # ------------------------------------------------------------------
    def _last_review(self, flashcard_id: str) -> Optional[FlashcardReview]:
        if not engine or not Session or not select:
            return None
        try:
            from app.infrastructure.db.models import FlashcardReviewTable
            with Session(engine) as session:
                stmt = (
                    select(FlashcardReviewTable)
                    .where(FlashcardReviewTable.flashcard_id == flashcard_id)
                    .order_by(FlashcardReviewTable.reviewed_at.desc())
                )
                rec = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                if not rec:
                    return None
                return FlashcardReview(
                    id=rec.id,
                    flashcard_id=rec.flashcard_id,
                    workspace_id=rec.workspace_id,
                    rating=rec.rating,
                    ease_factor=rec.ease_factor,
                    interval_days=rec.interval_days,
                    repetitions=rec.repetitions,
                    reviewed_at=rec.reviewed_at,
                )
        except Exception:
            return None

    def record_review(
        self,
        flashcard_id: str,
        workspace_id: str,
        rating: int,
        now: Optional[datetime] = None,
    ) -> FlashcardReview:
        """Apply the SM-2 algorithm and append an immutable review record."""
        rating = max(1, min(4, int(rating)))
        last = self._last_review(flashcard_id)
        prev_ef = last.ease_factor if last else 2.5
        prev_interval = last.interval_days if last else 0
        prev_reps = last.repetitions if last else 0

        result = sm2_review(
            ease_factor=prev_ef,
            interval_days=prev_interval,
            repetitions=prev_reps,
            rating=rating,
            now=now,
        )
        review = FlashcardReview(
            id=f"review_{uuid.uuid4().hex[:12]}",
            flashcard_id=flashcard_id,
            workspace_id=workspace_id,
            rating=rating,
            ease_factor=result.ease_factor,
            interval_days=result.interval_days,
            repetitions=result.repetitions,
            reviewed_at=now or datetime.utcnow(),
        )
        if engine and Session:
            try:
                from app.infrastructure.db.models import FlashcardReviewTable
                with Session(engine) as session:
                    session.add(
                        FlashcardReviewTable(
                            id=review.id,
                            flashcard_id=review.flashcard_id,
                            workspace_id=review.workspace_id,
                            rating=review.rating,
                            ease_factor=review.ease_factor,
                            interval_days=review.interval_days,
                            repetitions=review.repetitions,
                            reviewed_at=review.reviewed_at,
                        )
                    )
                    session.commit()
            except Exception:
                pass

        # Emit analytics event with concept grounding.
        if self.event_bus:
            card = self._get_card_meta(flashcard_id)
            import asyncio
            try:
                asyncio.get_event_loop().create_task(
                    self.event_bus.publish(
                        DomainEvent(
                            event_type="FlashcardReviewedEvent",
                            aggregate_id=workspace_id,
                            payload={
                                "workspace_id": workspace_id,
                                "flashcard_id": flashcard_id,
                                "rating": rating,
                                "ease_factor": review.ease_factor,
                                "concept_id": (card or {}).get("concept_id"),
                            },
                        )
                    )
                )
            except Exception:
                pass
        return review

    def _get_card_meta(self, flashcard_id: str) -> Optional[dict]:
        """Lightweight metadata lookup for event payloads (avoids loading full cards)."""
        if not engine or not Session:
            return None
        try:
            from app.infrastructure.db.models import FlashcardTable
            with Session(engine) as session:
                rec = session.get(FlashcardTable, flashcard_id)
                if not rec:
                    return None
                return {"concept_id": rec.concept_id}
        except Exception:
            return None

    def due_cards(self, workspace_id: str, limit: int = 30, now: Optional[datetime] = None) -> List[FlashcardCard]:
        """Cards whose next review is due, newest decks first."""
        now = now or datetime.utcnow()
        cards: List[FlashcardCard] = []
        for deck in self.list_decks(workspace_id):
            for card in self.get_deck_cards(deck.id):
                last = self._last_review(card.id)
                due_at = last.reviewed_at if last else None
                interval = last.interval_days if last else 0
                if due_at is None:
                    cards.append(card)
                elif interval <= 0:
                    cards.append(card)
                else:
                    from datetime import timedelta
                    if due_at + timedelta(days=interval) <= now:
                        cards.append(card)
                if len(cards) >= limit:
                    return cards
        return cards


def build_legacy_flashcards(workspace_id: str, concepts: List[dict], chunks: List[dict]) -> List[Flashcard]:
    """Backward-compatible deterministic flashcards (used by legacy endpoints/tests)."""
    extracted = generate_flashcards_heuristic(concepts, chunks, max_cards=10)
    return [
        Flashcard(
            id=f"card_{uuid.uuid4().hex[:8]}",
            workspace_id=workspace_id,
            front_prompt=c.front,
            back_answer=c.back or "",
            concept_id=c.concept,
        )
        for c in extracted
    ]
