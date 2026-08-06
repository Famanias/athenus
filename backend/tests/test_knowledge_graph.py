import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient

from app.domain.ai.capabilities import IEmbeddingCapability, ITextGenerationCapability, TextGenerationRequest, TextGenerationResponse
from app.domain.knowledge.concept_merging import ConceptMergingService, cosine_similarity
from app.domain.knowledge.entities import ConceptNode, RelationType
from app.domain.knowledge.graph_extraction import (
    build_extraction_prompt,
    extract_concepts_heuristic,
    parse_llm_extraction,
)
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.models import ConceptAliasTable, KnowledgeConceptTable
from app.infrastructure.db.session import engine, init_db
from app.main import app

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

client = TestClient(app)


# ---------------------------------------------------------------------------
# Legacy in-memory traversal behaviour
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Phase 1.1 — Incremental Concept Merging Service
# ---------------------------------------------------------------------------
class FakeEmbedding(IEmbeddingCapability):
    """Deterministic embedding test-double.

    Known names map to fixed vectors (exact control); unknown strings fall back
    to a character-trigram bag-of-words embedding so distinct terms get distinct
    vectors while near-identical strings remain similar.
    """

    DIMS = 384

    def __init__(self) -> None:
        self.vectors = {
            "neural networks": [1.0, 0.0, 0.0, 0.0],
            "neural network": [0.99, 0.02, 0.0, 0.0],
            "backpropagation": [0.0, 1.0, 0.0, 0.0],
            "back propagation": [0.01, 0.99, 0.0, 0.0],
            "quantum computing": [0.0, 0.0, 1.0, 0.0],
        }

    def _embed_str(self, text: str):
        key = text.lower().strip()
        if key in self.vectors:
            return self.vectors[key]
        vec = [0.0] * self.DIMS
        for i in range(max(0, len(key) - 2)):
            gram = key[i:i + 3]
            vec[hash(gram) % self.DIMS] += 1.0
        norm = sum(v * v for v in vec) ** 0.5
        if norm == 0.0:
            return [0.01] * self.DIMS
        return [v / norm for v in vec]

    async def embed_texts(self, texts):
        return [self._embed_str(t) for t in texts]

    async def embed_query(self, query):
        return self._embed_str(query)


@pytest.fixture(autouse=True)
def _init_db():
    init_db()


def test_concept_merging_exact_match():
    ws = f"ws_merge_exact_{uuid.uuid4().hex[:6]}"
    merging = ConceptMergingService(embedding_capability=FakeEmbedding())

    canonical_id, is_new = asyncio.run(
        merging.resolve_concept(ws, "Neural Networks", "Deep learning model")
    )
    assert is_new is True

    merged_id, is_new = asyncio.run(
        merging.resolve_concept(ws, "Neural Networks", "Duplicate description")
    )
    assert is_new is False
    assert merged_id == canonical_id


def test_concept_merging_alias_match():
    ws = f"ws_merge_alias_{uuid.uuid4().hex[:6]}"
    merging = ConceptMergingService(embedding_capability=FakeEmbedding())

    canonical_id, _ = asyncio.run(merging.resolve_concept(ws, "Backpropagation", "Gradient rule"))
    alias_id, is_new = asyncio.run(merging.resolve_concept(ws, "Back Propagation", "Spelling variant"))
    assert is_new is False
    assert alias_id == canonical_id


def test_concept_merging_semantic_match():
    ws = f"ws_merge_semantic_{uuid.uuid4().hex[:6]}"
    merging = ConceptMergingService(embedding_capability=FakeEmbedding())

    canonical_id, _ = asyncio.run(
        merging.resolve_concept(ws, "Neural Networks", "DL architecture", media_id="med_a", source_chunk_ids=["chunk_1"], start_time=0.0, end_time=10.0)
    )
    merged_id, is_new = asyncio.run(
        merging.resolve_concept(ws, "Neural Network", "Singular variant", media_id="med_b", source_chunk_ids=["chunk_2"], start_time=20.0, end_time=30.0)
    )
    assert is_new is False
    assert merged_id == canonical_id

    # Provenance accumulation across media
    with Session(engine) as session:
        row = session.get(KnowledgeConceptTable, canonical_id)
        assert row is not None
        assert row.media_id == "med_b"
        assert "chunk_1" in row.source_chunk_ids
        assert "chunk_2" in row.source_chunk_ids
        assert row.start_time == 0.0
        assert row.end_time == 30.0


def test_concept_merging_creates_distinct_concepts():
    ws = f"ws_merge_distinct_{uuid.uuid4().hex[:6]}"
    merging = ConceptMergingService(embedding_capability=FakeEmbedding())

    nn_id, is_new = asyncio.run(merging.resolve_concept(ws, "Neural Networks"))
    qc_id, is_new2 = asyncio.run(merging.resolve_concept(ws, "Quantum Computing"))
    assert is_new is True
    assert is_new2 is True
    assert nn_id != qc_id

    with Session(engine) as session:
        alias_stmt = select(ConceptAliasTable).where(ConceptAliasTable.workspace_id == ws)
        aliases = session.scalars(alias_stmt).all() if hasattr(session, "scalars") else session.exec(alias_stmt).all()
        assert len(aliases) == 2


def test_cosine_similarity_math():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
    assert cosine_similarity([], [1.0]) == 0.0


# ---------------------------------------------------------------------------
# Phase 1.2 — Graph extraction primitives
# ---------------------------------------------------------------------------
def test_heuristic_concept_extraction():
    chunks = [
        {"id": "c0", "text": "Gradient descent is an optimization algorithm used to minimize the loss function.", "start_time": 0.0, "end_time": 5.0},
        {"id": "c1", "text": "Backpropagation computes gradients of the loss function for gradient descent.", "start_time": 5.0, "end_time": 10.0},
    ]
    concepts, relations = extract_concepts_heuristic(chunks, max_concepts=6)
    assert len(concepts) >= 3
    names = [c.name.lower() for c in concepts]
    assert any("gradient" in n or "gradient descent" in n for n in names)
    for c in concepts:
        assert c.source_chunk_ids


def test_llm_extraction_json_parsing():
    valid = (
        '{"concepts": [{"name": "Backpropagation", "description": "d", "source_chunk_ids": ["c0"]}],'
        ' "relations": [{"source": "Backpropagation", "target": "Gradient Descent", "relation_type": "prerequisite_for"}]}'
    )
    concepts, relations = parse_llm_extraction(valid)
    assert concepts is not None
    assert concepts[0].name == "Backpropagation"
    assert relations[0].relation_type == "prerequisite_for"

    assert parse_llm_extraction("not json at all") is None


def test_extraction_prompt_includes_chunk_timestamps():
    chunks = [{"id": "c0", "text": "Some lecture content.", "start_time": 12.5, "end_time": 18.0}]
    prompt = build_extraction_prompt(chunks)
    assert "[chunk:c0]" in prompt
    assert "12.5" in prompt


class MockTextGen(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text=(
                '{"concepts": [{"name": "Local First AI", "description": "Offline local execution", "source_chunk_ids": ["chunk_0"]},'
                ' {"name": "Embedded Qdrant", "description": "Vector store", "source_chunk_ids": ["chunk_0"]}],'
                ' "relations": [{"source": "Embedded Qdrant", "target": "Local First AI", "relation_type": "related_to"}]}'
            )
        )

    async def stream(self, request):
        yield ""


def _seed_chunks(media_id, workspace_id, texts):
    from app.infrastructure.db.models import TranscriptChunkTable
    with Session(engine) as session:
        for idx, text in enumerate(texts):
            session.add(TranscriptChunkTable(
                id=f"{media_id}_chunk_{idx}",
                media_id=media_id,
                workspace_id=workspace_id,
                text=text,
                start_time=idx * 5.0,
                end_time=idx * 5.0 + 5.0,
                chunk_index=idx,
                word_count=len(text.split()),
            ))
        session.commit()


def test_graph_extraction_worker_end_to_end():
    from app.domain.ai.model_registry import ModelRegistry
    from app.domain.ai.provider_router import ProviderRouter
    from app.domain.ai.service_bus import AIServiceBus
    from app.infrastructure.events.event_bus import EventBus, DomainEvent
    from app.services.workers.graph_extraction_worker import GraphExtractionWorker

    ws = f"ws_graph_worker_{uuid.uuid4().hex[:6]}"
    media_id = f"med_worker_{uuid.uuid4().hex[:6]}"
    _seed_chunks(media_id, ws, [
        "Local first AI architectures run models entirely offline on the user's machine.",
        "Embedded Qdrant provides a local vector database for semantic retrieval.",
    ])

    registry = ModelRegistry()
    router = ProviderRouter(registry)
    bus = AIServiceBus(registry, router)
    bus.register_text_adapter("ollama", MockTextGen())
    bus.register_embedding_adapter("sentence_transformers", FakeEmbedding())

    event_bus = EventBus()
    graph_service = KnowledgeGraphService()
    worker = GraphExtractionWorker(event_bus, bus, graph_service)

    captured = []
    async def capture_updated(event: DomainEvent):
        captured.append(event)
    event_bus.subscribe("ConceptGraphUpdatedEvent", capture_updated)

    async def run():
        await event_bus.publish(DomainEvent(
            event_type="ChunksIndexedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "workspace_id": ws, "chunk_count": 2},
        ))

    asyncio.run(run())

    assert len(captured) == 1
    concepts = graph_service.get_concepts(ws)
    assert len(concepts) >= 2
    assert all(c.media_id == media_id for c in concepts)
    relations = graph_service.get_relations(ws)
    assert len(relations) >= 1


def test_graph_extraction_worker_heuristic_fallback():
    from app.domain.ai.model_registry import ModelRegistry
    from app.domain.ai.provider_router import ProviderRouter
    from app.domain.ai.service_bus import AIServiceBus
    from app.infrastructure.events.event_bus import EventBus, DomainEvent
    from app.services.workers.graph_extraction_worker import GraphExtractionWorker

    class OfflineTextGen(ITextGenerationCapability):
        async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
            return TextGenerationResponse(text="Local AI Response (Ollama Offline Fallback): ...")

        async def stream(self, request):
            yield ""

    ws = f"ws_graph_heuristic_{uuid.uuid4().hex[:6]}"
    media_id = f"med_heur_{uuid.uuid4().hex[:6]}"
    _seed_chunks(media_id, ws, [
        "Gradient descent minimizes the loss function in deep learning training.",
        "Backpropagation computes weight updates for gradient descent optimization.",
    ])

    registry = ModelRegistry()
    router = ProviderRouter(registry)
    bus = AIServiceBus(registry, router)
    bus.register_text_adapter("ollama", OfflineTextGen())
    bus.register_embedding_adapter("sentence_transformers", FakeEmbedding())

    event_bus = EventBus()
    graph_service = KnowledgeGraphService()
    GraphExtractionWorker(event_bus, bus, graph_service)

    async def run():
        await event_bus.publish(DomainEvent(
            event_type="ChunksIndexedEvent",
            aggregate_id=media_id,
            payload={"media_id": media_id, "workspace_id": ws, "chunk_count": 2},
        ))

    asyncio.run(run())

    concepts = graph_service.get_concepts(ws)
    assert len(concepts) >= 2
    job = graph_service.get_artifact_job(ws, "graph", target_key=media_id)
    assert job is not None
    assert job.status == "ready"


# ---------------------------------------------------------------------------
# Phase 1.3 — Graph REST APIs
# ---------------------------------------------------------------------------
def _seed_workspace_graph(workspace_id):
    service = KnowledgeGraphService()
    ids = []
    for name, desc in [
        ("Calculus", "Differential and integral calculus"),
        ("Linear Algebra", "Vector spaces and matrices"),
        ("Neural Networks", "Deep learning architecture"),
    ]:
        cid = f"concept_{uuid.uuid4().hex[:8]}"
        service.add_concept(ConceptNode(
            id=cid, workspace_id=workspace_id, name=name, description=desc,
            status="ready", media_id="med_seed", start_time=0.0, end_time=10.0,
            source_chunk_ids=["chunk_seed"],
        ))
        ids.append(cid)
    service.add_relation(ids[0], ids[2], RelationType.PREREQUISITE_FOR, workspace_id=workspace_id)
    service.add_relation(ids[1], ids[2], RelationType.PREREQUISITE_FOR, workspace_id=workspace_id)
    return ids


def test_graph_workspace_topology_endpoint():
    ws = f"ws_topology_{uuid.uuid4().hex[:6]}"
    _seed_workspace_graph(ws)

    res = client.get(f"/api/v1/graph/workspace/{ws}")
    assert res.status_code == 200
    data = res.json()
    assert len(data["nodes"]) == 3
    assert len(data["edges"]) == 2
    node = data["nodes"][0]
    assert node["media_id"] == "med_seed"
    assert node["start_time"] == 0.0
    assert node["end_time"] == 10.0


def test_graph_search_endpoint():
    ws = f"ws_search_{uuid.uuid4().hex[:6]}"
    _seed_workspace_graph(ws)

    res = client.get(f"/api/v1/graph/concepts/search", params={"workspace_id": ws, "q": "Calculus"})
    assert res.status_code == 200
    results = res.json()
    assert len(results) >= 1
    assert results[0]["name"] == "Calculus"


def test_graph_neighbors_endpoint():
    ws = f"ws_neighbors_{uuid.uuid4().hex[:6]}"
    ids = _seed_workspace_graph(ws)

    res = client.get(f"/api/v1/graph/concepts/{ids[2]}/neighbors", params={"workspace_id": ws, "depth": 2})
    assert res.status_code == 200
    groups = res.json()
    assert any("Calculus" in [c["name"] for c in group["concepts"]] for group in groups)


def test_graph_shortest_path_endpoint():
    ws = f"ws_path_{uuid.uuid4().hex[:6]}"
    ids = _seed_workspace_graph(ws)

    res = client.get(f"/api/v1/graph/concepts/shortest-path", params={"workspace_id": ws, "source": ids[0], "target": ids[2]})
    assert res.status_code == 200
    data = res.json()
    assert data["exists"] is True
    assert data["path"][0] == ids[0]
    assert data["path"][-1] == ids[2]
