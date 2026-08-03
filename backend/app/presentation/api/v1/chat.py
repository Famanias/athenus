import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from app.domain.ai.service_bus import AIServiceBus
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.infrastructure.db.models import ChatSessionTable, ChatMessageTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

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
    current_timestamp: Optional[float] = None
    selected_text: Optional[str] = None

class CitationDTO(BaseModel):
    chunk_id: Optional[str] = None
    start_time: float
    end_time: float
    text: str

class ChatQueryResponse(BaseModel):
    query: str
    answer: str
    citations: List[CitationDTO]
    context_provenance: Optional[Dict[str, Any]] = None

class ChatMessageDTO(BaseModel):
    id: str
    sender: str
    content: str
    timestamp: str
    citations: Optional[List[CitationDTO]] = None

def _persist_chat_turn(workspace_id: str, user_query: str, assistant_answer: str, citations: List[CitationDTO]) -> None:
    if not engine or not Session or not select:
        return
    try:
        with Session(engine) as session:
            session_statement = select(ChatSessionTable).where(ChatSessionTable.workspace_id == workspace_id).order_by(ChatSessionTable.created_at.desc())
            active_session = session.scalars(session_statement).first() if hasattr(session, "scalars") else session.exec(session_statement).first()
            if not active_session:
                active_session = ChatSessionTable(
                    id=f"sess_{uuid.uuid4().hex[:8]}",
                    workspace_id=workspace_id,
                    title="Active Learning Session"
                )
                session.add(active_session)
                session.commit()

            # Save user message
            user_msg = ChatMessageTable(
                id=f"user_{uuid.uuid4().hex[:8]}",
                session_id=active_session.id,
                workspace_id=workspace_id,
                sender="user",
                content=user_query
            )
            session.add(user_msg)

            # Save assistant message
            citations_json = json.dumps([c.model_dump() for c in citations]) if citations else None
            asst_msg = ChatMessageTable(
                id=f"asst_{uuid.uuid4().hex[:8]}",
                session_id=active_session.id,
                workspace_id=workspace_id,
                sender="assistant",
                content=assistant_answer,
                citations_json=citations_json
            )
            session.add(asst_msg)
            session.commit()
    except Exception:
        pass

@router.post("/chat/query", response_model=ChatQueryResponse)
async def query_chat(
    request: ChatQueryRequest,
    manager: WorkspaceIntelligenceManager = Depends(get_intelligence_manager)
):
    try:
        result = await manager.query_workspace(
            query=request.query,
            workspace_id=request.workspace_id,
            media_id=request.media_id,
            current_timestamp=request.current_timestamp,
            selected_text=request.selected_text
        )

        citations_list = [
            CitationDTO(
                chunk_id=c.get("chunk_id"),
                start_time=c.get("start_time", 0.0),
                end_time=c.get("end_time", 0.0),
                text=c.get("text", "")
            )
            for c in result.get("citations", [])
        ]

        # Persist conversation turn to SQLite
        _persist_chat_turn(request.workspace_id, request.query, result["answer"], citations_list)

        return ChatQueryResponse(
            query=result["query"],
            answer=result["answer"],
            citations=citations_list,
            context_provenance=result.get("context_provenance")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/chat/history", response_model=List[ChatMessageDTO])
async def get_chat_history(workspace_id: str = "default"):
    if not engine or not Session or not select:
        return []
    try:
        with Session(engine) as session:
            statement = select(ChatMessageTable).where(ChatMessageTable.workspace_id == workspace_id).order_by(ChatMessageTable.created_at)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            history = []
            for r in records:
                citations = None
                if r.citations_json:
                    try:
                        raw_cits = json.loads(r.citations_json)
                        citations = [CitationDTO(**c) for c in raw_cits]
                    except Exception:
                        citations = None

                history.append(
                    ChatMessageDTO(
                        id=r.id,
                        sender=r.sender,
                        content=r.content,
                        timestamp=r.created_at.strftime("%H:%M") if r.created_at else "00:00",
                        citations=citations
                    )
                )
            return history
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/chat/history")
async def clear_chat_history(workspace_id: str = "default"):
    """Clear persistent chat session messages for a given workspace in SQLite."""
    if not engine or not Session or not select:
        return {"status": "ok", "deleted_count": 0}
    try:
        with Session(engine) as session:
            statement = select(ChatMessageTable).where(ChatMessageTable.workspace_id == workspace_id)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            count = len(records)
            for r in records:
                session.delete(r)
            session.commit()
            return {"status": "ok", "deleted_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

