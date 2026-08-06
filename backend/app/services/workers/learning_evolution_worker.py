from typing import Optional

from app.domain.analytics.analytics_service import AnalyticsService
from app.infrastructure.events.event_bus import EventBus, DomainEvent


class LearningEvolutionWorker:
    """Worker reacting to Knowledge Graph updates by refreshing precomputed
    workspace analytics ONLY.

    Flashcards and Quizzes are never generated automatically on ingestion;
    they are produced on-demand from their respective studio tabs.
    """

    def __init__(
        self,
        event_bus: EventBus,
        analytics_service: Optional[AnalyticsService] = None,
    ) -> None:
        self.event_bus = event_bus
        self.analytics_service = analytics_service or AnalyticsService()

        # Subscribe to ConceptGraphUpdatedEvent
        self.event_bus.subscribe("ConceptGraphUpdatedEvent", self.handle_concept_graph_updated)

    async def handle_concept_graph_updated(self, event: DomainEvent) -> None:
        workspace_id = event.payload.get("workspace_id", "default")
        new_concept_ids = event.payload.get("new_concept_ids", [])

        # Skip precomputation if no new concepts were merged (e.g. duplicate video upload)
        if not new_concept_ids:
            return

        # Update graph metrics and trigger AnalyticsService precomputation ONLY.
        try:
            await self.analytics_service.handle_graph_updated(event)
        except Exception:
            pass
