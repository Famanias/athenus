from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from app.domain.workspace.entities import Workspace
from app.domain.workspace.workspace_service import WorkspaceService

router = APIRouter()
workspace_service = WorkspaceService()

def ensure_default_workspace():
    """Ensure at least one default workspace exists."""
    workspaces = workspace_service.list_workspaces()
    if not workspaces:
        workspace_service.create_workspace(
            name="Machine Learning & Deep Learning",
            description="Default learning workspace for indexed lecture videos.",
            icon="psychology"
        )

class CreateWorkspaceRequest(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    media_item_ids: List[str]

@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(request: CreateWorkspaceRequest):
    ws = workspace_service.create_workspace(
        name=request.name,
        description=request.description,
        icon=request.icon
    )
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        icon=ws.icon,
        media_item_ids=ws.media_item_ids
    )

@router.get("/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces():
    ensure_default_workspace()
    workspaces = workspace_service.list_workspaces()
    return [
        WorkspaceResponse(
            id=w.id,
            name=w.name,
            description=w.description,
            icon=w.icon,
            media_item_ids=w.media_item_ids
        )
        for w in workspaces
    ]

@router.get("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def get_workspace(workspace_id: str):
    ensure_default_workspace()
    ws = workspace_service.get_workspace(workspace_id)
    if not ws:
        # If 'default' is requested, attempt lookup of default workspace
        workspaces = workspace_service.list_workspaces()
        if workspaces:
            ws = workspaces[0]
        else:
            raise HTTPException(status_code=404, detail="Workspace not found")

    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        icon=ws.icon,
        media_item_ids=ws.media_item_ids
    )
