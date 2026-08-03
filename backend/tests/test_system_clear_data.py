import os
from fastapi.testclient import TestClient
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import (
    MediaItemTable,
    ChatMessageTable,
    WorkspaceTable,
)
from app.application.events.progress_store import progress_store
from app.main import app

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def test_system_clear_data_factory_reset():
    init_db()
    client = TestClient(app)

    uploads_dir = os.path.join(".", "data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    dummy_file = os.path.join(uploads_dir, "test_purge.mp4")
    with open(dummy_file, "w") as f:
        f.write("dummy video binary content")

    assert os.path.exists(dummy_file)

    # 1. Populate database records
    with Session(engine) as session:
        m_item = MediaItemTable(
            id="med_purge_1",
            workspace_id="default",
            title="Test Video to Delete",
            file_path=dummy_file
        )
        session.add(m_item)
        c_msg = ChatMessageTable(
            id="msg_purge_1",
            session_id="sess_1",
            workspace_id="default",
            sender="user",
            content="Delete me"
        )
        session.add(c_msg)
        session.commit()

    # Populate progress store
    progress_store.record_stage_progress("med_purge_1", "upload", 100, "Uploaded", "completed")

    # 2. Invoke POST /api/v1/system/clear-data
    res = client.post("/api/v1/system/clear-data")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"

    # 3. Assert database records purged
    with Session(engine) as session:
        m_records = session.scalars(select(MediaItemTable)).all() if hasattr(session, "scalars") else session.exec(select(MediaItemTable)).all()
        assert len(m_records) == 0

        msg_records = session.scalars(select(ChatMessageTable)).all() if hasattr(session, "scalars") else session.exec(select(ChatMessageTable)).all()
        assert len(msg_records) == 0

        # Assert default workspace is re-created
        ws_records = session.scalars(select(WorkspaceTable)).all() if hasattr(session, "scalars") else session.exec(select(WorkspaceTable)).all()
        assert len(ws_records) >= 1
        assert any(w.id == "default" for w in ws_records)

    # 4. Assert disk uploads purged
    assert not os.path.exists(dummy_file)

    # 5. Assert progress store reset
    assert len(progress_store._snapshots) == 0
