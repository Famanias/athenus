import pytest
from app.domain.ai.model_registry import ModelRegistry, ModelCapabilityType, ModelProviderType
from app.domain.ai.provider_router import ProviderRouter, RoutingPolicy
from app.domain.ai.service_bus import AIServiceBus
from app.infrastructure.adapters.ollama_adapter import OllamaTextGenAdapter

def test_model_registry_registration():
    registry = ModelRegistry()
    llm_models = registry.find_by_capability(ModelCapabilityType.TEXT_GENERATION)
    assert len(llm_models) >= 1
    assert llm_models[0].provider == ModelProviderType.OLLAMA

def test_provider_router_selection():
    registry = ModelRegistry()
    router = ProviderRouter(registry, RoutingPolicy(prefer_local=True))
    selected = router.select_model(ModelCapabilityType.TEXT_GENERATION)
    assert selected.is_local is True
    assert selected.model_id == "llama3:8b"

def test_ai_service_bus_resolution():
    registry = ModelRegistry()
    router = ProviderRouter(registry)
    bus = AIServiceBus(registry, router)
    adapter = OllamaTextGenAdapter()
    bus.register_text_adapter("ollama", adapter)
    
    capability = bus.get_text_capability()
    assert capability == adapter
