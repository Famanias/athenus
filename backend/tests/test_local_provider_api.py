import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_list_local_providers_endpoint():
    response = client.get("/api/v1/settings/providers/local")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert any(p["id"] == "ollama" for p in data)

def test_get_local_provider_status_endpoint():
    response = client.get("/api/v1/settings/providers/local/ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["provider_id"] == "ollama"
    assert data["label"] == "Ollama"
    assert "connected" in data

def test_get_local_provider_models_endpoint():
    response = client.get("/api/v1/settings/providers/local/ollama/models")
    assert response.status_code == 200
    data = response.json()
    assert data["provider_id"] == "ollama"
    assert "models" in data
    assert "count" in data

def test_get_unknown_local_provider_404():
    response = client.get("/api/v1/settings/providers/local/unknown_provider_xyz")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]
