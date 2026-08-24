from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from app.domain.knowledge.entities import ConceptNode
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.cache.runtime import application_memory_cache

router = APIRouter()
graph_service = KnowledgeGraphService(cache_store=application_memory_cache)

class ConceptNodeResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: str

@router.get("/graph/prerequisites/{concept_id}", response_model=List[ConceptNodeResponse])
def get_prerequisites(concept_id: str):
    prereqs = graph_service.recommend_prerequisites(concept_id)
    return [
        ConceptNodeResponse(
            id=p.id,
            workspace_id=p.workspace_id,
            name=p.name,
            description=p.description
        )
        for p in prereqs
    ]
