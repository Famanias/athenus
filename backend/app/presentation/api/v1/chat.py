from datetime import datetime
import json
import uuid
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, List, Optional, Any
from app.domain.ai.service_bus import AIServiceBus
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.domain.workspace.session_service import SessionService, ChatSessionDTO
from app.infrastructure.db.models import ChatSessionTable, ChatMessageTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

router = APIRouter()
session_service = SessionService()

# Global WorkspaceIntelligenceManager reference (initialized by main.py)
intelligence_manager: Optional[WorkspaceIntelligenceManager] = None

def get_intelligence_manager() -> WorkspaceIntelligenceManager:
    global intelligence_manager
    if intelligence_manager is None:
        from app.main import ai_service_bus, vector_store
        from app.infrastructure.retrieval.multi_stage_retriever import MultiStageRetriever
        from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
        from app.infrastructure.cache.runtime import application_memory_cache
        from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
        v_store = vector_store or EmbeddedQdrantVectorStoreAdapter()
        intelligence_manager = WorkspaceIntelligenceManager(
            ai_service_bus,
            retriever=MultiStageRetriever(
                ai_service_bus,
                vector_store=v_store,
                kg_service=KnowledgeGraphService(cache_store=application_memory_cache),
                cache_store=application_memory_cache,
            )
        )
    return intelligence_manager

class ChatQueryRequest(BaseModel):
    query: str
    workspace_id: str = "default"
    session_id: Optional[str] = None
    media_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: Optional[str] = None
    current_timestamp: Optional[float] = None
    current_page: Optional[int] = None
    selected_text: Optional[str] = None

class CreateSessionRequest(BaseModel):
    title: Optional[str] = "New Learning Session"
    is_pinned: bool = False
    is_archived: bool = False

class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None

class CitationDTO(BaseModel):
    chunk_id: Optional[str] = None
    source_type: str = "video"
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    page_number: Optional[int] = None
    section_title: Optional[str] = None
    text: str
    location: Optional[Dict[str, Any]] = None

class ChatQueryResponse(BaseModel):
    query: str
    answer: str
    session_id: str
    citations: List[CitationDTO]
    context_provenance: Optional[Dict[str, Any]] = None

class ChatMessageDTO(BaseModel):
    id: str
    session_id: str
    sender: str
    content: str
    timestamp: str
    citations: Optional[List[CitationDTO]] = None

def _persist_chat_turn(workspace_id: str, session_id: Optional[str], user_query: str, assistant_answer: str, citations: List[CitationDTO]) -> str:
    if not engine or not Session or not select:
        return session_id or f"sess_{uuid.uuid4().hex[:8]}"
    try:
        with Session(engine) as session:
            target_session = None
            if session_id:
                target_session = session.get(ChatSessionTable, session_id)

            if not target_session:
                # Lazy-create session on turn 1 using user's query snippet as title
                auto_title = user_query[:40] + "..." if len(user_query) > 40 else user_query
                target_session = ChatSessionTable(
                    id=session_id or f"sess_{uuid.uuid4().hex[:8]}",
                    workspace_id=workspace_id,
                    title=auto_title or "New Learning Session",
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                session.add(target_session)
                session.commit()
            elif target_session.title in ["New Learning Session", "Chat Session"]:
                target_session.title = user_query[:40] + "..." if len(user_query) > 40 else user_query

            # Save user message
            user_msg = ChatMessageTable(
                id=f"user_{uuid.uuid4().hex[:8]}",
                session_id=target_session.id,
                workspace_id=workspace_id,
                sender="user",
                content=user_query
            )
            session.add(user_msg)

            # Save assistant message
            citations_json = json.dumps([c.model_dump() for c in citations]) if citations else None
            asst_msg = ChatMessageTable(
                id=f"asst_{uuid.uuid4().hex[:8]}",
                session_id=target_session.id,
                workspace_id=workspace_id,
                sender="assistant",
                content=assistant_answer,
                citations_json=citations_json
            )
            session.add(asst_msg)

            # Update session preview & stats
            now = datetime.utcnow()
            target_session.last_message_at = now
            target_session.updated_at = now
            target_session.message_count = (getattr(target_session, "message_count", 0) or 0) + 2
            target_session.preview_text = user_query[:60]

            session.commit()
            return target_session.id
    except Exception:
        return session_id or f"sess_{uuid.uuid4().hex[:8]}"

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
            document_id=request.document_id,
            source_type=request.source_type,
            current_timestamp=request.current_timestamp,
            current_page=request.current_page,
            selected_text=request.selected_text
        )

        citations_list = [
            CitationDTO(
                chunk_id=c.get("chunk_id"),
                source_type=c.get("source_type", "video"),
                start_time=c.get("start_time"),
                end_time=c.get("end_time"),
                page_number=c.get("page_number"),
                section_title=c.get("section_title"),
                text=c.get("text", ""),
                location=c.get("location")
            )
            for c in result.get("citations", [])
        ]

        # Persist conversation turn to SQLite with session tracking
        actual_session_id = _persist_chat_turn(
            request.workspace_id,
            request.session_id,
            request.query,
            result["answer"],
            citations_list
        )

        return ChatQueryResponse(
            query=result["query"],
            answer=result["answer"],
            session_id=actual_session_id,
            citations=citations_list,
            context_provenance=result.get("context_provenance")
        )
    except HTTPException:
        raise
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/workspaces/{workspace_id}/sessions", response_model=List[ChatSessionDTO])
async def list_workspace_sessions(workspace_id: str, include_archived: bool = True):
    return session_service.list_sessions(workspace_id, include_archived=include_archived)

@router.post("/workspaces/{workspace_id}/sessions", response_model=ChatSessionDTO)
async def create_workspace_session(workspace_id: str, request: CreateSessionRequest):
    return session_service.create_session(
        workspace_id=workspace_id,
        title=request.title or "New Learning Session",
        is_pinned=request.is_pinned,
        is_archived=request.is_archived
    )

@router.get("/sessions/{session_id}", response_model=ChatSessionDTO)
async def get_session(session_id: str):
    sess = session_service.get_session(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@router.patch("/sessions/{session_id}", response_model=ChatSessionDTO)
async def update_session(session_id: str, request: UpdateSessionRequest):
    sess = session_service.update_session(
        session_id=session_id,
        title=request.title,
        is_pinned=request.is_pinned,
        is_archived=request.is_archived
    )
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    return sess

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    success = session_service.delete_session(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "deleted_session_id": session_id}

@router.get("/chat/history", response_model=List[ChatMessageDTO])
async def get_chat_history(workspace_id: str = "default", session_id: Optional[str] = None):
    if not engine or not Session or not select:
        return []
    try:
        with Session(engine) as session:
            if session_id:
                statement = select(ChatMessageTable).where(ChatMessageTable.session_id == session_id).order_by(ChatMessageTable.created_at)
            else:
                # Fallback to latest active session in workspace
                sess_stmt = select(ChatSessionTable).where(ChatSessionTable.workspace_id == workspace_id).order_by(ChatSessionTable.updated_at.desc())
                active_sess = session.scalars(sess_stmt).first() if hasattr(session, "scalars") else session.exec(sess_stmt).first()
                if not active_sess:
                    return []
                statement = select(ChatMessageTable).where(ChatMessageTable.session_id == active_sess.id).order_by(ChatMessageTable.created_at)

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
                        session_id=r.session_id,
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
async def clear_chat_history(workspace_id: str = "default", session_id: Optional[str] = None):
    """Clear persistent chat session messages for a given workspace or session in SQLite."""
    if not engine or not Session or not select:
        return {"status": "ok", "deleted_count": 0}
    try:
        with Session(engine) as session:
            if session_id:
                statement = select(ChatMessageTable).where(ChatMessageTable.session_id == session_id)
            else:
                statement = select(ChatMessageTable).where(ChatMessageTable.workspace_id == workspace_id)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            count = len(records)
            for r in records:
                session.delete(r)
            session.commit()
            return {"status": "ok", "deleted_count": count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


