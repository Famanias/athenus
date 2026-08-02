from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_settings_providers():
    response = client.get("/api/v1/settings/providers")
    assert response.status_code == 200
    data = response.json()
    assert "default_llm" in data
    assert "default_stt" in data
    assert "gpu_acceleration" in data
    assert data["status"] == "ok"

def test_put_settings_providers_valid():
    payload = {
        "default_llm": "groq",
        "default_stt": "faster-whisper",
        "gpu_acceleration": False
    }
    response = client.put("/api/v1/settings/providers", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["default_llm"] == "groq"
    assert data["gpu_acceleration"] is False

def test_put_settings_providers_invalid_llm():
    payload = {
        "default_llm": "invalid_provider_name",
        "default_stt": "faster-whisper",
        "gpu_acceleration": True
    }
    response = client.put("/api/v1/settings/providers", json=payload)
    assert response.status_code == 422
