from typing import List, Optional, Dict
import uuid
from datetime import datetime
from app.domain.common.cache_interface import ICacheStore, NullCacheStore
from app.domain.workspace.entities import Workspace
from app.infrastructure.db.models import (
    WorkspaceTable, MediaItemTable, TranscriptChunkTable,
    ChatSessionTable, ChatMessageTable, ProcessingLogTable,
    KnowledgeConceptTable, KnowledgeRelationTable
)
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class WorkspaceService:
    """Domain service managing workspace lifecycle and collections, backed by SQLite."""

    _instance: Optional["WorkspaceService"] = None
    _initialized: bool = False

    def __new__(
        cls,
        application_cache: Optional[ICacheStore] = None,
        persistent_cache: Optional[ICacheStore] = None,
    ) -> "WorkspaceService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        application_cache: Optional[ICacheStore] = None,
        persistent_cache: Optional[ICacheStore] = None,
    ) -> None:
        if WorkspaceService._initialized:
            if application_cache is not None:
                self._application_cache = application_cache
            if persistent_cache is not None:
                self._persistent_cache = persistent_cache
            return
        WorkspaceService._initialized = True
        self._application_cache = (
            application_cache if application_cache is not None else NullCacheStore()
        )
        self._persistent_cache = (
            persistent_cache if persistent_cache is not None else NullCacheStore()
        )
        self._workspaces: Dict[str, Workspace] = {}
        self._active_workspace_id: str = "default"
        self._load_from_db()
        if not self._workspaces:
            self.create_workspace(
                name="My Workspace",
                description="Default learning workspace for indexed lecture videos.",
                icon="psychology",
                workspace_id="default"
            )
        if self._workspaces and self._active_workspace_id not in self._workspaces:
            self._active_workspace_id = list(self._workspaces.keys())[0]

    def _load_from_db(self) -> None:
        if not engine or not Session or not select:
            return
        try:
            with Session(engine) as session:
                statement = select(WorkspaceTable).order_by(WorkspaceTable.last_accessed_at.desc())
                records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
                for rec in records:
                    media_statement = select(MediaItemTable.id).where(MediaItemTable.workspace_id == rec.id)
                    media_ids = list(session.scalars(media_statement).all() if hasattr(session, "scalars") else session.exec(media_statement).all())
                    ws = Workspace(
                        id=rec.id,
                        name=rec.name,
                        description=rec.description,
                        icon=rec.icon,
                        is_pinned=getattr(rec, "is_pinned", False),
                        is_archived=getattr(rec, "is_archived", False),
                        last_accessed_at=getattr(rec, "last_accessed_at", rec.updated_at),
                        media_item_ids=media_ids,
                        created_at=rec.created_at,
                        updated_at=rec.updated_at
                    )
                    self._workspaces[ws.id] = ws
        except Exception:
            pass

    def get_active_workspace_id(self) -> str:
        if self._active_workspace_id not in self._workspaces and self._workspaces:
            self._active_workspace_id = list(self._workspaces.keys())[0]
        return self._active_workspace_id

    def set_active_workspace_id(self, workspace_id: str) -> bool:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return False
        self._active_workspace_id = workspace_id
        self.touch_last_accessed(workspace_id)
        return True

    def create_workspace(
        self,
        name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        workspace_id: Optional[str] = None,
        is_pinned: bool = False,
        is_archived: bool = False
    ) -> Workspace:
        ws_id = workspace_id or f"ws_{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        workspace = Workspace(
            id=ws_id,
            name=name,
            description=description,
            icon=icon,
            is_pinned=is_pinned,
            is_archived=is_archived,
            last_accessed_at=now,
            created_at=now,
            updated_at=now
        )
        self._workspaces[ws_id] = workspace
        self._active_workspace_id = ws_id

        if engine and Session:
            try:
                with Session(engine) as session:
                    db_ws = session.get(WorkspaceTable, ws_id)
                    if not db_ws:
                        db_ws = WorkspaceTable(
                            id=ws_id,
                            name=name,
                            description=description,
                            icon=icon,
                            is_pinned=is_pinned,
                            is_archived=is_archived,
                            last_accessed_at=now,
                            created_at=now,
                            updated_at=now
                        )
                        session.add(db_ws)
                    else:
                        db_ws.name = name
                        db_ws.description = description
                        db_ws.icon = icon
                        db_ws.is_pinned = is_pinned
                        db_ws.is_archived = is_archived
                        db_ws.last_accessed_at = now
                        db_ws.updated_at = now
                    session.commit()
            except Exception:
                pass

        return workspace

    def update_workspace(
        self,
        workspace_id: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        is_pinned: Optional[bool] = None,
        is_archived: Optional[bool] = None
    ) -> Optional[Workspace]:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return None

        if name is not None:
            ws.name = name
        if description is not None:
            ws.description = description
        if icon is not None:
            ws.icon = icon
        if is_pinned is not None:
            ws.is_pinned = is_pinned
        if is_archived is not None:
            ws.is_archived = is_archived

        ws.updated_at = datetime.utcnow()

        if engine and Session:
            try:
                with Session(engine) as session:
                    db_ws = session.get(WorkspaceTable, workspace_id)
                    if db_ws:
                        if name is not None:
                            db_ws.name = name
                        if description is not None:
                            db_ws.description = description
                        if icon is not None:
                            db_ws.icon = icon
                        if is_pinned is not None:
                            db_ws.is_pinned = is_pinned
                        if is_archived is not None:
                            db_ws.is_archived = is_archived
                        db_ws.updated_at = ws.updated_at
                        session.commit()
            except Exception:
                pass

        return ws

    def delete_workspace(self, workspace_id: str) -> bool:
        if workspace_id not in self._workspaces:
            return False

        # If deleting active workspace, switch active to another workspace first
        if self._active_workspace_id == workspace_id:
            remaining = [wid for wid in self._workspaces.keys() if wid != workspace_id]
            if remaining:
                self._active_workspace_id = remaining[0]
            else:
                # Re-create a default workspace if no workspaces left
                new_def = self.create_workspace(
                    name="Default Learning Workspace",
                    description="Auto-created default workspace.",
                    icon="psychology",
                    workspace_id="default"
                )
                self._active_workspace_id = new_def.id

        del self._workspaces[workspace_id]

        if engine and Session and select:
            try:
                with Session(engine) as session:
                    # Cascade delete SQLite records for this workspace
                    for table in [
                        ChatMessageTable, ChatSessionTable, TranscriptChunkTable,
                        MediaItemTable, ProcessingLogTable, KnowledgeConceptTable,
                        KnowledgeRelationTable
                    ]:
                        stmt = select(table).where(getattr(table, "workspace_id") == workspace_id)
                        recs = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
                        for r in recs:
                            session.delete(r)
                    
                    db_ws = session.get(WorkspaceTable, workspace_id)
                    if db_ws:
                        session.delete(db_ws)

                    session.commit()
            except Exception:
                pass

        self._application_cache.delete_prefix(f"kg:ws:{workspace_id}:")
        self._application_cache.delete_prefix(f"rag:{workspace_id}:")
        self._persistent_cache.delete_prefix(f"llm:ws:{workspace_id}:")

        return True

    def touch_last_accessed(self, workspace_id: str) -> None:
        ws = self._workspaces.get(workspace_id)
        if ws:
            now = datetime.utcnow()
            ws.last_accessed_at = now
            if engine and Session:
                try:
                    with Session(engine) as session:
                        db_ws = session.get(WorkspaceTable, workspace_id)
                        if db_ws:
                            db_ws.last_accessed_at = now
                            session.commit()
                except Exception:
                    pass

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        ws = self._workspaces.get(workspace_id)
        if ws and engine and Session and select:
            try:
                with Session(engine) as session:
                    media_statement = select(MediaItemTable.id).where(MediaItemTable.workspace_id == workspace_id)
                    ws.media_item_ids = list(session.scalars(media_statement).all() if hasattr(session, "scalars") else session.exec(media_statement).all())
            except Exception:
                pass
        return ws

    def list_workspaces(self, include_archived: bool = True) -> List[Workspace]:
        self._load_from_db()
        workspaces = list(self._workspaces.values())
        if not include_archived:
            workspaces = [w for w in workspaces if not w.is_archived]
        return sorted(workspaces, key=lambda w: (not w.is_pinned, w.last_accessed_at or w.created_at), reverse=True)

    def add_media_to_workspace(self, workspace_id: str, media_id: str) -> bool:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return False
        if media_id not in ws.media_item_ids:
            ws.media_item_ids.append(media_id)
        return True

