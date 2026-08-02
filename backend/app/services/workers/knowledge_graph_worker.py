from app.domain.knowledge.entities import ConceptNode, RelationType
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.events.event_bus import EventBus, DomainEvent

class KnowledgeGraphWorker:
    """Worker building Concept Graph linkages from indexed chunks."""
    
    def __init__(self, event_bus: EventBus, graph_service: KnowledgeGraphService) -> None:
        self.event_bus = event_bus
        self.graph_service = graph_service
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")

        node = ConceptNode(
            id=f"concept_{media_id}",
            workspace_id=workspace_id,
            name=f"Concept Topic for {media_id}",
            description="Extracted concept entity from transcript chunk indexing."
        )
        self.graph_service.add_node(node)

        await self.event_bus.publish(DomainEvent(
            event_type="ConceptGraphUpdatedEvent",
            aggregate_id=workspace_id,
            payload={"workspace_id": workspace_id, "concept_id": node.id}
        ))
