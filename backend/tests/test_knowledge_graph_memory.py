from fastapi.testclient import TestClient
from app.domain.ai.service_bus import AIServiceBus
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.knowledge.entities import ConceptNode, RelationType
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.adapters.sentence_transformers_adapter import SentenceTransformersEmbeddingAdapter
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import KnowledgeConceptTable, KnowledgeRelationTable, ChatMessageTable
from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
from app.main import app

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def test_knowledge_graph_persistence_and_rag_expansion():
    init_db()
    workspace_id = "ws_kg_test_99"
    kg_service = KnowledgeGraphService()

    # 1. Add concept nodes and edges to SQLite
    node_cs1 = ConceptNode(id="concept_gd", workspace_id=workspace_id, name="Gradient Descent", description="Optimization algorithm")
    node_cs2 = ConceptNode(id="concept_bp", workspace_id=workspace_id, name="Backpropagation", description="Derivative weight updates")
    kg_service.add_node(node_cs1, workspace_id=workspace_id)
    kg_service.add_node(node_cs2, workspace_id=workspace_id)
    kg_service.add_edge("concept_bp", "concept_gd", RelationType.PREREQUISITE_FOR, workspace_id=workspace_id)

    # 2. Verify concepts and relations persist in SQLite tables
    with Session(engine) as session:
        c_stmt = select(KnowledgeConceptTable).where(KnowledgeConceptTable.workspace_id == workspace_id)
        concepts = session.scalars(c_stmt).all() if hasattr(session, "scalars") else session.exec(c_stmt).all()
        assert len(concepts) >= 2

        r_stmt = select(KnowledgeRelationTable).where(KnowledgeRelationTable.workspace_id == workspace_id)
        relations = session.scalars(r_stmt).all() if hasattr(session, "scalars") else session.exec(r_stmt).all()
        assert len(relations) >= 1
        assert relations[0].source_concept == "concept_bp"

    # 3. Test RAG Stage 4 graph traversal context expansion
    async def _test_retrieval():
        registry = ModelRegistry()
        router = ProviderRouter(registry)
        bus = AIServiceBus(registry, router)
        bus.register_embedding_adapter("sentence_transformers", SentenceTransformersEmbeddingAdapter())

        retriever = MultiStageRetriever(bus, kg_service=kg_service)
        ctx = await retriever.execute_retrieval(query="How does backpropagation optimize weights?", workspace_id=workspace_id)
        assert len(ctx.graph_triples) > 0
        assert "concept_bp" in ctx.graph_triples[0]
        assert "Knowledge Graph Concepts & Relationships" in ctx.assembled_prompt

    import asyncio
    asyncio.run(_test_retrieval())


def test_chat_history_deletion_endpoint():
    init_db()
    client = TestClient(app)
    ws_id = "ws_del_test_1"

    # Post a chat turn
    post_res = client.post("/api/v1/chat/query", json={
        "query": "What is machine learning?",
        "workspace_id": ws_id
    })
    assert post_res.status_code == 200

    # Verify history exists
    get_res = client.get(f"/api/v1/chat/history?workspace_id={ws_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 2

    # Delete history via DELETE endpoint
    del_res = client.delete(f"/api/v1/chat/history?workspace_id={ws_id}")
    assert del_res.status_code == 200
    assert del_res.json()["deleted_count"] >= 2

    # Verify history is now empty
    get_res_empty = client.get(f"/api/v1/chat/history?workspace_id={ws_id}")
    assert get_res_empty.status_code == 200
    assert len(get_res_empty.json()) == 0
