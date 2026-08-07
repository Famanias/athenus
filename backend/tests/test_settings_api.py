import pytest
import asyncio
from fastapi.testclient import TestClient
from app.main import app, ai_service_bus, llm_provider_registry, config_resolver
from app.domain.ai.service_bus import UnsupportedCapabilityError
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO

class NoVisionProvider(BaseLLMProvider):
    provider_id = "test_novision"
    name = "No Vision Provider"
    is_local = True

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(supports_vision=False)

    async def list_models(self, force_refresh: bool = False):
        return [LLMModelMetadataDTO(id="test-model", name="Test Model")]

    async def generate(self, request): pass
    async def stream(self, request): yield ""


def test_ai_service_bus_capability_checked_dispatch():
    no_vis = NoVisionProvider()
    llm_provider_registry.register(no_vis)
    config_resolver.set_active_provider_id("test_novision")

    # Regular capability retrieval succeeds
    cap = ai_service_bus.get_text_capability()
    assert cap.provider_id == "test_novision"

    # Capability check for unsupported feature raises UnsupportedCapabilityError
    with pytest.raises(UnsupportedCapabilityError) as exc_info:
        ai_service_bus.get_text_capability(required_capabilities=["vision"])
    assert "does not support Vision capabilities" in str(exc_info.value)

    # Restore default active provider
    config_resolver.set_active_provider_id("ollama")


def test_settings_provider_catalog_endpoint():
    client = TestClient(app)
    response = client.get("/api/v1/settings/providers/catalog")
    assert response.status_code == 200
    data = response.json()

    assert "active" in data
    assert "providers" in data
    assert len(data["providers"]) >= 3

    provider_ids = [p["id"] for p in data["providers"]]
    assert "ollama" in provider_ids
    assert "openrouter" in provider_ids
    assert "groq" in provider_ids
    assert "anthropic" in provider_ids


def test_settings_provider_test_connection_endpoint():
    client = TestClient(app)
    response = client.post("/api/v1/settings/providers/ollama/test")
    assert response.status_code == 200
    data = response.json()

    assert data["provider_id"] == "ollama"
    assert "is_available" in data
    assert "is_configured" in data

    # Testing non-registered provider returns 404
    bad_resp = client.post("/api/v1/settings/providers/non_existent_provider_xyz/test")
    assert bad_resp.status_code == 404
