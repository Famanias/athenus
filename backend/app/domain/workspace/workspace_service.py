from typing import List, Optional, Dict
import uuid
from app.domain.workspace.entities import Workspace
from app.infrastructure.db.models import WorkspaceTable, MediaItemTable
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class WorkspaceService:
    """Domain service managing workspace lifecycle and collections, backed by SQLite."""

    def __init__(self) -> None:
        self._workspaces: Dict[str, Workspace] = {}
        self._load_from_db()
        if not self._workspaces:
            self.create_workspace(
                name="Machine Learning & Deep Learning",
                description="Default learning workspace for indexed lecture videos.",
                icon="psychology",
                workspace_id="default"
            )

    def _load_from_db(self) -> None:
        if not engine or not Session or not select:
            return
        try:
            with Session(engine) as session:
                statement = select(WorkspaceTable)
                records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
                for rec in records:
                    media_statement = select(MediaItemTable.id).where(MediaItemTable.workspace_id == rec.id)
                    media_ids = list(session.scalars(media_statement).all() if hasattr(session, "scalars") else session.exec(media_statement).all())
                    ws = Workspace(
                        id=rec.id,
                        name=rec.name,
                        description=rec.description,
                        icon=rec.icon,
                        media_item_ids=media_ids
                    )
                    self._workspaces[ws.id] = ws
        except Exception:
            pass

    def create_workspace(
        self,
        name: str,
        description: Optional[str] = None,
        icon: Optional[str] = None,
        workspace_id: Optional[str] = None
    ) -> Workspace:
        ws_id = workspace_id or f"ws_{uuid.uuid4().hex[:8]}"
        workspace = Workspace(id=ws_id, name=name, description=description, icon=icon)
        self._workspaces[ws_id] = workspace

        if engine and Session:
            try:
                with Session(engine) as session:
                    db_ws = session.get(WorkspaceTable, ws_id)
                    if not db_ws:
                        db_ws = WorkspaceTable(
                            id=ws_id,
                            name=name,
                            description=description,
                            icon=icon
                        )
                        session.add(db_ws)
                    else:
                        db_ws.name = name
                        db_ws.description = description
                        db_ws.icon = icon
                    session.commit()
            except Exception:
                pass

        return workspace

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

    def list_workspaces(self) -> List[Workspace]:
        self._load_from_db()
        return list(self._workspaces.values())

    def add_media_to_workspace(self, workspace_id: str, media_id: str) -> bool:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return False
        if media_id not in ws.media_item_ids:
            ws.media_item_ids.append(media_id)
        return True
