from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Dict, Any
from app.domain.ai.agent_protocol import TaskContext, AgentInput
from app.domain.ai.agent_coordinator import AgentCoordinator

router = APIRouter()
agent_coordinator = AgentCoordinator()

class CoordinateTaskRequest(BaseModel):
    task_type: str
    query_text: str
    workspace_id: str = "default"

class AgentResultDTO(BaseModel):
    agent_name: str
    success: bool
    data: Dict[str, Any]

class CoordinateTaskResponse(BaseModel):
    active_agents: List[str]
    results: Dict[str, AgentResultDTO]

@router.get("/agents/list", response_model=List[str])
def list_agents():
    return agent_coordinator.list_agents()

@router.post("/agents/coordinate", response_model=CoordinateTaskResponse)
async def coordinate_agents(request: CoordinateTaskRequest):
    ctx = TaskContext(workspace_id=request.workspace_id, user_id="default_user")
    agent_input = AgentInput(task_type=request.task_type, query_text=request.query_text, context=ctx)
    
    results = await agent_coordinator.coordinate_task(agent_input)
    
    dto_results = {
        name: AgentResultDTO(agent_name=res.agent_name, success=res.success, data=res.data)
        for name, res in results.items()
    }

    return CoordinateTaskResponse(
        active_agents=agent_coordinator.list_agents(),
        results=dto_results
    )
