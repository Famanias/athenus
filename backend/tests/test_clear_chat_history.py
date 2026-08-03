import uuid
from fastapi.testclient import TestClient
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import ChatSessionTable, ChatMessageTable
from app.main import app

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


def test_clear_chat_history_api():
    init_db()
    client = TestClient(app)
    suffix = uuid.uuid4().hex[:6]
    workspace_id = f"test_clear_ws_{suffix}"
    session_id = f"sess_clear_{suffix}"

    # 1. Seed chat messages in SQLite
    with Session(engine) as session:
        sess = ChatSessionTable(id=session_id, workspace_id=workspace_id, title="Test Session")
        session.add(sess)
        msg1 = ChatMessageTable(id=f"msg_c1_{suffix}", session_id=session_id, workspace_id=workspace_id, sender="user", content="Hello")
        msg2 = ChatMessageTable(id=f"msg_c2_{suffix}", session_id=session_id, workspace_id=workspace_id, sender="assistant", content="Hi there!")
        session.add(msg1)
        session.add(msg2)
        session.commit()

    # 2. Verify messages exist via GET
    get_res = client.get(f"/api/v1/chat/history?workspace_id={workspace_id}")
    assert get_res.status_code == 200
    assert len(get_res.json()) >= 2

    # 3. Call DELETE /api/v1/chat/history
    del_res = client.delete(f"/api/v1/chat/history?workspace_id={workspace_id}")
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "ok"
    assert del_res.json()["deleted_count"] >= 2

    # 4. Verify history is empty
    get_res_after = client.get(f"/api/v1/chat/history?workspace_id={workspace_id}")
    assert get_res_after.status_code == 200
    assert len(get_res_after.json()) == 0
