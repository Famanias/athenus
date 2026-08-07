import pytest
import asyncio
from typing import AsyncGenerator, List
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO
from app.domain.ai.config_resolver import ProviderConfigResolver
from app.domain.ai.provider_registry import LLMProviderRegistry

class MockLocalProvider(BaseLLMProvider):
    def __init__(self, provider_id: str = "ollama", name: str = "Ollama Local") -> None:
        self._provider_id = provider_id
        self._name = name

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return True

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        return [LLMModelMetadataDTO(id="llama3:8b", name="Llama 3 8B", size_bytes=4700000000)]

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(text="local response")

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        yield "local response"

class MockCloudProvider(BaseLLMProvider):
    def __init__(self, provider_id: str = "openrouter", name: str = "OpenRouter Cloud", api_key: str = "", default_model: str = "gemini-2.5-flash") -> None:
        self._provider_id = provider_id
        self._name = name
        self.api_key = api_key
        self.default_model = default_model

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return False

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        if not self.api_key:
            return [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Default)")]
        return [LLMModelMetadataDTO(id="google/gemini-2.5-flash", name="Gemini 2.5 Flash")]

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        return TextGenerationResponse(text="cloud response")

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        yield "cloud response"


def test_base_provider_health_check_credential_validation():
    async def run():
        # Local provider with no key -> is_configured = True
        local_p = MockLocalProvider()
        local_health = await local_p.check_health()
        assert local_health.is_configured is True
        assert local_health.is_available is True
        assert local_health.active_model == "llama3:8b"

        # Cloud provider with missing key -> is_configured = False, is_available = False
        unconfig_cloud = MockCloudProvider(api_key="")
        unconfig_health = await unconfig_cloud.check_health()
        assert unconfig_health.is_configured is False
        assert unconfig_health.is_available is False
        assert unconfig_health.error_message == "Missing API key in .env"

        # Cloud provider with API key -> is_configured = True, is_available = True
        config_cloud = MockCloudProvider(api_key="sk-test-12345")
        config_health = await config_cloud.check_health()
        assert config_health.is_configured is True
        assert config_health.is_available is True
        assert config_health.active_model == "google/gemini-2.5-flash"

    asyncio.run(run())


def test_provider_config_resolver():
    resolver = ProviderConfigResolver()
    assert resolver.get_active_provider_id() in ["ollama", "groq", "openrouter"]
    
    # Test setting active provider
    resolver.set_active_provider_id("groq")
    assert resolver.get_active_provider_id() == "groq"
    
    resolver.set_active_provider_id("ollama")
    assert resolver.get_active_provider_id() == "ollama"


def test_provider_registry_concurrent_catalog_and_hot_swap():
    async def run():
        resolver = ProviderConfigResolver()
        registry = LLMProviderRegistry(config_resolver=resolver)
        
        local_p = MockLocalProvider()
        unconfig_cloud = MockCloudProvider("openrouter", "OpenRouter", api_key="")
        config_cloud = MockCloudProvider("groq", "Groq Cloud", api_key="gsk_test")

        registry.register(local_p)
        registry.register(unconfig_cloud)
        registry.register(config_cloud)

        assert len(registry.list_providers()) == 3
        assert registry.get("ollama") == local_p
        assert registry.get("openrouter") == unconfig_cloud

        # Concurrent catalog retrieval
        catalog = await registry.get_catalog(force_refresh=True)
        assert len(catalog) == 3

        by_id = {item["id"]: item for item in catalog}
        assert by_id["ollama"]["is_configured"] is True
        assert by_id["ollama"]["is_available"] is True
        assert by_id["openrouter"]["is_configured"] is False
        assert by_id["openrouter"]["is_available"] is False
        assert by_id["groq"]["is_configured"] is True
        assert by_id["groq"]["is_available"] is True

        # Active provider resolution and hot swapping
        resolver.set_active_provider_id("groq")
        active = registry.get_active_provider()
        assert active.provider_id == "groq"

        resolver.set_active_provider_id("ollama")
        active_local = registry.get_active_provider()
        assert active_local.provider_id == "ollama"

    asyncio.run(run())
