import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_get_ollama_settings_default():
    response = client.get("/api/v1/settings/ollama")
    assert response.status_code == 200
    data = response.json()
    assert data["valid"] is False
    assert data["models_count"] == 0

def test_put_ollama_directory_invalid():
    response = client.put("/api/v1/settings/ollama", json={"models_dir": "C:\\NonExistent_Test_Folder_XYZ"})
    assert response.status_code == 400
    assert "does not exist" in response.json()["detail"]

def test_put_and_scan_ollama_directory_valid():
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Construct valid mock Ollama models directory
        manifest_dir = os.path.join(tmp_dir, "manifests", "registry.ollama.ai", "library", "phi3")
        os.makedirs(manifest_dir, exist_ok=True)
        with open(os.path.join(manifest_dir, "mini"), "w") as f:
            f.write('{"schemaVersion": 2}')

        put_res = client.put("/api/v1/settings/ollama", json={"models_dir": tmp_dir})
        assert put_res.status_code == 200
        put_data = put_res.json()
        assert put_data["valid"] is True
        assert put_data["models_count"] == 1
        assert put_data["models"][0]["full_id"] == "phi3:mini"

        # Test POST rescan endpoint
        scan_res = client.post("/api/v1/settings/ollama/scan")
        assert scan_res.status_code == 200
        scan_data = scan_res.json()
        assert scan_data["valid"] is True
        assert scan_data["models_count"] == 1
        assert scan_data["models"][0]["full_id"] == "phi3:mini"

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
