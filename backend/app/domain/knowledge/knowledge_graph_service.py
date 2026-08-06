import uuid
from collections import deque
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from app.domain.knowledge.entities import ConceptNode, ConceptRelation, RelationType, KnowledgeGraphProtocol
from app.infrastructure.db.models import (
    ArtifactJobTable,
    KnowledgeConceptTable,
    KnowledgeRelationTable,
)
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class KnowledgeGraphService(KnowledgeGraphProtocol):
    """SQLite-backed Knowledge Graph Service implementing concept graph traversal,
    persistence, provenance-grounded canonical node storage, and artifact lifecycle
    observability."""

    def __init__(self) -> None:
        self._nodes: Dict[str, ConceptNode] = {}
        self._edges: List[ConceptRelation] = []

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    @staticmethod
    def _relation_to_str(relation) -> str:
        return relation.value if isinstance(relation, RelationType) else str(relation)

    @staticmethod
    def _relation_from_str(relation_type: str) -> RelationType:
        try:
            return RelationType(relation_type)
        except (ValueError, TypeError):
            return RelationType.RELATED_TO

    # ------------------------------------------------------------------
    # Node & edge storage
    # ------------------------------------------------------------------
    def add_node(self, node: ConceptNode, workspace_id: str = "default") -> None:
        self._nodes[node.id] = node

        if engine and Session:
            try:
                with Session(engine) as session:
                    db_concept = session.get(KnowledgeConceptTable, node.id)
                    if not db_concept:
                        db_concept = KnowledgeConceptTable(
                            id=node.id,
                            workspace_id=workspace_id,
                            name=node.name,
                            description=node.description,
                            status=node.status,
                            media_id=node.media_id,
                            source_chunk_ids=(
                                ",".join(node.source_chunk_ids)
                                if node.source_chunk_ids
                                else None
                            ),
                            start_time=node.start_time,
                            end_time=node.end_time,
                        )
                        session.add(db_concept)
                        session.commit()
            except Exception:
                pass

    def add_concept(self, concept: ConceptNode) -> None:
        """Canonical, provenance-grounded concept insert/update (idempotent)."""
        self.add_node(concept, workspace_id=concept.workspace_id)

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0,
        workspace_id: str = "default",
        media_id: Optional[str] = None,
    ) -> None:
        edge_id = f"edge_{source_id}_{target_id}"
        self._edges.append(
            ConceptRelation(
                id=edge_id,
                source_concept_id=source_id,
                target_concept_id=target_id,
                relation_type=relation,
                weight=weight,
                media_id=media_id,
            )
        )

        if engine and Session:
            try:
                rel_str = self._relation_to_str(relation)
                with Session(engine) as session:
                    db_rel = session.get(KnowledgeRelationTable, edge_id)
                    if not db_rel:
                        db_rel = KnowledgeRelationTable(
                            id=edge_id,
                            workspace_id=workspace_id,
                            source_concept=source_id,
                            target_concept=target_id,
                            relation_type=rel_str,
                            weight=weight,
                            media_id=media_id,
                        )
                        session.add(db_rel)
                        session.commit()
            except Exception:
                pass

    def add_relation(
        self,
        source_id: str,
        target_id: str,
        relation_type: RelationType,
        weight: float = 1.0,
        workspace_id: str = "default",
        media_id: Optional[str] = None,
    ) -> None:
        """Canonical directional relation insert (deduplicated by source/target pair)."""
        if source_id == target_id:
            return
        edge_id = f"edge_{source_id}_{target_id}"
        rel_str = self._relation_to_str(relation_type)

        relation = ConceptRelation(
            id=edge_id,
            source_concept_id=source_id,
            target_concept_id=target_id,
            relation_type=relation_type,
            weight=weight,
            media_id=media_id,
        )
        # Keep in-memory graph in sync
        existing_in_memory = [e for e in self._edges if e.id == edge_id]
        if existing_in_memory:
            existing_in_memory[0].weight = weight
            existing_in_memory[0].media_id = media_id
        else:
            self._edges.append(relation)

        if not engine or not Session:
            return
        try:
            with Session(engine) as session:
                db_rel = session.get(KnowledgeRelationTable, edge_id)
                if db_rel:
                    db_rel.relation_type = rel_str
                    db_rel.weight = weight
                    db_rel.media_id = media_id
                    db_rel.updated_at = datetime.utcnow()
                else:
                    db_rel = KnowledgeRelationTable(
                        id=edge_id,
                        workspace_id=workspace_id,
                        source_concept=source_id,
                        target_concept=target_id,
                        relation_type=rel_str,
                        weight=weight,
                        media_id=media_id,
                    )
                    session.add(db_rel)
                session.commit()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Retrieval (DB-backed with in-memory fallback)
    # ------------------------------------------------------------------
    def get_concepts(self, workspace_id: str = "default") -> List[ConceptNode]:
        if engine and Session and select:
            try:
                with Session(engine) as session:
                    stmt = (
                        select(KnowledgeConceptTable)
                        .where(KnowledgeConceptTable.workspace_id == workspace_id)
                        .order_by(KnowledgeConceptTable.name)
                    )
                    records = self._scalars(session, stmt)
                    if records:
                        return [self._concept_from_db(r) for r in records]
            except Exception:
                pass
        return [n for n in self._nodes.values() if n.workspace_id == workspace_id]

    def get_concept(self, concept_id: str) -> Optional[ConceptNode]:
        if engine and Session:
            try:
                with Session(engine) as session:
                    rec = session.get(KnowledgeConceptTable, concept_id)
                    if rec:
                        return self._concept_from_db(rec)
            except Exception:
                pass
        return self._nodes.get(concept_id)

    def get_relations(self, workspace_id: str = "default") -> List[ConceptRelation]:
        if engine and Session and select:
            try:
                with Session(engine) as session:
                    stmt = select(KnowledgeRelationTable).where(
                        KnowledgeRelationTable.workspace_id == workspace_id
                    )
                    records = self._scalars(session, stmt)
                    if records:
                        return [
                            ConceptRelation(
                                id=r.id,
                                source_concept_id=r.source_concept,
                                target_concept_id=r.target_concept,
                                relation_type=self._relation_from_str(r.relation_type),
                                weight=getattr(r, "weight", 1.0) or 1.0,
                                media_id=getattr(r, "media_id", None),
                            )
                            for r in records
                        ]
            except Exception:
                pass
        return [e for e in self._edges if e.source_concept_id in self._nodes or e.target_concept_id in self._nodes]

    @staticmethod
    def _concept_from_db(rec) -> ConceptNode:
        chunk_ids = [c for c in (rec.source_chunk_ids or "").split(",") if c]
        return ConceptNode(
            id=rec.id,
            workspace_id=rec.workspace_id,
            name=rec.name,
            description=rec.description or "",
            source_chunk_ids=chunk_ids,
            status=getattr(rec, "status", "ready") or "ready",
            media_id=getattr(rec, "media_id", None),
            start_time=getattr(rec, "start_time", None),
            end_time=getattr(rec, "end_time", None),
        )

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------
    def _edges_for(self, concept_id: str) -> List[ConceptRelation]:
        """Prefer the in-memory edge set (fast path used by traversal tests),
        falling back to DB-backed workspace edges for fresh service instances."""
        if self._edges:
            return self._edges
        workspace = self._workspace_of_concept(concept_id)
        return self.get_relations(workspace)

    def find_related(self, concept_id: str, max_depth: int = 2) -> List[ConceptNode]:
        related_ids: Set[str] = set()
        for edge in self._edges_for(concept_id):
            if edge.source_concept_id == concept_id:
                related_ids.add(edge.target_concept_id)
            elif edge.target_concept_id == concept_id:
                related_ids.add(edge.source_concept_id)
        return [self._nodes[nid] for nid in related_ids if nid in self._nodes]

    def recommend_prerequisites(self, target_concept_id: str) -> List[ConceptNode]:
        prereqs = []
        for edge in self._edges_for(target_concept_id):
            if (
                edge.target_concept_id == target_concept_id
                and edge.relation_type == RelationType.PREREQUISITE_FOR
            ):
                if edge.source_concept_id in self._nodes:
                    prereqs.append(self._nodes[edge.source_concept_id])
        return prereqs

    def get_neighbors(self, concept_id: str, max_depth: int = 2, workspace_id: str = "default") -> Dict[str, List[ConceptNode]]:
        """N-hop BFS traversal returning {depth: [concept nodes]}."""
        if max_depth < 1:
            max_depth = 1
        relations = self.get_relations(workspace_id)
        adjacency: Dict[str, List[str]] = {}
        for edge in relations:
            adjacency.setdefault(edge.source_concept_id, []).append(edge.target_concept_id)
            adjacency.setdefault(edge.target_concept_id, []).append(edge.source_concept_id)

        visited: Set[str] = {concept_id}
        frontier: List[str] = [concept_id]
        result: Dict[str, List[ConceptNode]] = {}
        for depth in range(1, max_depth + 1):
            next_frontier: List[str] = []
            for node_id in frontier:
                for neighbor in adjacency.get(node_id, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_frontier.append(neighbor)
            nodes_at_depth = [
                self.get_concept(nid) for nid in next_frontier if self.get_concept(nid)
            ]
            if nodes_at_depth:
                result[str(depth)] = nodes_at_depth
            frontier = next_frontier
            if not frontier:
                break
        return result

    def shortest_path(self, source_id: str, target_id: str, workspace_id: str = "default") -> List[str]:
        """BFS shortest path resolving prerequisite dependency chains."""
        if source_id == target_id:
            return [source_id]
        relations = self.get_relations(workspace_id)
        adjacency: Dict[str, List[str]] = {}
        for edge in relations:
            adjacency.setdefault(edge.source_concept_id, []).append(edge.target_concept_id)
            adjacency.setdefault(edge.target_concept_id, []).append(edge.source_concept_id)

        queue: deque = deque([source_id])
        parent: Dict[str, Optional[str]] = {source_id: None}
        while queue:
            current = queue.popleft()
            if current == target_id:
                break
            for neighbor in adjacency.get(current, []):
                if neighbor not in parent:
                    parent[neighbor] = current
                    queue.append(neighbor)

        if target_id not in parent:
            return []
        path: List[str] = []
        cursor: Optional[str] = target_id
        while cursor is not None:
            path.append(cursor)
            cursor = parent.get(cursor)
        path.reverse()
        return path

    def _workspace_of_concept(self, concept_id: str) -> str:
        node = self.get_concept(concept_id)
        if node:
            return node.workspace_id
        return "default"

    def _is_db_loaded(self) -> bool:
        return engine is not None and Session is not None

    # ------------------------------------------------------------------
    # RAG context expansion
    # ------------------------------------------------------------------
    def get_workspace_triples(self, workspace_id: str = "default") -> List[str]:
        """Retrieve structured text representation of knowledge triples for RAG prompt context expansion."""
        if not engine or not Session or not select:
            return [
                f"{e.source_concept_id} --[{e.relation_type.value if hasattr(e.relation_type, 'value') else e.relation_type}]--> {e.target_concept_id}"
                for e in self._edges
            ]

        try:
            with Session(engine) as session:
                statement = select(KnowledgeRelationTable).where(
                    KnowledgeRelationTable.workspace_id == workspace_id
                )
                records = self._scalars(session, statement)
                if not records and self._edges:
                    return [
                        f"{e.source_concept_id} --[{e.relation_type.value if hasattr(e.relation_type, 'value') else e.relation_type}]--> {e.target_concept_id}"
                        for e in self._edges
                    ]

                return [
                    f"{r.source_concept} --[{r.relation_type}]--> {r.target_concept}"
                    for r in records
                ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Artifact lifecycle observability
    # ------------------------------------------------------------------
    def upsert_artifact_job(
        self,
        job_id: str,
        workspace_id: str,
        artifact_type: str,
        target_key: str,
        status: str,
        stage: Optional[str] = None,
        progress: int = 0,
        message: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        if not engine or not Session:
            return
        try:
            with Session(engine) as session:
                job = session.get(ArtifactJobTable, job_id)
                if job:
                    job.status = status
                    if stage is not None:
                        job.stage = stage
                    job.progress = progress
                    job.message = message
                    job.error_message = error_message
                    job.updated_at = datetime.utcnow()
                else:
                    job = ArtifactJobTable(
                        id=job_id,
                        workspace_id=workspace_id,
                        artifact_type=artifact_type,
                        target_key=target_key,
                        status=status,
                        stage=stage,
                        progress=progress,
                        message=message,
                        error_message=error_message,
                    )
                    session.add(job)
                session.commit()
        except Exception:
            pass

    def get_artifact_job(self, workspace_id: str, artifact_type: str, target_key: Optional[str] = None) -> Optional[ArtifactJobTable]:
        if not engine or not Session or not select:
            return None
        try:
            with Session(engine) as session:
                stmt = select(ArtifactJobTable).where(
                    ArtifactJobTable.workspace_id == workspace_id,
                    ArtifactJobTable.artifact_type == artifact_type,
                )
                if target_key:
                    stmt = stmt.where(ArtifactJobTable.target_key == target_key)
                stmt = stmt.order_by(ArtifactJobTable.updated_at.desc())
                record = session.scalars(stmt).first() if hasattr(session, "scalars") else session.exec(stmt).first()
                return record
        except Exception:
            return None
