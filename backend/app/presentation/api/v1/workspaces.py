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
            name="My Workspace",
            description="Default learning workspace for indexed lecture videos.",
            icon="psychology",
            workspace_id="default"
        )

class CreateWorkspaceRequest(BaseModel):
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_pinned: bool = False
    is_archived: bool = False

class UpdateWorkspaceRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    is_pinned: Optional[bool] = None
    is_archived: Optional[bool] = None

class WorkspaceResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    is_pinned: bool = False
    is_archived: bool = False
    last_accessed_at: Optional[str] = None
    media_item_ids: List[str]

class ActiveWorkspaceResponse(BaseModel):
    active_workspace_id: str

def _to_workspace_response(ws: Workspace) -> WorkspaceResponse:
    last_acc = ws.last_accessed_at.isoformat() if ws.last_accessed_at else None
    return WorkspaceResponse(
        id=ws.id,
        name=ws.name,
        description=ws.description,
        icon=ws.icon,
        is_pinned=ws.is_pinned,
        is_archived=ws.is_archived,
        last_accessed_at=last_acc,
        media_item_ids=ws.media_item_ids
    )

@router.post("/workspaces", response_model=WorkspaceResponse)
def create_workspace(request: CreateWorkspaceRequest):
    ws = workspace_service.create_workspace(
        name=request.name,
        description=request.description,
        icon=request.icon,
        is_pinned=request.is_pinned,
        is_archived=request.is_archived
    )
    return _to_workspace_response(ws)

@router.get("/workspaces", response_model=List[WorkspaceResponse])
def list_workspaces(include_archived: bool = True):
    ensure_default_workspace()
    workspaces = workspace_service.list_workspaces(include_archived=include_archived)
    return [_to_workspace_response(w) for w in workspaces]

@router.get("/workspaces/active", response_model=ActiveWorkspaceResponse)
def get_active_workspace():
    ensure_default_workspace()
    active_id = workspace_service.get_active_workspace_id()
    return ActiveWorkspaceResponse(active_workspace_id=active_id)

@router.post("/workspaces/{workspace_id}/activate", response_model=ActiveWorkspaceResponse)
def activate_workspace(workspace_id: str):
    ensure_default_workspace()
    success = workspace_service.set_active_workspace_id(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ActiveWorkspaceResponse(active_workspace_id=workspace_id)

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
    workspace_service.touch_last_accessed(ws.id)
    return _to_workspace_response(ws)

@router.patch("/workspaces/{workspace_id}", response_model=WorkspaceResponse)
def update_workspace(workspace_id: str, request: UpdateWorkspaceRequest):
    ws = workspace_service.update_workspace(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        icon=request.icon,
        is_pinned=request.is_pinned,
        is_archived=request.is_archived
    )
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return _to_workspace_response(ws)

@router.delete("/workspaces/{workspace_id}")
def delete_workspace(workspace_id: str):
    success = workspace_service.delete_workspace(workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return {"status": "ok", "deleted_workspace_id": workspace_id, "active_workspace_id": workspace_service.get_active_workspace_id()}

