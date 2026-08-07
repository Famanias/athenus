import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.settings.settings_service import SettingsService
from app.infrastructure.db.session import init_db

client = TestClient(app)

def test_settings_persistence_across_service_reloads():
    init_db()
    service = SettingsService()
    service.update_settings({
        "default_llm": "ollama",
        "selected_ollama_model": None,
        "gpu_acceleration": True
    })

    # 1. Update settings via API
    payload = {
        "default_llm": "groq",
        "selected_ollama_model": "mistral:latest",
        "default_stt": "faster_whisper",
        "gpu_acceleration": False,
        "api_key": ""
    }
    put_res = client.put("/api/v1/settings/providers", json=payload)
    assert put_res.status_code == 200
    data = put_res.json()
    assert data["default_llm"] == "groq"
    assert data["selected_ollama_model"] == "mistral:latest"
    assert data["gpu_acceleration"] is False

    # 2. Simulate backend process restart: query database directly using fresh service instance
    fresh_service = SettingsService()
    persisted_rec = fresh_service.get_settings()

    assert persisted_rec.default_llm == "groq"
    assert persisted_rec.selected_ollama_model == "mistral:latest"
    assert persisted_rec.gpu_acceleration is False

    # 3. Verify API GET endpoint returns exact persisted settings after restart
    get_res = client.get("/api/v1/settings/providers")
    assert get_res.status_code == 200
    get_data = get_res.json()
    assert get_data["default_llm"] == "groq"
    assert get_data["selected_ollama_model"] == "mistral:latest"
    assert get_data["gpu_acceleration"] is False
