from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from app.domain.ai.service_bus import AIServiceBus
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager

router = APIRouter()

# Global WorkspaceIntelligenceManager reference (initialized by main.py)
intelligence_manager: Optional[WorkspaceIntelligenceManager] = None

def get_intelligence_manager() -> WorkspaceIntelligenceManager:
    global intelligence_manager
    if intelligence_manager is None:
        from app.main import ai_service_bus, vector_store
        from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
        from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
        v_store = vector_store or EmbeddedQdrantVectorStoreAdapter()
        intelligence_manager = WorkspaceIntelligenceManager(
            ai_service_bus,
            retriever=MultiStageRetriever(ai_service_bus, vector_store=v_store)
        )
    return intelligence_manager

class ChatQueryRequest(BaseModel):
    query: str
    workspace_id: str = "default"
    media_id: Optional[str] = None

class CitationDTO(BaseModel):
    chunk_id: Optional[str] = None
    start_time: float
    end_time: float
    text: str

class ChatQueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationDTO]

@router.post("/chat/query", response_model=ChatQueryResponse)
async def query_chat(
    request: ChatQueryRequest,
    manager: WorkspaceIntelligenceManager = Depends(get_intelligence_manager)
):
    try:
        result = await manager.query_workspace(
            query=request.query,
            workspace_id=request.workspace_id,
            media_id=request.media_id
        )
        return ChatQueryResponse(
            query=result["query"],
            answer=result["answer"],
            citations=[
                CitationDTO(
                    chunk_id=c.get("chunk_id"),
                    start_time=c.get("start_time", 0.0),
                    end_time=c.get("end_time", 0.0),
                    text=c.get("text", "")
                )
                for c in result.get("citations", [])
            ]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
