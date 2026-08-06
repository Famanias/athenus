import json
from typing import Optional
from app.domain.learning.flashcard_service import FlashcardService
from app.domain.learning.quiz_service import QuizService
from app.infrastructure.events.event_bus import EventBus, DomainEvent
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


class LearningEvolutionWorker:
    """Worker automatically evolving workspace Flashcard decks and Quizzes when new concepts are merged into the Knowledge Graph."""

    def __init__(
        self,
        event_bus: EventBus,
        flashcard_service: Optional[FlashcardService] = None,
        quiz_service: Optional[QuizService] = None,
    ) -> None:
        self.event_bus = event_bus
        self.flashcard_service = flashcard_service or FlashcardService(event_bus=event_bus)
        self.quiz_service = quiz_service or QuizService(event_bus=event_bus)

        # Subscribe to ConceptGraphUpdatedEvent
        self.event_bus.subscribe("ConceptGraphUpdatedEvent", self.handle_concept_graph_updated)

    async def handle_concept_graph_updated(self, event: DomainEvent) -> None:
        workspace_id = event.payload.get("workspace_id", "default")
        new_concept_ids = event.payload.get("new_concept_ids", [])

        # Skip auto-evolution if no new concepts were merged (e.g. duplicate video upload)
        if not new_concept_ids:
            return

        settings = self._get_workspace_settings(workspace_id)
        auto_evolve_flashcards = settings.get("auto_evolve_flashcards", True)
        flashcard_budget = settings.get("flashcard_target_budget_per_media", 20)
        auto_evolve_quizzes = settings.get("auto_evolve_quizzes", True)
        quiz_budget = settings.get("quiz_target_budget_per_media", 15)

        # Evolve Flashcard Deck
        if auto_evolve_flashcards:
            try:
                evolved_deck = await self.flashcard_service.evolve_workspace_deck(
                    workspace_id=workspace_id,
                    new_concept_ids=new_concept_ids,
                    target_budget=flashcard_budget,
                )
                if evolved_deck:
                    await self.event_bus.publish(DomainEvent(
                        event_type="DeckEvolvedEvent",
                        aggregate_id=workspace_id,
                        payload={
                            "workspace_id": workspace_id,
                            "deck_id": evolved_deck.id,
                            "version": evolved_deck.version,
                            "card_count": evolved_deck.card_count,
                        }
                    ))
            except Exception as e:
                pass

        # Evolve Quiz
        if auto_evolve_quizzes:
            try:
                evolved_quiz = await self.quiz_service.evolve_workspace_quiz(
                    workspace_id=workspace_id,
                    new_concept_ids=new_concept_ids,
                    target_budget=quiz_budget,
                )
                if evolved_quiz:
                    await self.event_bus.publish(DomainEvent(
                        event_type="QuizEvolvedEvent",
                        aggregate_id=workspace_id,
                        payload={
                            "workspace_id": workspace_id,
                            "quiz_id": evolved_quiz.id,
                            "version": evolved_quiz.version,
                            "question_count": evolved_quiz.question_count,
                        }
                    ))
            except Exception as e:
                pass

    def _get_workspace_settings(self, workspace_id: str) -> dict:
        if not engine or not Session:
            return {}
        try:
            from app.infrastructure.db.models import WorkspaceTable
            with Session(engine) as session:
                ws = session.get(WorkspaceTable, workspace_id)
                if ws and ws.settings_json:
                    return json.loads(ws.settings_json)
        except Exception:
            pass
        return {}
