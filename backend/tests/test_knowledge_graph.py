from app.domain.knowledge.entities import ConceptNode, RelationType
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService

def test_knowledge_graph_traversal():
    service = KnowledgeGraphService()
    n1 = ConceptNode(id="c1", workspace_id="ws1", name="Calculus", description="Differential calculus")
    n2 = ConceptNode(id="c2", workspace_id="ws1", name="Neural Networks", description="Deep learning backpropagation")

    service.add_node(n1)
    service.add_node(n2)
    service.add_edge(source_id="c1", target_id="c2", relation=RelationType.PREREQUISITE_FOR)

    prereqs = service.recommend_prerequisites("c2")
    assert len(prereqs) == 1
    assert prereqs[0].id == "c1"

    related = service.find_related("c1")
    assert len(related) == 1
    assert related[0].id == "c2"
