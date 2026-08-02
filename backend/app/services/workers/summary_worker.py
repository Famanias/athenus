from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.events.event_bus import EventBus, DomainEvent

class SummaryWorker:
    """Worker constructing video summaries and chapter outlines."""
    
    def __init__(self, event_bus: EventBus, ai_service_bus: AIServiceBus) -> None:
        self.event_bus = event_bus
        self.ai_service_bus = ai_service_bus
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")

        text_capability = self.ai_service_bus.get_text_capability()
        gen_res = await text_capability.generate(TextGenerationRequest(
            prompt=f"Generate a bulleted summary and chapter outline for media ID {media_id}."
        ))

        await self.event_bus.publish(DomainEvent(
            event_type="SummaryGeneratedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "workspace_id": workspace_id, "summary_text": gen_res.text}
        ))
