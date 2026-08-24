from typing import Dict, List, Optional, Any
from app.domain.ai.capabilities import ITextGenerationCapability, ISpeechToTextCapability, IEmbeddingCapability
from app.domain.ai.model_registry import ModelCapabilityType, ModelRegistry
from app.domain.ai.provider_router import ProviderRouter
from app.domain.ai.provider_interface import ILLMProvider
from app.domain.ai.provider_registry import LLMProviderRegistry
from app.domain.ai.cached_text_generation import CachedTextGenerationAdapter
from app.domain.common.cache_interface import ICacheStore

class UnsupportedCapabilityError(RuntimeError):
    """Raised when a requested feature capability is not supported by the active LLM provider."""
    pass

class AIServiceBus:
    """Centralized AI Service Bus for capability routing, adapter invocation, and telemetry hooks."""
    
    def __init__(
        self,
        registry: ModelRegistry,
        router: ProviderRouter,
        llm_registry: Optional[LLMProviderRegistry] = None,
        completion_cache: Optional[ICacheStore] = None,
    ) -> None:
        self.registry = registry
        self.router = router
        self.llm_registry = llm_registry
        self.completion_cache = completion_cache
        self._text_adapters: Dict[str, ITextGenerationCapability] = {}
        self._stt_adapters: Dict[str, ISpeechToTextCapability] = {}
        self._embedding_adapters: Dict[str, IEmbeddingCapability] = {}
        self._cached_text_adapters: Dict[int, CachedTextGenerationAdapter] = {}

    def _with_completion_cache(self, adapter):
        if self.completion_cache is None:
            return adapter
        identity = id(adapter)
        cached = self._cached_text_adapters.get(identity)
        if cached is None:
            cached = CachedTextGenerationAdapter(adapter, self.completion_cache)
            self._cached_text_adapters[identity] = cached
        return cached

    def invalidate_workspace_cache(self, workspace_id: str) -> int:
        """Invalidate deterministic completions associated with a workspace."""
        if self.completion_cache is None:
            return 0
        return self.completion_cache.delete_prefix(f"llm:ws:{workspace_id}:")

    def register_text_adapter(self, provider_id: str, adapter: ITextGenerationCapability) -> None:
        self._text_adapters[provider_id] = adapter

    def register_stt_adapter(self, provider_id: str, adapter: ISpeechToTextCapability) -> None:
        self._stt_adapters[provider_id] = adapter

    def register_embedding_adapter(self, provider_id: str, adapter: IEmbeddingCapability) -> None:
        self._embedding_adapters[provider_id] = adapter

    def get_text_capability(
        self,
        model_id: Optional[str] = None,
        required_capabilities: Optional[List[str]] = None
    ) -> ILLMProvider:
        """Resolve active text generation provider capability with optional capability negotiation."""
        if self.llm_registry:
            provider = self.llm_registry.get_active_provider()
            if required_capabilities:
                # Capability check
                import asyncio
                try:
                    caps = asyncio.run(provider.get_capabilities())
                    for req in required_capabilities:
                        if req == "vision" and not caps.supports_vision:
                            raise UnsupportedCapabilityError(f"Active provider '{provider.name}' does not support Vision capabilities.")
                        if req == "function_calling" and not caps.supports_function_calling:
                            raise UnsupportedCapabilityError(f"Active provider '{provider.name}' does not support Function Calling.")
                except UnsupportedCapabilityError:
                    raise
                except Exception:
                    pass
            return self._with_completion_cache(provider)

        # Fallback to legacy dictionary lookup
        from app.domain.settings.settings_service import SettingsService
        active_provider = SettingsService().get_settings().default_llm.lower()

        adapter = self._text_adapters.get(active_provider)
        if not adapter:
            adapter = self._text_adapters.get("ollama")
        if not adapter:
            raise RuntimeError(f"No adapter registered for provider: {active_provider}")
        return self._with_completion_cache(adapter)

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
