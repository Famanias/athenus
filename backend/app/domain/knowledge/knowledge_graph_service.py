from typing import List, Dict, Optional
from app.domain.knowledge.entities import ConceptNode, ConceptRelation, RelationType, KnowledgeGraphProtocol

class KnowledgeGraphService(KnowledgeGraphProtocol):
    """In-memory Knowledge Graph Service implementing Concept Graph traversal."""
    
    def __init__(self) -> None:
        self._nodes: Dict[str, ConceptNode] = {}
        self._edges: List[ConceptRelation] = []

    def add_node(self, node: ConceptNode) -> None:
        self._nodes[node.id] = node

    def add_edge(self, source_id: str, target_id: str, relation: RelationType, weight: float = 1.0) -> None:
        edge_id = f"edge_{source_id}_{target_id}"
        self._edges.append(ConceptRelation(
            id=edge_id,
            source_concept_id=source_id,
            target_concept_id=target_id,
            relation_type=relation,
            weight=weight
        ))

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
