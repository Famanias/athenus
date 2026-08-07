import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.domain.settings.settings_service import SettingsService
from app.infrastructure.db.session import init_db

client = TestClient(app)


def test_active_models_roundtrip_json():
    init_db()
    SettingsService().update_settings({
        "active_models": {"openai": "gpt-4o", "groq": "llama-3.1-8b-instant"},
    })
    rec = SettingsService().get_settings()
    assert rec.active_models["openai"] == "gpt-4o"
    assert rec.active_models["groq"] == "llama-3.1-8b-instant"


def test_patch_selected_model_persists_to_active_models():
    init_db()
    SettingsService().update_settings({"default_llm": "groq", "selected_ollama_model": None})

    res = client.patch(
        "/api/v1/settings/providers",
        json={"default_llm": "groq", "selected_model": "llama-3.1-8b-instant"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["selected_model"] == "llama-3.1-8b-instant"
    assert data["active_models"].get("groq") == "llama-3.1-8b-instant"

    # GET reflects the persisted selection for the active provider
    get_res = client.get("/api/v1/settings/providers")
    assert get_res.status_code == 200
    assert get_res.json()["selected_model"] == "llama-3.1-8b-instant"

    # Catalog active model reflects the persisted selection, not the first model
    catalog_res = client.get("/api/v1/settings/providers/catalog")
    assert catalog_res.status_code == 200
    cat = catalog_res.json()
    assert cat["active"]["provider"] == "groq"
    assert cat["active"]["model"] == "llama-3.1-8b-instant"


def test_legacy_ollama_model_backfills_active_models():
    init_db()
    SettingsService().update_settings({"default_llm": "ollama", "selected_ollama_model": "phi3:mini"})
    rec = SettingsService().get_settings()
    assert rec.active_models.get("ollama") == "phi3:mini"

    res = client.get("/api/v1/settings/providers/catalog")
    assert res.status_code == 200
    assert res.json()["active"]["model"] == "phi3:mini"


def test_cloud_adapter_resolves_persisted_model():
    from app.infrastructure.adapters.openai_compatible_adapter import OpenAICompatibleProviderAdapter

    init_db()
    SettingsService().update_settings({
        "default_llm": "groq",
        "active_models": {"groq": "llama-3.1-8b-instant"},
    })

    adapter = OpenAICompatibleProviderAdapter(
        provider_id="groq",
        name="Groq API (Cloud LPU)",
        base_url="http://localhost:9999",
        api_key="sk-test",
        default_model="llama-3.3-70b-versatile",
    )
    assert adapter._resolve_model() == "llama-3.1-8b-instant"

    # Falls back to the adapter default when no persisted selection exists
    SettingsService().update_settings({"active_models": {"groq": None}})
    assert adapter._resolve_model() == "llama-3.3-70b-versatile"
