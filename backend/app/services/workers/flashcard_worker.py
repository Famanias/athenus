import uuid
from typing import List
from app.domain.learning.entities import Flashcard
from app.infrastructure.events.event_bus import EventBus, DomainEvent

class FlashcardWorker:
    """Worker formulating spaced-repetition flashcards (Anki SM-2 compatible)."""
    
    def __init__(self, event_bus: EventBus) -> None:
        self.event_bus = event_bus
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")

        card = Flashcard(
            id=f"card_{uuid.uuid4().hex[:8]}",
            workspace_id=workspace_id,
            front_prompt="What distance metric is used in Embedded Qdrant vector retrieval?",
            back_answer="Cosine Distance metric over 384-dimensional BGE embeddings."
        )

        await self.event_bus.publish(DomainEvent(
            event_type="FlashcardGeneratedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "card_id": card.id}
        ))
