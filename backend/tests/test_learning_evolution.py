import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import WorkspaceTable

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

def test_workspace_learning_settings_api():
    init_db()
    client = TestClient(app)
    ws_id = "test_ws_evolution_1"

    # Create workspace row
    with Session(engine) as session:
        ws = session.get(WorkspaceTable, ws_id)
        if not ws:
            session.add(WorkspaceTable(id=ws_id, name="Test Evolution WS"))
            session.commit()

    # GET default settings
    res = client.get(f"/api/v1/learning/workspaces/{ws_id}/settings")
    assert res.status_code == 200
    data = res.json()
    assert data["auto_evolve_flashcards"] is True
    assert data["flashcard_target_budget_per_media"] == 20

    # PATCH settings
    patch_res = client.patch(
        f"/api/v1/learning/workspaces/{ws_id}/settings",
        json={
            "auto_evolve_flashcards": True,
            "flashcard_target_budget_per_media": 30,
            "auto_evolve_quizzes": False,
            "quiz_target_budget_per_media": 10,
        }
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["flashcard_target_budget_per_media"] == 30
    assert updated_data["auto_evolve_quizzes"] is False
