import json
from typing import List, Optional, Tuple

from app.domain.ai.capabilities import TextGenerationRequest
from app.domain.ai.service_bus import AIServiceBus
from app.domain.knowledge.concept_merging import ConceptMergingService
from app.domain.knowledge.entities import RelationType
from app.domain.knowledge.graph_extraction import (
    ExtractedConcept,
    ExtractedRelation,
    build_extraction_prompt,
    extract_concepts_heuristic,
    parse_llm_extraction,
)
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import engine
from app.infrastructure.events.event_bus import EventBus, DomainEvent

try:
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


class GraphExtractionWorker:
    """Event-driven knowledge graph extraction pipeline.

    Listens to ``ChunksIndexedEvent``, extracts domain concepts and directional
    relationships using AIServiceBus LLM capabilities, passes candidates through
    the incremental ConceptMergingService, and emits artifact lifecycle updates
    (``pending`` -> ``generating`` -> ``ready`` / ``failed``).
    """

    def __init__(
        self,
        event_bus: EventBus,
        ai_service_bus: AIServiceBus,
        graph_service: KnowledgeGraphService,
        merging_service: Optional[ConceptMergingService] = None,
    ) -> None:
        self.event_bus = event_bus
        self.ai_service_bus = ai_service_bus
        self.graph_service = graph_service
        self.merging_service = merging_service or ConceptMergingService(
            embedding_capability=self._get_embedding_capability()
        )
        self.event_bus.subscribe("ChunksIndexedEvent", self.handle_chunks_indexed)

    def _get_embedding_capability(self):
        try:
            return self.ai_service_bus.get_embedding_capability()
        except Exception:
            return None

    def _update_job(
        self,
        media_id: str,
        workspace_id: str,
        status: str,
        progress: int,
        message: Optional[str] = None,
        error: Optional[str] = None,
    ) -> None:
        self.graph_service.upsert_artifact_job(
            job_id=f"graph_{media_id}",
            workspace_id=workspace_id,
            artifact_type="graph",
            target_key=media_id,
            status=status,
            progress=progress,
            message=message,
            error_message=error,
        )

    async def _extract_with_llm(
        self, chunks: List[dict]
    ) -> Tuple[List[ExtractedConcept], List[ExtractedRelation]]:
        try:
            text_capability = self.ai_service_bus.get_text_capability()
        except Exception:
            return [], []
        try:
            gen_res = await text_capability.generate(
                TextGenerationRequest(
                    prompt=build_extraction_prompt(chunks),
                    temperature=0.1,
                    max_tokens=2048,
                )
            )
        except Exception:
            return [], []
        parsed = parse_llm_extraction(gen_res.text)
        if parsed is None:
            return [], []
        return parsed

    async def handle_chunks_indexed(self, event: DomainEvent) -> None:
        media_id = event.aggregate_id
        workspace_id = event.payload.get("workspace_id", "default")

        self._update_job(
            media_id, workspace_id, "generating", 15,
            message="Extracting domain concepts from transcript chunks...",
        )

        try:
            chunks = load_chunks(media_id, workspace_id)
            if not chunks:
                self._update_job(
                    media_id, workspace_id, "ready", 100,
                    message="No transcript chunks available for graph extraction.",
                )
                return

            self._update_job(media_id, workspace_id, "generating", 35, message="Running LLM concept extraction...")
            concepts, relations = await self._extract_with_llm(chunks)
            if not concepts:
                self._update_job(media_id, workspace_id, "generating", 55, message="LLM extraction unavailable; using deterministic heuristic extraction...")
                concepts, relations = extract_concepts_heuristic(chunks)

            if not concepts:
                self._update_job(
                    media_id, workspace_id, "failed", 0,
                    message="No concepts could be extracted.", error="Empty extraction result.",
                )
                return

            self._update_job(media_id, workspace_id, "generating", 70, message="Merging candidate concepts into canonical knowledge graph...")
            resolved_ids: dict = {}
            for concept in concepts:
                canonical_id, _ = await self.merging_service.resolve_concept(
                    workspace_id=workspace_id,
                    name=concept.name,
                    description=concept.description,
                    media_id=media_id,
                    source_chunk_ids=concept.source_chunk_ids or [c["id"] for c in chunks],
                    start_time=concept.start_time or (chunks[0].get("start_time", 0.0) if chunks else 0.0),
                    end_time=concept.end_time or (chunks[-1].get("end_time", 0.0) if chunks else 0.0),
                )
                resolved_ids[concept.name.lower()] = canonical_id

            relation_count = 0
            for rel in relations:
                source_id = resolved_ids.get(rel.source.lower())
                target_id = resolved_ids.get(rel.target.lower())
                if not source_id or not target_id or source_id == target_id:
                    continue
                try:
                    rel_enum = RelationType(rel.relation_type)
                except (ValueError, TypeError):
                    rel_enum = RelationType.RELATED_TO
                self.graph_service.add_relation(
                    source_id=source_id,
                    target_id=target_id,
                    relation_type=rel_enum,
                    weight=rel.weight,
                    workspace_id=workspace_id,
                    media_id=media_id,
                )
                relation_count += 1

            self._update_job(
                media_id, workspace_id, "ready", 100,
                message=f"Knowledge graph updated: {len(resolved_ids)} canonical concepts, {relation_count} relations.",
            )

            await self.event_bus.publish(DomainEvent(
                event_type="ConceptGraphUpdatedEvent",
                aggregate_id=workspace_id,
                payload={
                    "workspace_id": workspace_id,
                    "media_id": media_id,
                    "concept_count": len(resolved_ids),
                    "relation_count": relation_count,
                },
            ))
        except Exception as e:
            err_msg = str(e).strip() or repr(e)
            self._update_job(
                media_id, workspace_id, "failed", 0,
                message="Knowledge graph extraction failed.", error=err_msg,
            )
