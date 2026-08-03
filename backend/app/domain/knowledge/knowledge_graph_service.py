import uuid
from typing import List, Dict, Optional
from app.domain.knowledge.entities import ConceptNode, ConceptRelation, RelationType, KnowledgeGraphProtocol
from app.infrastructure.db.models import KnowledgeConceptTable, KnowledgeRelationTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class KnowledgeGraphService(KnowledgeGraphProtocol):
    """SQLite-backed Knowledge Graph Service implementing Concept Graph traversal and storage."""
    
    def __init__(self) -> None:
        self._nodes: Dict[str, ConceptNode] = {}
        self._edges: List[ConceptRelation] = []

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
                            description=node.description
                        )
                        session.add(db_concept)
                        session.commit()
            except Exception:
                pass

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        relation: RelationType,
        weight: float = 1.0,
        workspace_id: str = "default"
    ) -> None:
        edge_id = f"edge_{source_id}_{target_id}"
        self._edges.append(ConceptRelation(
            id=edge_id,
            source_concept_id=source_id,
            target_concept_id=target_id,
            relation_type=relation,
            weight=weight
        ))

        if engine and Session:
            try:
                rel_str = relation.value if isinstance(relation, RelationType) else str(relation)
                with Session(engine) as session:
                    db_rel = session.get(KnowledgeRelationTable, edge_id)
                    if not db_rel:
                        db_rel = KnowledgeRelationTable(
                            id=edge_id,
                            workspace_id=workspace_id,
                            source_concept=source_id,
                            target_concept=target_id,
                            relation_type=rel_str
                        )
                        session.add(db_rel)
                        session.commit()
            except Exception:
                pass

    def find_related(self, concept_id: str, max_depth: int = 2) -> List[ConceptNode]:
        related_ids = set()
        for edge in self._edges:
            if edge.source_concept_id == concept_id:
                related_ids.add(edge.target_concept_id)
            elif edge.target_concept_id == concept_id:
                related_ids.add(edge.source_concept_id)

        return [self._nodes[nid] for nid in related_ids if nid in self._nodes]

    def recommend_prerequisites(self, target_concept_id: str) -> List[ConceptNode]:
        prereqs = []
        for edge in self._edges:
            if edge.target_concept_id == target_concept_id and edge.relation_type == RelationType.PREREQUISITE_FOR:
                if edge.source_concept_id in self._nodes:
                    prereqs.append(self._nodes[edge.source_concept_id])
        return prereqs

    def get_workspace_triples(self, workspace_id: str = "default") -> List[str]:
        """Retrieve structured text representation of knowledge triples for RAG prompt context expansion."""
        if not engine or not Session or not select:
            return [f"{e.source_concept_id} --[{e.relation_type.value if hasattr(e.relation_type, 'value') else e.relation_type}]--> {e.target_concept_id}" for e in self._edges]

        try:
            with Session(engine) as session:
                statement = select(KnowledgeRelationTable).where(KnowledgeRelationTable.workspace_id == workspace_id)
                records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
                if not records and self._edges:
                    return [f"{e.source_concept_id} --[{e.relation_type.value if hasattr(e.relation_type, 'value') else e.relation_type}]--> {e.target_concept_id}" for e in self._edges]
                
                return [
                    f"{r.source_concept} --[{r.relation_type}]--> {r.target_concept}"
                    for r in records
                ]
        except Exception:
            return []
