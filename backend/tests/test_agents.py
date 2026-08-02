import asyncio
import pytest
from app.domain.ai.agent_protocol import TaskContext, AgentInput
from app.domain.ai.agent_coordinator import AgentCoordinator
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_agent_coordinator():
    async def _async_test():
        coordinator = AgentCoordinator()
        assert len(coordinator.list_agents()) == 3
        
        ctx = TaskContext(workspace_id="ws1", user_id="u1")
        inp = AgentInput(task_type="learning_plan", query_text="Learn neural networks", context=ctx)
        results = await coordinator.coordinate_task(inp)
        
        assert "planner" in results
        assert results["planner"].success is True
        assert "execution_plan" in results["planner"].data

    asyncio.run(_async_test())

def test_agents_api_endpoints():
    list_res = client.get("/api/v1/agents/list")
    assert list_res.status_code == 200
    agents = list_res.json()
    assert len(agents) >= 3

    coord_res = client.post("/api/v1/agents/coordinate", json={
        "task_type": "study_session",
        "query_text": "Study calculus prerequisites",
        "workspace_id": "default"
    })
    assert coord_res.status_code == 200
    data = coord_res.json()
    assert "results" in data
    assert "planner" in data["results"]
