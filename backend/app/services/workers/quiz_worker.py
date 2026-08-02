from typing import List
import uuid
from app.domain.learning.entities import Quiz, QuizQuestion
from app.infrastructure.events.event_bus import EventBus, DomainEvent

class QuizWorker:
    """Worker generating interactive comprehension quizzes."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")

        quiz = Quiz(
            id=f"quiz_{uuid.uuid4().hex[:8]}",
            workspace_id=workspace_id,
            title=f"Comprehension Quiz for {media_id}",
            questions=[
                QuizQuestion(
                    id="q1",
                    question_text="What is the core principle of Local-First AI architectures?",
                    options=["Cloud dependency", "Data privacy and offline execution", "High latency", "Centralized hosting"],
                    correct_option_index=1,
                    explanation="Local-first architectures prioritize running models and databases locally to preserve privacy and function offline."
                )
            ]
        )

        await self.event_bus.publish(DomainEvent(
            event_type="QuizGeneratedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "quiz_id": quiz.id, "question_count": len(quiz.questions)}
        ))
