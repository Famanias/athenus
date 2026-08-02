from typing import Dict, Optional, Any
from app.domain.ai.capabilities import ITextGenerationCapability, ISpeechToTextCapability, IEmbeddingCapability
from app.domain.ai.model_registry import ModelCapabilityType, ModelRegistry
from app.domain.ai.provider_router import ProviderRouter

class AIServiceBus:
    """Centralized AI Service Bus for capability routing, adapter invocation, and telemetry hooks."""
    def __init__(self, registry: ModelRegistry, router: ProviderRouter) -> None:
        self.registry = registry
        self.router = router
        self._text_adapters: Dict[str, ITextGenerationCapability] = {}
        self._stt_adapters: Dict[str, ISpeechToTextCapability] = {}
        self._embedding_adapters: Dict[str, IEmbeddingCapability] = {}

    def register_text_adapter(self, provider_id: str, adapter: ITextGenerationCapability) -> None:
        self._text_adapters[provider_id] = adapter

    def register_stt_adapter(self, provider_id: str, adapter: ISpeechToTextCapability) -> None:
        self._stt_adapters[provider_id] = adapter

    def register_embedding_adapter(self, provider_id: str, adapter: IEmbeddingCapability) -> None:
        self._embedding_adapters[provider_id] = adapter

    def get_text_capability(self, model_id: Optional[str] = None) -> ITextGenerationCapability:
        from app.presentation.api.v1.settings import current_settings
        active_provider = current_settings.get("default_llm", "ollama").lower()

        adapter = self._text_adapters.get(active_provider)
        if not adapter:
            # Fallback to local ollama adapter or default
            adapter = self._text_adapters.get("ollama")
        if not adapter:
            raise RuntimeError(f"No adapter registered for provider: {active_provider}")
        return adapter

    def get_stt_capability(self, model_id: Optional[str] = None) -> ISpeechToTextCapability:
        selected_model = self.router.select_model(ModelCapabilityType.SPEECH_TO_TEXT, preferred_model_id=model_id)
        adapter = self._stt_adapters.get(selected_model.provider.value)
        if not adapter:
            raise RuntimeError(f"No STT adapter registered for provider: {selected_model.provider}")
        return adapter

    def get_embedding_capability(self, model_id: Optional[str] = None) -> IEmbeddingCapability:
        selected_model = self.router.select_model(ModelCapabilityType.EMBEDDINGS, preferred_model_id=model_id)
        adapter = self._embedding_adapters.get(selected_model.provider.value)
        if not adapter:
            raise RuntimeError(f"No embedding adapter registered for provider: {selected_model.provider}")
        return adapter
