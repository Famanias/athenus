from fastapi.testclient import TestClient
from app.main import app
from app.domain.ai.capabilities import ITextGenerationCapability, IEmbeddingCapability, TextGenerationRequest, TextGenerationResponse
from app.domain.ai.model_registry import ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.service_bus import AIServiceBus
from app.application.services.workspace_intelligence import WorkspaceIntelligenceManager
from app.presentation.api.v1.chat import get_intelligence_manager
from typing import List


class _MockTextAdapter(ITextGenerationCapability):
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(
            text="The Jacobian matrix represents partial derivatives of a vector-valued function.",
            prompt_tokens=30,
            completion_tokens=15
        )

    async def stream(self, request: TextGenerationRequest):
        yield "The Jacobian matrix represents partial derivatives."


class _MockEmbeddingAdapter(IEmbeddingCapability):
    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        return [[0.01 * (i + 1) for i in range(384)] for _ in texts]

    async def embed_query(self, query: str) -> List[float]:
        return [0.01 * (i + 1) for i in range(384)]


def _mock_intelligence_manager() -> WorkspaceIntelligenceManager:
    registry = ModelRegistry()
    router = ProviderRouter(registry)
    bus = AIServiceBus(registry, router)
    bus.register_text_adapter("ollama", _MockTextAdapter())
    bus.register_embedding_adapter("sentence_transformers", _MockEmbeddingAdapter())
    return WorkspaceIntelligenceManager(bus)


def test_session_lifecycle_and_lazy_creation():
    app.dependency_overrides[get_intelligence_manager] = _mock_intelligence_manager
    try:
        client = TestClient(app)

        # 1. Create Workspace
        ws_res = client.post("/api/v1/workspaces", json={
            "name": "Robotics Workspace",
            "description": "Kinematics and Control"
        })
        assert ws_res.status_code == 200
        ws_id = ws_res.json()["id"]

        # 2. Explicit Session Creation
        sess_res = client.post(f"/api/v1/workspaces/{ws_id}/sessions", json={
            "title": "Forward Kinematics Session"
        })
        assert sess_res.status_code == 200
        sess_data = sess_res.json()
        sess_id = sess_data["id"]
        assert sess_data["title"] == "Forward Kinematics Session"

        # 3. List Sessions for Workspace
        list_res = client.get(f"/api/v1/workspaces/{ws_id}/sessions")
        assert list_res.status_code == 200
        sessions = list_res.json()
        assert any(s["id"] == sess_id for s in sessions)

        # 4. Chat Query with Explicit Session ID
        query_res = client.post("/api/v1/chat/query", json={
            "query": "What is the Jacobian matrix?",
            "workspace_id": ws_id,
            "session_id": sess_id
        })
        assert query_res.status_code == 200
        assert query_res.json()["session_id"] == sess_id

        # 5. Fetch Session History
        hist_res = client.get(f"/api/v1/chat/history?workspace_id={ws_id}&session_id={sess_id}")
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) == 2
        assert history[0]["content"] == "What is the Jacobian matrix?"

        # 6. Lazy Session Creation (no session_id provided)
        lazy_query = client.post("/api/v1/chat/query", json={
            "query": "Explain Inverse Kinematics",
            "workspace_id": ws_id
        })
        assert lazy_query.status_code == 200
        new_sess_id = lazy_query.json()["session_id"]
        assert new_sess_id != sess_id

        # Verify new session appeared in session list with preview_text
        list_after = client.get(f"/api/v1/workspaces/{ws_id}/sessions").json()
        lazy_sess = next((s for s in list_after if s["id"] == new_sess_id), None)
        assert lazy_sess is not None
        assert lazy_sess["preview_text"] == "Explain Inverse Kinematics"

        # 7. Delete Session
        del_res = client.delete(f"/api/v1/sessions/{sess_id}")
        assert del_res.status_code == 200
        assert del_res.json()["status"] == "ok"
    finally:
        app.dependency_overrides.pop(get_intelligence_manager, None)
