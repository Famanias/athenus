from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_and_list_workspaces():
    response = client.post("/api/v1/workspaces", json={
        "name": "Machine Learning Workgroup",
        "description": "Deep Learning and Neural Network lectures"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Machine Learning Workgroup"
    assert "id" in data

    list_response = client.get("/api/v1/workspaces")
    assert list_response.status_code == 200
    workspaces = list_response.json()
    assert len(workspaces) >= 2

def test_workspace_crud_and_active():
    # 1. Create Workspace
    create_res = client.post("/api/v1/workspaces", json={
        "name": "Quantum Computing",
        "description": "Intro to Qubits",
        "icon": "science"
    })
    assert create_res.status_code == 200
    ws_data = create_res.json()
    ws_id = ws_data["id"]
    assert ws_data["name"] == "Quantum Computing"

    # 2. Activate Workspace
    act_res = client.post(f"/api/v1/workspaces/{ws_id}/activate")
    assert act_res.status_code == 200
    assert act_res.json()["active_workspace_id"] == ws_id

    # 3. Get Active Workspace
    get_act = client.get("/api/v1/workspaces/active")
    assert get_act.status_code == 200
    assert get_act.json()["active_workspace_id"] == ws_id

    # 4. Patch Workspace (Pin & Rename)
    patch_res = client.patch(f"/api/v1/workspaces/{ws_id}", json={
        "name": "Advanced Quantum Computing",
        "is_pinned": True
    })
    assert patch_res.status_code == 200
    patched = patch_res.json()
    assert patched["name"] == "Advanced Quantum Computing"
    assert patched["is_pinned"] is True

    # 5. Delete Workspace with safe fallback
    del_res = client.delete(f"/api/v1/workspaces/{ws_id}")
    assert del_res.status_code == 200
    del_data = del_res.json()
    assert del_data["status"] == "ok"
    assert del_data["active_workspace_id"] != ws_id

