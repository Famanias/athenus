from datetime import datetime
from typing import List, Optional
import uuid
from pydantic import BaseModel
from app.infrastructure.db.models import ChatSessionTable, ChatMessageTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class ChatSessionDTO(BaseModel):
    id: str
    workspace_id: str
    title: str
    is_pinned: bool = False
    is_archived: bool = False
    last_message_at: Optional[str] = None
    message_count: int = 0
    preview_text: Optional[str] = None
    created_at: str
    updated_at: str


class SessionService:
    """Domain service managing chat session lifecycles per workspace."""

    def create_session(
        self,
        workspace_id: str,
        title: str = "New Learning Session",
        is_pinned: bool = False,
        is_archived: bool = False,
        session_id: Optional[str] = None
    ) -> ChatSessionDTO:
        sid = session_id or f"sess_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()

        if engine and Session:
            try:
                with Session(engine) as session:
                    db_sess = ChatSessionTable(
                        id=sid,
                        workspace_id=workspace_id,
                        title=title,
                        is_pinned=is_pinned,
                        is_archived=is_archived,
                        created_at=now,
                        updated_at=now
                    )
                    session.add(db_sess)
                    session.commit()
            except Exception:
                pass

        return ChatSessionDTO(
            id=sid,
            workspace_id=workspace_id,
            title=title,
            is_pinned=is_pinned,
            is_archived=is_archived,
            last_message_at=None,
            message_count=0,
            preview_text=None,
            created_at=now.isoformat(),
            updated_at=now.isoformat()
        )

    def list_sessions(self, workspace_id: str, include_archived: bool = True) -> List[ChatSessionDTO]:
        if not engine or not Session or not select:
            return []
        try:
            with Session(engine) as session:
                stmt = select(ChatSessionTable).where(ChatSessionTable.workspace_id == workspace_id)
                records = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                results = []
                for r in records:
                    if not include_archived and getattr(r, "is_archived", False):
                        continue
                    last_msg_str = r.last_message_at.strftime("%Y-%m-%d %H:%M") if getattr(r, "last_message_at", None) else None
                    created_str = r.created_at.isoformat() if r.created_at else ""
                    updated_str = r.updated_at.isoformat() if r.updated_at else ""
                    results.append(
                        ChatSessionDTO(
                            id=r.id,
                            workspace_id=r.workspace_id,
                            title=r.title or "Chat Session",
                            is_pinned=bool(getattr(r, "is_pinned", False)),
                            is_archived=bool(getattr(r, "is_archived", False)),
                            last_message_at=last_msg_str,
                            message_count=getattr(r, "message_count", 0) or 0,
                            preview_text=getattr(r, "preview_text", None),
                            created_at=created_str,
                            updated_at=updated_str
                        )
                    )
                # Sort: pinned first, then last_message_at or created_at descending
                return sorted(
                    results,
                    key=lambda s: (not s.is_pinned, s.last_message_at or s.created_at),
                    reverse=True
                )
        except Exception:
            return []

    def get_session(self, session_id: str) -> Optional[ChatSessionDTO]:
        if not engine or not Session:
            return None
        try:
            with Session(engine) as session:
                r = session.get(ChatSessionTable, session_id)
                if not r:
                    return None
                last_msg_str = r.last_message_at.strftime("%Y-%m-%d %H:%M") if getattr(r, "last_message_at", None) else None
                return ChatSessionDTO(
                    id=r.id,
                    workspace_id=r.workspace_id,
                    title=r.title or "Chat Session",
                    is_pinned=bool(getattr(r, "is_pinned", False)),
                    is_archived=bool(getattr(r, "is_archived", False)),
                    last_message_at=last_msg_str,
                    message_count=getattr(r, "message_count", 0) or 0,
                    preview_text=getattr(r, "preview_text", None),
                    created_at=r.created_at.isoformat() if r.created_at else "",
                    updated_at=r.updated_at.isoformat() if r.updated_at else ""
                )
        except Exception:
            return None

    def update_session(
        self,
        session_id: str,
        title: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None
    ) -> Optional[ChatSessionDTO]:
        if not engine or not Session:
            return None
        try:
            with Session(engine) as session:
                r = session.get(ChatSessionTable, session_id)
                if not r:
                    return None
                if title is not None:
                    r.title = title
                if is_pinned is not None:
                    r.is_pinned = is_pinned
                if is_archived is not None:
                    r.is_archived = is_archived
                r.updated_at = datetime.utcnow()
                session.commit()
                return self.get_session(session_id)
        except Exception:
            return None

    def delete_session(self, session_id: str) -> bool:
        if not engine or not Session or not select:
            return False
        try:
            with Session(engine) as session:
                # Delete messages in session
                stmt = select(ChatMessageTable).where(ChatMessageTable.session_id == session_id)
                messages = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                for m in messages:
                    session.delete(m)
                
                sess = session.get(ChatSessionTable, session_id)
                if sess:
                    session.delete(sess)
                session.commit()
                return True
        except Exception:
            return False

    def move_session(self, session_id: str, target_workspace_id: str) -> bool:
        """Future-proofing helper to move a chat session to a new workspace."""
        if not engine or not Session or not select:
            return False
        try:
            with Session(engine) as session:
                sess = session.get(ChatSessionTable, session_id)
                if not sess:
                    return False
                sess.workspace_id = target_workspace_id
                sess.updated_at = datetime.utcnow()
                
                # Update messages workspace_id as well
                stmt = select(ChatMessageTable).where(ChatMessageTable.session_id == session_id)
                messages = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                for m in messages:
                    m.workspace_id = target_workspace_id
                session.commit()
                return True
        except Exception:
            return False
