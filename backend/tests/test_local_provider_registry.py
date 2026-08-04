import pytest
from app.domain.ai.local_model_provider import (
    ILocalModelProvider,
    ProviderStatusDTO,
    ModelCatalogDTO,
    CatalogModelDTO,
)
from app.application.registries.local_provider_registry import LocalModelProviderRegistry

class MockLocalProvider(ILocalModelProvider):
    def __init__(self, pid: str, label_text: str, models_list: list) -> None:
        self._pid = pid
        self._label = label_text
        self._models = models_list

    @property
    def provider_id(self) -> str:
        return self._pid

    @property
    def label(self) -> str:
        return self._label

    async def get_status(self) -> ProviderStatusDTO:
        return ProviderStatusDTO(
            provider_id=self.provider_id,
            label=self.label,
            connected=True,
            version="1.0.0",
            base_url=f"http://localhost:{self.provider_id}"
        )

    async def list_models(self) -> ModelCatalogDTO:
        dtos = [
            CatalogModelDTO(full_id=m, name=m.split(":")[0], tag="latest", provider_id=self.provider_id)
            for m in self._models
        ]
        return ModelCatalogDTO(provider_id=self.provider_id, models=dtos, count=len(dtos))

def test_registry_registration_and_lookup():
    registry = LocalModelProviderRegistry()
    assert len(registry.list_providers()) == 0

    ollama_provider = MockLocalProvider("ollama", "Ollama", ["llama3:8b", "phi3:mini"])
    registry.register(ollama_provider)

    assert len(registry.list_providers()) == 1
    found = registry.get_provider("ollama")
    assert found is not None
    assert found.label == "Ollama"

def test_multi_provider_independent_registration():
    registry = LocalModelProviderRegistry()
    ollama_provider = MockLocalProvider("ollama", "Ollama", ["llama3:8b"])
    lmstudio_provider = MockLocalProvider("lmstudio", "LM Studio", ["qwen2.5-7b"])

    registry.register(ollama_provider)
    registry.register(lmstudio_provider)

    providers = registry.list_providers()
    assert len(providers) == 2

    assert registry.get_provider("ollama").label == "Ollama"
    assert registry.get_provider("lmstudio").label == "LM Studio"
    assert registry.get_provider("unknown") is None
