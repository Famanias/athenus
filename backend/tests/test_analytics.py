import asyncio
import uuid

from fastapi.testclient import TestClient

from app.domain.analytics.analytics_service import AnalyticsService
from app.domain.knowledge.entities import ConceptNode
from app.domain.knowledge.knowledge_graph_service import KnowledgeGraphService
from app.infrastructure.db.session import init_db
from app.infrastructure.events.event_bus import DomainEvent, EventBus
from app.main import app

client = TestClient(app)


def _seed_graph(workspace_id: str) -> None:
    service = KnowledgeGraphService()
    for idx, name in enumerate(["Overfitting", "Regularization", "Backpropagation"]):
        service.add_concept(
            ConceptNode(
                id=f"{workspace_id}_c{idx}",
                workspace_id=workspace_id,
                name=name,
                description=f"{name} explanation.",
            )
        )


def test_analytics_endpoint_returns_zero_state():
    ws = f"ws_azero_{uuid.uuid4().hex[:8]}"
    response = client.get(f"/api/v1/analytics/workspace/{ws}")
    assert response.status_code == 200
    data = response.json()
    assert data["workspace_id"] == ws
    assert data["total_concepts"] == 0
    assert data["total_quiz_attempts"] == 0


def test_quiz_attempt_event_updates_analytics():
    init_db()
    ws = f"ws_aevent_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    bus = EventBus()
    analytics = AnalyticsService(event_bus=bus, graph_service=KnowledgeGraphService())

    concept_results = {
        "q1": {"is_correct": True, "concept_id": f"{ws}_c0"},
        "q2": {"is_correct": False, "concept_id": f"{ws}_c1"},
    }
    asyncio.run(
        bus.publish(
            DomainEvent(
                event_type="QuizAttemptEvent",
                aggregate_id=ws,
                payload={
                    "workspace_id": ws,
                    "score": 50.0,
                    "correct_count": 1,
                    "total_questions": 2,
                    "time_taken": 30.0,
                    "concept_results": concept_results,
                },
            )
        )
    )

    data = analytics.get_workspace_analytics(ws)
    assert data is not None
    assert data["total_quiz_attempts"] == 1
    assert data["avg_quiz_score"] == 50.0
    assert data["total_study_seconds"] == 30.0

    mastery = analytics.get_concept_mastery(ws)
    by_id = {m["concept_id"]: m for m in mastery}
    assert f"{ws}_c0" in by_id
    assert by_id[f"{ws}_c0"]["quiz_correct"] == 1
    assert by_id[f"{ws}_c0"]["quiz_attempts"] == 1
    assert by_id[f"{ws}_c0"]["mastery_level"] > 0
    assert by_id[f"{ws}_c1"]["quiz_attempts"] == 1


def test_flashcard_review_event_updates_analytics():
    init_db()
    ws = f"ws_areview_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    bus = EventBus()
    analytics = AnalyticsService(event_bus=bus, graph_service=KnowledgeGraphService())

    asyncio.run(
        bus.publish(
            DomainEvent(
                event_type="FlashcardReviewedEvent",
                aggregate_id=ws,
                payload={
                    "workspace_id": ws,
                    "flashcard_id": "card_1",
                    "rating": 3,
                    "ease_factor": 2.5,
                    "concept_id": f"{ws}_c0",
                },
            )
        )
    )
    asyncio.run(
        bus.publish(
            DomainEvent(
                event_type="FlashcardReviewedEvent",
                aggregate_id=ws,
                payload={
                    "workspace_id": ws,
                    "flashcard_id": "card_2",
                    "rating": 4,
                    "ease_factor": 2.6,
                    "concept_id": f"{ws}_c0",
                },
            )
        )
    )

    data = analytics.get_workspace_analytics(ws)
    assert data["total_reviews"] == 2
    assert data["review_streak_days"] >= 1

    mastery = analytics.get_concept_mastery(ws)
    by_id = {m["concept_id"]: m for m in mastery}
    assert by_id[f"{ws}_c0"]["review_count"] == 2


def test_revision_recommendations():
    init_db()
    ws = f"ws_arev_{uuid.uuid4().hex[:8]}"
    _seed_graph(ws)
    bus = EventBus()
    analytics = AnalyticsService(event_bus=bus, graph_service=KnowledgeGraphService())

    asyncio.run(
        bus.publish(
            DomainEvent(
                event_type="QuizAttemptEvent",
                aggregate_id=ws,
                payload={
                    "workspace_id": ws,
                    "score": 33.3,
                    "correct_count": 1,
                    "total_questions": 3,
                    "time_taken": 20.0,
                    "concept_results": {
                        "q1": {"is_correct": False, "concept_id": f"{ws}_c0"},
                        "q2": {"is_correct": False, "concept_id": f"{ws}_c1"},
                        "q3": {"is_correct": True, "concept_id": f"{ws}_c2"},
                    },
                },
            )
        )
    )

    recommendations = analytics.recommend_revisions(ws)
    assert len(recommendations) >= 1
    assert any(r["type"] == "concept" for r in recommendations)
    low = [r for r in recommendations if r["priority"] == "high"]
    assert low, "Low-mastery concepts should be flagged high priority"


def test_analytics_summary_endpoint():
    ws = f"ws_asum_{uuid.uuid4().hex[:8]}"
    response = client.get(f"/api/v1/analytics/workspace/{ws}/summary")
    assert response.status_code == 200
    data = response.json()
    assert "workspace" in data
    assert "concept_mastery" in data
    assert "recent_activity" in data
    assert "revision_recommendations" in data
