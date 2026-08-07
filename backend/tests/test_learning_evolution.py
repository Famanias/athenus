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
    assert data["auto_evolve_flashcards"] is False
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


def test_learning_evolution_worker_analytics_only():
    """ConceptGraphUpdatedEvent must trigger analytics precomputation ONLY —
    never automatic Flashcard or Quiz generation."""
    import asyncio
    from app.domain.analytics.analytics_service import AnalyticsService
    from app.infrastructure.events.event_bus import EventBus, DomainEvent
    from app.services.workers.learning_evolution_worker import LearningEvolutionWorker

    class RecordingAnalytics(AnalyticsService):
        def __init__(self) -> None:
            super().__init__(event_bus=None)
            self.graph_updates = 0

        async def handle_graph_updated(self, event):
            self.graph_updates += 1

    bus = EventBus()
    analytics = RecordingAnalytics()
    worker = LearningEvolutionWorker(bus, analytics_service=analytics)

    async def run():
        await bus.publish(DomainEvent(
            event_type="ConceptGraphUpdatedEvent",
            aggregate_id="test_ws_worker_1",
            payload={
                "workspace_id": "test_ws_worker_1",
                "new_concept_ids": ["c1", "c2"],
            },
        ))

    asyncio.run(run())

    assert analytics.graph_updates == 1
    assert not hasattr(worker, "flashcard_service")
    assert not hasattr(worker, "quiz_service")
