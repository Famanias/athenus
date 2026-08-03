from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_session_lifecycle_and_lazy_creation():
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
