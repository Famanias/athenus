import os
import tempfile
import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings
from app.domain.settings.settings_service import SettingsService
from app.infrastructure.db.session import init_db

client = TestClient(app)


def _setup_ollama_dir(tmp_dir: str) -> str:
    manifest_dir = os.path.join(tmp_dir, "manifests", "registry.ollama.ai", "library", "phi3")
    os.makedirs(manifest_dir, exist_ok=True)
    with open(os.path.join(manifest_dir, "mini"), "w") as f:
        f.write('{"schemaVersion": 2}')
    return tmp_dir


def test_patch_provider_settings_preserves_api_key_and_merges():
    init_db()
    SettingsService().update_settings({"selected_ollama_model": None})

    # Seed an API key via full PUT
    put_res = client.put(
        "/api/v1/settings/providers",
        json={
            "default_llm": "groq",
            "selected_ollama_model": None,
            "default_stt": "faster_whisper",
            "gpu_acceleration": True,
            "api_key": "sk-test-123",
        },
    )
    assert put_res.status_code == 200
    assert put_res.json()["api_key"] == "sk-test-123"

    # PATCH only provider + model -> api_key and unrelated fields preserved
    patch_res = client.patch(
        "/api/v1/settings/providers",
        json={"default_llm": "ollama", "selected_ollama_model": "phi3:mini"},
    )
    assert patch_res.status_code == 200
    data = patch_res.json()
    assert data["default_llm"] == "ollama"
    assert data["selected_ollama_model"] == "phi3:mini"
    assert data["api_key"] == "sk-test-123"
    assert data["gpu_acceleration"] is True
    assert data["default_stt"] == "faster_whisper"


def test_patch_provider_settings_explicit_api_key_update():
    init_db()
    res = client.patch("/api/v1/settings/providers", json={"api_key": "sk-new-key"})
    assert res.status_code == 200
    assert res.json()["api_key"] == "sk-new-key"


def test_patch_provider_settings_invalid_provider():
    init_db()
    res = client.patch("/api/v1/settings/providers", json={"default_llm": "bogus"})
    assert res.status_code == 422


def test_provider_catalog_lists_ollama_models_and_active_selection():
    init_db()
    with tempfile.TemporaryDirectory() as tmp_dir:
        models_dir = _setup_ollama_dir(tmp_dir)
        SettingsService().update_settings({
            "ollama_models_dir": models_dir,
            "selected_ollama_model": "phi3:mini",
            "default_llm": "ollama",
        })

        res = client.get("/api/v1/settings/providers/catalog")
        assert res.status_code == 200
        data = res.json()
        assert data["active"]["provider"] == "ollama"
        assert data["active"]["model"] == "phi3:mini"

        by_id = {p["id"]: p for p in data["providers"]}
        assert "ollama" in by_id
        assert "phi3:mini" in [m["id"] for m in by_id["ollama"]["models"]]
        assert "groq" in by_id
        assert len(by_id["groq"]["models"]) > 0
        assert "openrouter" in by_id
        assert len(by_id["openrouter"]["models"]) > 0


def test_provider_catalog_active_reflects_cloud_provider():
    init_db()
    SettingsService().update_settings({"default_llm": "groq", "selected_ollama_model": None})

    res = client.get("/api/v1/settings/providers/catalog")
    assert res.status_code == 200
    data = res.json()
    assert data["active"]["provider"] == "groq"
    assert data["active"]["model"] is not None


def test_ollama_adapter_resolves_selected_model():
    from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter

    class FakeSettings:
        def __init__(self, model):
            self.selected_ollama_model = model

    class FakeSettingsService:
        def __init__(self, model):
            self._settings = FakeSettings(model)

        def get_settings(self):
            return self._settings

    adapter = OllamaTextGenAdapter(default_model="llama3:8b", settings_service=FakeSettingsService("phi3:mini"))
    assert adapter._resolve_model() == "phi3:mini"

    adapter2 = OllamaTextGenAdapter(default_model="llama3:8b", settings_service=FakeSettingsService(None))
    assert adapter2._resolve_model() == "llama3:8b"
