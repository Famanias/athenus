import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_provider_settings_selected_ollama_model():
    from app.domain.settings.settings_service import SettingsService
    SettingsService().update_settings({"selected_ollama_model": None})

    # Initial GET provider settings
    get_res = client.get("/api/v1/settings/providers")
    assert get_res.status_code == 200
    assert get_res.json()["selected_ollama_model"] is None

    # PUT provider settings with selected_ollama_model
    put_res = client.put(
        "/api/v1/settings/providers",
        json={
            "default_llm": "ollama",
            "selected_ollama_model": "phi3:mini",
            "default_stt": "faster_whisper",
            "gpu_acceleration": True,
            "api_key": ""
        }
    )
    assert put_res.status_code == 200
    assert put_res.json()["selected_ollama_model"] == "phi3:mini"
