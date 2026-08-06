import json
import math
import re
import uuid
from datetime import datetime
from typing import List, Optional, Tuple

from app.domain.ai.capabilities import IEmbeddingCapability
from app.infrastructure.db.models import ConceptAliasTable, KnowledgeConceptTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    if not vec_a or not vec_b:
        return 0.0
    if len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


class ConceptMergingService:
    """Incremental hybrid concept deduplication engine.

    Resolves candidate concept names against canonical workspace concepts using:
      1. Exact normalized-name matching.
      2. Alias-table lookup (ConceptAliasTable).
      3. Semantic embedding distance (bge-small-en-v1.5 via AIServiceBus capability).

    Duplicates are merged into the canonical concept while preserving accumulated
    provenance (media_id, source_chunk_ids, start_time/end_time windows).
    """

    SEMANTIC_THRESHOLD = 0.88

    def __init__(self, embedding_capability: Optional[IEmbeddingCapability] = None) -> None:
        self.embedding_capability = embedding_capability

    # ------------------------------------------------------------------
    # Name normalization
    # ------------------------------------------------------------------
    def normalize_name(self, name: str) -> str:
        text = (name or "").lower().strip()
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^a-z0-9\s]", "", text)
        return text.strip()

    def _parse_json(self, raw: Optional[str]) -> List[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            return list(parsed) if isinstance(parsed, list) else []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------
    def _scalars(self, session, statement):
        if hasattr(session, "scalars"):
            return session.scalars(statement).all()
        return session.exec(statement).all()

    def find_by_normalized(self, workspace_id: str, normalized: str) -> Optional[KnowledgeConceptTable]:
        if not engine or not Session or not select:
            return None
        with Session(engine) as session:
            stmt = (
                select(ConceptAliasTable)
                .where(ConceptAliasTable.workspace_id == workspace_id)
                .where(ConceptAliasTable.normalized == normalized)
            )
            alias_records = self._scalars(session, stmt)
            if not alias_records:
                return None
            concept = session.get(KnowledgeConceptTable, alias_records[0].concept_id)
            return concept

    def find_by_alias(self, workspace_id: str, alias: str) -> Optional[KnowledgeConceptTable]:
        return self.find_by_normalized(workspace_id, self.normalize_name(alias))

    def find_by_id(self, concept_id: str) -> Optional[KnowledgeConceptTable]:
        if not engine or not Session:
            return None
        with Session(engine) as session:
            return session.get(KnowledgeConceptTable, concept_id)

    def list_concepts(self, workspace_id: str) -> List[KnowledgeConceptTable]:
        if not engine or not Session or not select:
            return []
        with Session(engine) as session:
            stmt = (
                select(KnowledgeConceptTable)
                .where(KnowledgeConceptTable.workspace_id == workspace_id)
                .order_by(KnowledgeConceptTable.name)
            )
            return self._scalars(session, stmt)

    async def _find_semantic_match(
        self, workspace_id: str, name: str
    ) -> Optional[KnowledgeConceptTable]:
        if not self.embedding_capability:
            return None
        try:
            query_vec = await self.embedding_capability.embed_query(name)
        except Exception:
            return None

        best_concept: Optional[KnowledgeConceptTable] = None
        best_score = 0.0
        for concept in self.list_concepts(workspace_id):
            if not concept.embedding:
                continue
            try:
                stored = json.loads(concept.embedding)
            except Exception:
                continue
            score = cosine_similarity(query_vec, stored)
            if score > best_score:
                best_concept = concept
                best_score = score
        if best_concept and best_score >= self.SEMANTIC_THRESHOLD:
            return best_concept
        return None

    async def _embed(self, text: str) -> Optional[List[float]]:
        if not self.embedding_capability:
            return None
        try:
            return await self.embedding_capability.embed_query(text)
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Canonical resolution
    # ------------------------------------------------------------------
    async def resolve_concept(
        self,
        workspace_id: str,
        name: str,
        description: str = "",
        media_id: Optional[str] = None,
        source_chunk_ids: Optional[List[str]] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
    ) -> Tuple[str, bool]:
        """Return (canonical_concept_id, is_new_concept) for the candidate name.

        Merges into an existing canonical concept when an exact, alias, or
        semantic match is found, otherwise persists a brand new concept node.
        """
        normalized = self.normalize_name(name)
        if not normalized:
            normalized = self.normalize_name(f"concept {media_id or 'unknown'}")

        existing = self.find_by_normalized(workspace_id, normalized)
        if existing:
            self._merge_into(
                existing, name, media_id, source_chunk_ids, start_time, end_time
            )
            return existing.id, False

        alias_concept = self.find_by_alias(workspace_id, name)
        if alias_concept:
            self._merge_into(
                alias_concept, name, media_id, source_chunk_ids, start_time, end_time
            )
            return alias_concept.id, False

        semantic_match = await self._find_semantic_match(workspace_id, name)
        if semantic_match:
            self._merge_into(
                semantic_match, name, media_id, source_chunk_ids, start_time, end_time
            )
            return semantic_match.id, False

        new_id = f"concept_{uuid.uuid4().hex[:10]}"
        embedding = await self._embed(name)
        self._create_concept(
            concept_id=new_id,
            workspace_id=workspace_id,
            name=name,
            description=description,
            media_id=media_id,
            source_chunk_ids=source_chunk_ids,
            start_time=start_time,
            end_time=end_time,
            embedding=embedding,
            normalized=normalized,
        )
        return new_id, True

    def _create_concept(
        self,
        concept_id: str,
        workspace_id: str,
        name: str,
        description: str,
        media_id: Optional[str],
        source_chunk_ids: Optional[List[str]],
        start_time: Optional[float],
        end_time: Optional[float],
        embedding: Optional[List[float]],
        normalized: str,
    ) -> None:
        if not engine or not Session:
            return
        with Session(engine) as session:
            concept = KnowledgeConceptTable(
                id=concept_id,
                workspace_id=workspace_id,
                name=name,
                description=description,
                status="ready",
                media_id=media_id,
                source_chunk_ids=json.dumps(list(source_chunk_ids or [])),
                start_time=start_time,
                end_time=end_time,
                embedding=json.dumps(embedding) if embedding else None,
            )
            session.add(concept)
            session.add(
                ConceptAliasTable(
                    id=f"alias_{uuid.uuid4().hex[:10]}",
                    workspace_id=workspace_id,
                    concept_id=concept_id,
                    alias=name,
                    normalized=normalized,
                )
            )
            session.commit()

    def _merge_into(
        self,
        concept: KnowledgeConceptTable,
        new_name: str,
        media_id: Optional[str],
        source_chunk_ids: Optional[List[str]],
        start_time: Optional[float],
        end_time: Optional[float],
    ) -> None:
        if not engine or not Session:
            return
        with Session(engine) as session:
            db = session.get(KnowledgeConceptTable, concept.id)
            if not db:
                return

            merged_chunks = set(self._parse_json(db.source_chunk_ids))
            merged_chunks.update(list(source_chunk_ids or []))
            db.source_chunk_ids = json.dumps(sorted(merged_chunks)) if merged_chunks else None

            if media_id:
                db.media_id = media_id
            if start_time is not None:
                existing_start = db.start_time if db.start_time is not None else start_time
                db.start_time = min(existing_start, start_time)
            if end_time is not None:
                existing_end = db.end_time if db.end_time is not None else end_time
                db.end_time = max(existing_end, end_time)
            db.updated_at = datetime.utcnow()

            # Register the new surface name as an alias for future incremental merges
            normalized = self.normalize_name(new_name)
            if normalized:
                alias_stmt = (
                    select(ConceptAliasTable)
                    .where(ConceptAliasTable.concept_id == db.id)
                    .where(ConceptAliasTable.normalized == normalized)
                )
                existing_aliases = self._scalars(session, alias_stmt)
                if not existing_aliases:
                    session.add(
                        ConceptAliasTable(
                            id=f"alias_{uuid.uuid4().hex[:10]}",
                            workspace_id=db.workspace_id,
                            concept_id=db.id,
                            alias=new_name,
                            normalized=normalized,
                        )
                    )
            session.commit()
