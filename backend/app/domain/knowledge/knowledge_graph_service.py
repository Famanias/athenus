import uuid
import hashlib
import json
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
from app.domain.common.cache_interface import ICacheStore
from app.infrastructure.cache.memory_cache import MemoryCacheAdapter

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class KnowledgeGraphService(KnowledgeGraphProtocol):
    """SQLite-backed Knowledge Graph Service implementing concept graph traversal,
    persistence, provenance-grounded canonical node storage, and artifact lifecycle
    observability."""

    CACHE_TTL_SECONDS = 600

    def __init__(self, cache_store: Optional[ICacheStore] = None) -> None:
        self._nodes: Dict[str, ConceptNode] = {}
        self._edges: List[ConceptRelation] = []
        self._cache = cache_store if cache_store is not None else MemoryCacheAdapter(maxsize=500)

    def invalidate_workspace(self, workspace_id: str) -> int:
        return self._cache.delete_prefix(f"kg:ws:{workspace_id}:")

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
        self.invalidate_workspace(workspace_id)

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
        self.invalidate_workspace(workspace_id)

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
            self.invalidate_workspace(workspace_id)
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
        self.invalidate_workspace(workspace_id)

    # ------------------------------------------------------------------
    # Retrieval (DB-backed with in-memory fallback)
    # ------------------------------------------------------------------
    def get_concepts(self, workspace_id: str = "default") -> List[ConceptNode]:
        cache_key = f"kg:ws:{workspace_id}:topology:nodes"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return list(cached)
        result: List[ConceptNode] = []
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
                        result = [self._concept_from_db(r) for r in records]
            except Exception:
                pass
        if not result:
            result = [n for n in self._nodes.values() if n.workspace_id == workspace_id]
        self._cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL_SECONDS)
        return list(result)

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
        cache_key = f"kg:ws:{workspace_id}:topology:relations"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return list(cached)
        result: List[ConceptRelation] = []
        if engine and Session and select:
            try:
                with Session(engine) as session:
                    stmt = select(KnowledgeRelationTable).where(
                        KnowledgeRelationTable.workspace_id == workspace_id
                    )
                    records = self._scalars(session, stmt)
                    if records:
                        result = [
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
        if not result:
            result = [e for e in self._edges if e.source_concept_id in self._nodes or e.target_concept_id in self._nodes]
        self._cache.set(cache_key, result, ttl_seconds=self.CACHE_TTL_SECONDS)
        return list(result)

    @staticmethod
    def _concept_from_db(rec) -> ConceptNode:
        raw_chunk_ids = rec.source_chunk_ids or ""
        try:
            parsed = json.loads(raw_chunk_ids)
            chunk_ids = list(parsed) if isinstance(parsed, list) else []
        except (TypeError, json.JSONDecodeError):
            chunk_ids = [c for c in raw_chunk_ids.split(",") if c]
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
        adjacency = self._get_adjacency(workspace_id)
        concept_map = {node.id: node for node in self.get_concepts(workspace_id)}

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
            nodes_at_depth = [concept_map[nid] for nid in next_frontier if nid in concept_map]
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
        adjacency = self._get_adjacency(workspace_id)

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

    def _get_adjacency(self, workspace_id: str) -> Dict[str, List[str]]:
        cache_key = f"kg:ws:{workspace_id}:adjacency"
        cached = self._cache.get(cache_key)
        if isinstance(cached, dict):
            return {str(key): list(value) for key, value in cached.items()}
        adjacency: Dict[str, List[str]] = {}
        for edge in self.get_relations(workspace_id):
            adjacency.setdefault(edge.source_concept_id, []).append(edge.target_concept_id)
            adjacency.setdefault(edge.target_concept_id, []).append(edge.source_concept_id)
        self._cache.set(cache_key, adjacency, ttl_seconds=self.CACHE_TTL_SECONDS)
        return adjacency

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
    def get_workspace_triples(
        self,
        workspace_id: str = "default",
        query: Optional[str] = None
    ) -> List[str]:
        """Retrieve structured text representation of knowledge triples for RAG prompt context expansion.
        Enforces Zero-Match Guardrail and query relevance filtering when query is provided."""
        normalized_query = " ".join((query or "").lower().split())
        query_digest = hashlib.sha256(normalized_query.encode("utf-8")).hexdigest()
        cache_key = f"kg:ws:{workspace_id}:triples:{query_digest}"
        cached = self._cache.get(cache_key)
        if isinstance(cached, list):
            return list(cached)

        stop_words = {
            "a", "an", "the", "and", "or", "but", "if", "because", "as", "what", "which",
            "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was",
            "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
            "did", "doing", "can", "could", "should", "would", "may", "might", "must",
            "shall", "tell", "give", "me", "summarize", "summary", "explain", "about",
            "file", "attached", "document", "pdf", "video", "please", "hi", "hello", "hey"
        }

        query_tokens: Set[str] = set()
        if query:
            clean_q = "".join([c.lower() if c.isalnum() or c.isspace() else " " for c in query])
            query_tokens = {t for t in clean_q.split() if t not in stop_words and len(t) > 1}

        relevant_concept_ids: Set[str] = set()
        if query is not None:
            if not query_tokens:
                # Zero-match guardrail: Empty/generic query -> 0 triples
                self._cache.set(cache_key, [], ttl_seconds=self.CACHE_TTL_SECONDS)
                return []

            concepts = self.get_concepts(workspace_id)
            for c in concepts:
                c_name_tokens = set("".join([ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in c.name]).split())
                c_desc_tokens = set("".join([ch.lower() if ch.isalnum() or ch.isspace() else " " for ch in (c.description or "")]).split())

                if query_tokens & c_name_tokens or query_tokens & c_desc_tokens or any(qt in c.name.lower() for qt in query_tokens):
                    relevant_concept_ids.add(c.id)
                    relevant_concept_ids.add(c.name.lower())

            if not relevant_concept_ids:
                # Zero-match guardrail: No concepts matched query
                self._cache.set(cache_key, [], ttl_seconds=self.CACHE_TTL_SECONDS)
                return []

        relations = self.get_relations(workspace_id)
        filtered_triples: List[str] = []

        for r in relations:
            src = r.source_concept_id
            tgt = r.target_concept_id
            rel = r.relation_type.value if hasattr(r.relation_type, "value") else str(r.relation_type)

            if query is not None:
                is_rel = (
                    src in relevant_concept_ids
                    or tgt in relevant_concept_ids
                    or src.lower() in relevant_concept_ids
                    or tgt.lower() in relevant_concept_ids
                    or any(qt in src.lower() for qt in query_tokens)
                    or any(qt in tgt.lower() for qt in query_tokens)
                )
                if not is_rel:
                    continue

            filtered_triples.append(f"{src} --[{rel}]--> {tgt}")

        self._cache.set(cache_key, filtered_triples, ttl_seconds=self.CACHE_TTL_SECONDS)
        return list(filtered_triples)

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
