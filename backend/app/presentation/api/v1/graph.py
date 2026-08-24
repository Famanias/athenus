import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.domain.knowledge.concept_merging import ConceptMergingService, cosine_similarity
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.cache.runtime import application_memory_cache

router = APIRouter()
graph_service = KnowledgeGraphService(cache_store=application_memory_cache)


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------
class ConceptNodeDTO(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str
    status: str
    media_id: Optional[str] = None
    source_chunk_ids: List[str] = []
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    degree: int = 0
    video_count: int = 0


class ConceptEdgeDTO(BaseModel):
    id: str
    source: str
    target: str
    relation_type: str
    weight: float
    media_id: Optional[str] = None


class ArtifactLifecycleDTO(BaseModel):
    status: str
    progress: int
    stage: Optional[str] = None
    message: Optional[str] = None
    error_message: Optional[str] = None
    updated_at: Optional[str] = None


class GraphTopologyResponse(BaseModel):
    workspace_id: str
    artifact: Optional[ArtifactLifecycleDTO] = None
    nodes: List[ConceptNodeDTO] = []
    edges: List[ConceptEdgeDTO] = []


class SearchResultDTO(BaseModel):
    id: str
    name: str
    description: str
    score: float
    media_id: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None


class NeighborGroupDTO(BaseModel):
    depth: str
    concepts: List[ConceptNodeDTO]


class ShortestPathResponse(BaseModel):
    path: List[str]
    exists: bool
    hop_count: int


# ---------------------------------------------------------------------------
# Lazy AI Service Bus access (embedding capabilities only)
# ---------------------------------------------------------------------------
def _get_embedding_capability():
    from app.main import ai_service_bus
    return ai_service_bus.get_embedding_capability()


def _concept_dto(node, degree: int = 0, video_count: int = 0) -> ConceptNodeDTO:
    return ConceptNodeDTO(
        id=node.id,
        workspace_id=node.workspace_id,
        name=node.name,
        description=node.description,
        status=node.status,
        media_id=node.media_id,
        source_chunk_ids=node.source_chunk_ids,
        start_time=node.start_time,
        end_time=node.end_time,
        degree=degree,
        video_count=video_count,
    )


# ---------------------------------------------------------------------------
# Topology
# ---------------------------------------------------------------------------
@router.get("/graph/workspace/{workspace_id}", response_model=GraphTopologyResponse)
def get_workspace_graph(workspace_id: str):
    nodes = graph_service.get_concepts(workspace_id)
    edges = graph_service.get_relations(workspace_id)

    degree_map: dict = {}
    for edge in edges:
        degree_map[edge.source_concept_id] = degree_map.get(edge.source_concept_id, 0) + 1
        degree_map[edge.target_concept_id] = degree_map.get(edge.target_concept_id, 0) + 1

    job = graph_service.get_artifact_job(workspace_id, "graph")
    artifact = None
    if job:
        artifact = ArtifactLifecycleDTO(
            status=job.status,
            progress=job.progress,
            stage=getattr(job, "stage", None),
            message=job.message,
            error_message=job.error_message,
            updated_at=job.updated_at.isoformat() if job.updated_at else None,
        )

    return GraphTopologyResponse(
        workspace_id=workspace_id,
        artifact=artifact,
        nodes=[
            _concept_dto(
                n,
                degree=degree_map.get(n.id, 0),
                video_count=1 if n.media_id else 0,
            )
            for n in nodes
        ],
        edges=[
            ConceptEdgeDTO(
                id=e.id,
                source=e.source_concept_id,
                target=e.target_concept_id,
                relation_type=e.relation_type.value
                if hasattr(e.relation_type, "value")
                else str(e.relation_type),
                weight=e.weight,
                media_id=e.media_id,
            )
            for e in edges
        ],
    )


# ---------------------------------------------------------------------------
# Hybrid keyword + semantic concept search
# ---------------------------------------------------------------------------
@router.get("/graph/concepts/search", response_model=List[SearchResultDTO])
async def search_concepts(
    workspace_id: str = Query("default"),
    q: str = Query("", min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    if not q.strip():
        raise HTTPException(status_code=422, detail="Query parameter 'q' is required.")
    query_lower = q.lower()

    merging = ConceptMergingService(cache_store=application_memory_cache)
    rows = merging.list_concepts(workspace_id)
    if not rows:
        return []

    # 1. Keyword scoring (exact / substring on name & description)
    scored: dict = {}
    for row in rows:
        kw_score = 0.0
        if query_lower in row.name.lower():
            kw_score = max(kw_score, 1.0)
        if row.description and query_lower in row.description.lower():
            kw_score = max(kw_score, 0.6)
        if kw_score > 0:
            scored[row.id] = max(scored.get(row.id, 0.0), kw_score)

    # 2. Semantic scoring via embedding distance
    try:
        embedding_cap = _get_embedding_capability()
        semantic = ConceptMergingService(
            embedding_capability=embedding_cap,
            cache_store=application_memory_cache,
        )
        query_vec = await embedding_cap.embed_query(q)
        for row in rows:
            if not row.embedding:
                continue
            try:
                stored = json.loads(row.embedding)
            except Exception:
                continue
            sim = cosine_similarity(query_vec, stored)
            if sim >= 0.45:
                scored[row.id] = max(scored.get(row.id, 0.0), round(sim, 4))
    except Exception:
        pass

    ranked = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:limit]
    by_id = {r.id: r for r in rows}
    return [
        SearchResultDTO(
            id=cid,
            name=by_id[cid].name,
            description=by_id[cid].description or "",
            score=score,
            media_id=by_id[cid].media_id,
            start_time=by_id[cid].start_time,
            end_time=by_id[cid].end_time,
        )
        for cid, score in ranked
        if cid in by_id
    ]


# ---------------------------------------------------------------------------
# N-hop traversal
# ---------------------------------------------------------------------------
@router.get("/graph/concepts/{concept_id}/neighbors", response_model=List[NeighborGroupDTO])
def get_concept_neighbors(
    concept_id: str,
    workspace_id: str = Query("default"),
    depth: int = Query(2, ge=1, le=6),
):
    node = graph_service.get_concept(concept_id)
    if not node:
        raise HTTPException(status_code=404, detail="Concept not found")
    neighbors = graph_service.get_neighbors(concept_id, max_depth=depth, workspace_id=workspace_id)
    return [
        NeighborGroupDTO(depth=d, concepts=[_concept_dto(n) for n in nodes])
        for d, nodes in neighbors.items()
    ]


# ---------------------------------------------------------------------------
# Shortest path / prerequisite dependency resolution
# ---------------------------------------------------------------------------
@router.get("/graph/concepts/shortest-path", response_model=ShortestPathResponse)
def get_shortest_path(
    workspace_id: str = Query("default"),
    source: str = Query(...),
    target: str = Query(...),
):
    if not graph_service.get_concept(source):
        raise HTTPException(status_code=404, detail=f"Source concept '{source}' not found")
    if not graph_service.get_concept(target):
        raise HTTPException(status_code=404, detail=f"Target concept '{target}' not found")
    path = graph_service.shortest_path(source, target, workspace_id=workspace_id)
    return ShortestPathResponse(
        path=path,
        exists=len(path) > 0,
        hop_count=max(0, len(path) - 1),
    )


# ---------------------------------------------------------------------------
# Legacy compatibility route
# ---------------------------------------------------------------------------
@router.get("/graph/prerequisites/{concept_id}", response_model=List[ConceptNodeDTO])
def get_prerequisites(concept_id: str):
    prereqs = graph_service.recommend_prerequisites(concept_id)
    return [_concept_dto(p) for p in prereqs]
