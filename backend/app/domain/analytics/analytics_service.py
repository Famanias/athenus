"""Precomputed, event-driven learning analytics.

Subscribes to learning events (``QuizAttemptEvent``, ``ConceptGraphUpdatedEvent``,
flashcard review calls) and maintains denormalized counters in
``WorkspaceAnalyticsTable`` / ``ConceptMasteryTable`` plus immutable
``StudySessionTable`` rows. Exposes revision recommendations computed from
concept mastery and SM-2 due cards.
"""
import json
import uuid
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from app.domain.learning.entities import FlashcardCard
from app.domain.learning.flashcard_service import FlashcardService
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import DomainEvent, EventBus

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


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


class AnalyticsService:
    """Maintains precomputed workspace analytics and concept mastery scores."""

    def __init__(
        self,
        event_bus: Optional[EventBus] = None,
        graph_service: Optional[KnowledgeGraphService] = None,
        flashcard_service: Optional[FlashcardService] = None,
    ) -> None:
        self.event_bus = event_bus
        self.graph_service = graph_service or KnowledgeGraphService()
        self.flashcard_service = flashcard_service or FlashcardService(graph_service=self.graph_service)
        if self.event_bus:
            self.event_bus.subscribe("QuizAttemptEvent", self.handle_quiz_attempt)
            self.event_bus.subscribe("ConceptGraphUpdatedEvent", self.handle_graph_updated)
            self.event_bus.subscribe("FlashcardReviewedEvent", self.handle_flashcard_review)

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    def _get_workspace_analytics(self, session, workspace_id: str):
        from app.infrastructure.db.models import WorkspaceAnalyticsTable
        return session.get(WorkspaceAnalyticsTable, workspace_id)

    def _ensure_workspace_analytics(self, session, workspace_id: str):
        from app.infrastructure.db.models import WorkspaceAnalyticsTable
        record = self._get_workspace_analytics(session, workspace_id)
        if not record:
            record = WorkspaceAnalyticsTable(workspace_id=workspace_id)
            session.add(record)
            session.flush()
        return record

    def _get_concept_mastery(self, session, concept_id: str):
        from app.infrastructure.db.models import ConceptMasteryTable
        return session.get(ConceptMasteryTable, concept_id)

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    async def handle_quiz_attempt(self, event: DomainEvent) -> None:
        if not engine or not Session:
            return
        workspace_id = event.payload.get("workspace_id") or event.aggregate_id
        score = float(event.payload.get("score", 0.0))
        correct = int(event.payload.get("correct_count", 0))
        total = int(event.payload.get("total_questions", 0))
        concept_results = event.payload.get("concept_results") or {}

        try:
            with Session(engine) as session:
                ws = self._ensure_workspace_analytics(session, workspace_id)
                ws.total_quiz_attempts = (ws.total_quiz_attempts or 0) + 1
                ws.total_study_seconds = (ws.total_study_seconds or 0.0) + float(event.payload.get("time_taken", 0.0))
                if ws.total_quiz_attempts > 1:
                    ws.avg_quiz_score = (
                        ((ws.avg_quiz_score or 0.0) * (ws.total_quiz_attempts - 1)) + score
                    ) / ws.total_quiz_attempts
                else:
                    ws.avg_quiz_score = score
                ws.last_activity_at = datetime.utcnow()
                ws.updated_at = datetime.utcnow()
                self._record_study_session(session, workspace_id, "quiz", float(event.payload.get("time_taken", 0.0)))

                # Concept mastery per question
                for question_id, result in concept_results.items():
                    concept_id = None
                    if isinstance(result, dict) and result.get("concept_id"):
                        concept_id = result["concept_id"]
                    if not concept_id:
                        continue
                    mastery = self._get_concept_mastery(session, concept_id)
                    if not mastery:
                        from app.infrastructure.db.models import ConceptMasteryTable
                        concept = self.graph_service.get_concept(concept_id)
                        mastery = ConceptMasteryTable(
                            concept_id=concept_id,
                            workspace_id=workspace_id,
                            concept_name=concept.name if concept else "",
                        )
                        session.add(mastery)
                        session.flush()
                    mastery.quiz_attempts = (mastery.quiz_attempts or 0) + 1
                    if isinstance(result, dict) and result.get("is_correct"):
                        mastery.quiz_correct = (mastery.quiz_correct or 0) + 1
                    mastery.mastery_level = self._compute_mastery(mastery.quiz_correct, mastery.quiz_attempts, mastery.review_count)
                    mastery.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

    async def handle_graph_updated(self, event: DomainEvent) -> None:
        if not engine or not Session:
            return
        workspace_id = event.payload.get("workspace_id") or event.aggregate_id
        try:
            with Session(engine) as session:
                ws = self._ensure_workspace_analytics(session, workspace_id)
                ws.total_concepts = self.graph_service.get_concepts(workspace_id).__len__()
                ws.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

    async def handle_flashcard_review(self, event: DomainEvent) -> None:
        if not engine or not Session:
            return
        workspace_id = event.payload.get("workspace_id") or event.aggregate_id
        concept_id = event.payload.get("concept_id")
        rating = int(event.payload.get("rating", 3))
        try:
            with Session(engine) as session:
                ws = self._ensure_workspace_analytics(session, workspace_id)
                ws.total_reviews = (ws.total_reviews or 0) + 1
                ws.review_streak_days = self._compute_streak(session, workspace_id, ws.review_streak_days or 0)
                ws.last_activity_at = datetime.utcnow()
                ws.updated_at = datetime.utcnow()
                self._record_study_session(session, workspace_id, "review", 0.0)

                if concept_id:
                    mastery = self._get_concept_mastery(session, concept_id)
                    if not mastery:
                        from app.infrastructure.db.models import ConceptMasteryTable
                        concept = self.graph_service.get_concept(concept_id)
                        mastery = ConceptMasteryTable(
                            concept_id=concept_id,
                            workspace_id=workspace_id,
                            concept_name=concept.name if concept else "",
                        )
                        session.add(mastery)
                        session.flush()
                    mastery.review_count = (mastery.review_count or 0) + 1
                    mastery.last_reviewed_at = datetime.utcnow()
                    # Successful recalls (rating >= 3) boost mastery.
                    if rating >= 3:
                        mastery.mastery_level = self._compute_mastery(mastery.quiz_correct, mastery.quiz_attempts, mastery.review_count, success_bonus=0.05)
                    else:
                        mastery.mastery_level = self._compute_mastery(mastery.quiz_correct, mastery.quiz_attempts, mastery.review_count, success_bonus=-0.03)
                    mastery.updated_at = datetime.utcnow()
                session.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _compute_mastery(quiz_correct: int, quiz_attempts: int, review_count: int, success_bonus: float = 0.0) -> float:
        score = 0.0
        if quiz_attempts > 0:
            score += 0.6 * (quiz_correct / quiz_attempts)
        score += 0.4 * min(1.0, (review_count or 0) / 10.0)
        score += success_bonus
        return max(0.0, min(1.0, round(score, 3)))

    @staticmethod
    def _compute_streak(session, workspace_id: str, current_streak: int) -> int:
        """Increment or reset the review streak based on the last activity date."""
        try:
            from app.infrastructure.db.models import StudySessionTable
            stmt = (
                select(StudySessionTable)
                .where(StudySessionTable.workspace_id == workspace_id)
                .order_by(StudySessionTable.created_at.desc())
            )
            records = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
            if records and records.created_at:
                last = records.created_at.date()
                today = date.today()
                if last == today:
                    return max(current_streak, 1)
                if (today - last).days == 1:
                    return current_streak + 1
                if (today - last).days > 1:
                    return 1
            return current_streak
        except Exception:
            return current_streak

    @staticmethod
    def _record_study_session(session, workspace_id: str, activity_type: str, duration_seconds: float) -> None:
        try:
            from app.infrastructure.db.models import StudySessionTable
            session.add(
                StudySessionTable(
                    id=f"session_{uuid.uuid4().hex[:12]}",
                    workspace_id=workspace_id,
                    activity_type=activity_type,
                    started_at=datetime.utcnow(),
                    ended_at=datetime.utcnow(),
                    duration_seconds=duration_seconds,
                )
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Query APIs
    # ------------------------------------------------------------------
    def get_workspace_analytics(self, workspace_id: str) -> Optional[dict]:
        if not engine or not Session:
            return None
        try:
            with Session(engine) as session:
                record = self._get_workspace_analytics(session, workspace_id)
                if not record:
                    return {
                        "workspace_id": workspace_id,
                        "total_media": 0,
                        "total_concepts": 0,
                        "total_flashcards": 0,
                        "total_quiz_attempts": 0,
                        "total_reviews": 0,
                        "avg_quiz_score": 0.0,
                        "total_study_seconds": 0.0,
                        "review_streak_days": 0,
                        "last_activity_at": None,
                    }
                return {
                    "workspace_id": record.workspace_id,
                    "total_media": record.total_media or 0,
                    "total_concepts": record.total_concepts or 0,
                    "total_flashcards": record.total_flashcards or 0,
                    "total_quiz_attempts": record.total_quiz_attempts or 0,
                    "total_reviews": record.total_reviews or 0,
                    "avg_quiz_score": round(record.avg_quiz_score or 0.0, 2),
                    "total_study_seconds": round(record.total_study_seconds or 0.0, 1),
                    "review_streak_days": record.review_streak_days or 0,
                    "last_activity_at": record.last_activity_at.isoformat() if record.last_activity_at else None,
                }
        except Exception:
            return None

    def get_concept_mastery(self, workspace_id: str) -> List[dict]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import ConceptMasteryTable
            with Session(engine) as session:
                stmt = select(ConceptMasteryTable).where(
                    ConceptMasteryTable.workspace_id == workspace_id
                )
                records = self._scalars(session, stmt)
                return [
                    {
                        "concept_id": r.concept_id,
                        "concept_name": r.concept_name,
                        "mastery_level": r.mastery_level or 0.0,
                        "review_count": r.review_count or 0,
                        "quiz_correct": r.quiz_correct or 0,
                        "quiz_attempts": r.quiz_attempts or 0,
                        "last_reviewed_at": r.last_reviewed_at.isoformat() if r.last_reviewed_at else None,
                    }
                    for r in records
                ]
        except Exception:
            return []

    def get_recent_activity(self, workspace_id: str, limit: int = 10) -> List[dict]:
        if not engine or not Session or not select:
            return []
        try:
            from app.infrastructure.db.models import StudySessionTable
            with Session(engine) as session:
                stmt = (
                    select(StudySessionTable)
                    .where(StudySessionTable.workspace_id == workspace_id)
                    .order_by(StudySessionTable.created_at.desc())
                    .limit(limit)
                )
                records = self._scalars(session, stmt)
                return [
                    {
                        "id": r.id,
                        "activity_type": r.activity_type,
                        "duration_seconds": r.duration_seconds or 0.0,
                        "created_at": r.created_at.isoformat() if r.created_at else None,
                    }
                    for r in records
                ]
        except Exception:
            return []

    def recommend_revisions(self, workspace_id: str, limit: int = 8) -> List[dict]:
        """Prioritized revision list: low-mastery concepts + due flashcards."""
        mastery = self.get_concept_mastery(workspace_id)
        by_id = {m["concept_id"]: m for m in mastery}
        recommendations: List[dict] = []

        try:
            due_cards = self.flashcard_service.due_cards(workspace_id, limit=limit * 2)
        except Exception:
            due_cards = []
        for card in due_cards[:limit]:
            concept_mastery = by_id.get(card.concept_id, {})
            recommendations.append(
                {
                    "type": "flashcard",
                    "card_id": card.id,
                    "title": card.front,
                    "concept_id": card.concept_id,
                    "concept_name": card.concept_name or concept_mastery.get("concept_name"),
                    "due_in_days": 0,
                    "mastery_level": concept_mastery.get("mastery_level", 0.0),
                    "priority": "high" if (concept_mastery.get("mastery_level", 0.0) or 0.0) < 0.5 else "medium",
                }
            )

        # Low-mastery concepts not already covered by a due card.
        covered_concepts = {r.get("concept_id") for r in recommendations}
        for m in sorted(mastery, key=lambda x: x["mastery_level"]):
            if len(recommendations) >= limit:
                break
            if m["concept_id"] in covered_concepts:
                continue
            if (m["mastery_level"] or 0.0) < 0.6:
                recommendations.append(
                    {
                        "type": "concept",
                        "card_id": None,
                        "title": m["concept_name"],
                        "concept_id": m["concept_id"],
                        "concept_name": m["concept_name"],
                        "due_in_days": 0,
                        "mastery_level": m["mastery_level"],
                        "priority": "high" if (m["mastery_level"] or 0.0) < 0.35 else "medium",
                    }
                )
        return recommendations[:limit]
