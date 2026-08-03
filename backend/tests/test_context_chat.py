import uuid
from fastapi.testclient import TestClient
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import MediaItemTable, TranscriptSegmentTable
from app.main import app

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


def test_context_aware_chat_query():
    init_db()
    client = TestClient(app)

    unique_suffix = uuid.uuid4().hex[:6]
    media_id = f"med_ctx_test_{unique_suffix}"
    workspace_id = "default"

    # 1. Populate test media item and transcript segments in SQLite
    with Session(engine) as session:
        m_item = MediaItemTable(
            id=media_id,
            workspace_id=workspace_id,
            title="Lecture on Backpropagation and Gradient Descent",
            file_path="./data/uploads/lecture_test.mp4"
        )
        session.add(m_item)

        # Add 3 segments around 754s (12:34)
        seg1 = TranscriptSegmentTable(
            media_id=media_id,
            start_time=730.0,  # 12:10
            end_time=750.0,    # 12:30
            text="First we calculate the activation function derivatives using the chain rule."
        )
        seg2 = TranscriptSegmentTable(
            media_id=media_id,
            start_time=751.0,  # 12:31
            end_time=770.0,    # 12:50
            text="Next we multiply the error vector by the derivative to update weights."
        )
        seg3 = TranscriptSegmentTable(
            media_id=media_id,
            start_time=771.0,  # 12:51
            end_time=790.0,    # 13:10
            text="This gradient descent step ensures the loss function decreases monotonically."
        )
        session.add(seg1)
        session.add(seg2)
        session.add(seg3)
        session.commit()

    # 2. Execute POST /api/v1/chat/query with current_timestamp=754.0 (12:34)
    response = client.post(
        "/api/v1/chat/query",
        json={
            "query": "Can you explain why we multiply by the derivative here?",
            "workspace_id": "default",
            "media_id": media_id,
            "current_timestamp": 754.0,
            "selected_text": "multiply the error vector by the derivative"
        }
    )

    assert response.status_code == 200
    data = response.json()

    # 3. Assert context_provenance metadata is present and accurate
    assert "context_provenance" in data
    prov = data["context_provenance"]
    assert prov is not None
    assert prov["media_title"] == "Lecture on Backpropagation and Gradient Descent"
    assert prov["timestamp"] == "12:34"
    assert prov["timestamp_range"] == "12:10 - 13:10"
    assert prov["segment_count"] == 3
    assert prov["selected_text"] == "multiply the error vector by the derivative"
    assert "answer" in data
