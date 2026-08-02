from typing import List, Optional, Dict
import uuid
from app.domain.workspace.entities import Workspace

class WorkspaceService:
    """Domain service managing workspace lifecycle and collections."""
    
    def __init__(self) -> None:
        self._workspaces: Dict[str, Workspace] = {
            "default": Workspace(id="default", name="Default Workspace", description="Default user workspace")
        }

    def create_workspace(self, name: str, description: Optional[str] = None, icon: Optional[str] = None) -> Workspace:
        ws_id = f"ws_{uuid.uuid4().hex[:8]}"
        workspace = Workspace(id=ws_id, name=name, description=description, icon=icon)
        self._workspaces[ws_id] = workspace
        return workspace

    def get_workspace(self, workspace_id: str) -> Optional[Workspace]:
        return self._workspaces.get(workspace_id)

    def list_workspaces(self) -> List[Workspace]:
        return list(self._workspaces.values())

    def add_media_to_workspace(self, workspace_id: str, media_id: str) -> bool:
        ws = self.get_workspace(workspace_id)
        if not ws:
            return False
        if media_id not in ws.media_item_ids:
            ws.media_item_ids.append(media_id)
        return True
