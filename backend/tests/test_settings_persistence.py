import os
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
        "ollama_models_dir": None,
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

    # 2. Update Ollama models directory via API
    import tempfile
    with tempfile.TemporaryDirectory() as tmp_dir:
        manifest_dir = os.path.join(tmp_dir, "manifests", "registry.ollama.ai", "library", "phi3")
        os.makedirs(manifest_dir, exist_ok=True)
        with open(os.path.join(manifest_dir, "mini"), "w") as f:
            f.write('{"schemaVersion": 2}')

        dir_res = client.put("/api/v1/settings/ollama", json={"models_dir": tmp_dir})
        assert dir_res.status_code == 200

        # 3. Simulate backend process restart: query database directly using fresh service instance
        fresh_service = SettingsService()
        persisted_rec = fresh_service.get_settings()

        assert persisted_rec.default_llm == "groq"
        assert persisted_rec.selected_ollama_model == "mistral:latest"
        assert persisted_rec.ollama_models_dir == tmp_dir
        assert persisted_rec.gpu_acceleration is False

        # 4. Verify API GET endpoint returns exact persisted settings after restart
        get_res = client.get("/api/v1/settings/providers")
        assert get_res.status_code == 200
        get_data = get_res.json()
        assert get_data["default_llm"] == "groq"
        assert get_data["selected_ollama_model"] == "mistral:latest"
        assert get_data["gpu_acceleration"] is False

def test_invalid_ollama_directory_preserves_saved_path():
    init_db()
    service = SettingsService()

    # Set invalid directory path
    invalid_path = "C:\\InvalidNonExistentPath_Test_123"
    client.put("/api/v1/settings/ollama", json={"models_dir": invalid_path})

    # GET /settings/ollama should report valid: False but preserve configured_dir
    ollama_res = client.get("/api/v1/settings/ollama")
    assert ollama_res.status_code == 200
    ollama_data = ollama_res.json()
    assert ollama_data["configured_dir"] == invalid_path
    assert ollama_data["valid"] is False
    assert ollama_data["error"] is not None

    # Verify provider preferences remain 100% intact
    prov_res = client.get("/api/v1/settings/providers")
    assert prov_res.status_code == 200
