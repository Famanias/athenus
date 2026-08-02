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
