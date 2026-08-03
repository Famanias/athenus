from fastapi.testclient import TestClient
from app.application.events.progress_store import progress_store
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import ProcessingLogTable
from app.main import app

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def test_knowledge_lifecycle_processing_logs():
    init_db()
    media_id = "med_test_lifecycle_100"

    # Simulate full stage ingestion progression
    progress_store.record_stage_progress(
        media_id=media_id,
        stage="upload",
        progress=100,
        message="Media uploaded successfully.",
        status="processing"
    )
    progress_store.record_stage_progress(
        media_id=media_id,
        stage="audio_extraction",
        progress=25,
        message="Extracting audio track...",
        status="processing"
    )
    progress_store.record_stage_progress(
        media_id=media_id,
        stage="transcription",
        progress=60,
        message="Transcribing speech with Whisper ASR...",
        status="processing"
    )
    progress_store.record_stage_progress(
        media_id=media_id,
        stage="vector_indexing",
        progress=100,
        message="Indexed chunks into Embedded Qdrant.",
        status="completed"
    )

    # 1. Direct SQLite database query assertion
    with Session(engine) as session:
        statement = select(ProcessingLogTable).where(ProcessingLogTable.media_id == media_id).order_by(ProcessingLogTable.created_at)
        records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
        assert len(records) >= 4
        stages = [r.stage for r in records]
        assert "upload" in stages
        assert "audio_extraction" in stages
        assert "transcription" in stages
        assert "vector_indexing" in stages
        assert records[-1].status == "completed"

    # 2. REST API endpoint assertion
    client = TestClient(app)
    res = client.get(f"/api/v1/media/{media_id}/history")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 4
    assert data[-1]["stage"] == "vector_indexing"
    assert data[-1]["status"] == "completed"
    assert data[-1]["progress"] == 100
