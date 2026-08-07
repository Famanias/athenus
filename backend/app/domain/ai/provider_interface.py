from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse

@dataclass
class LLMProviderCapabilities:
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_model_discovery: bool = True
    max_context_window: int = 128000

@dataclass
class LLMModelMetadataDTO:
    id: str
    name: str
    context_window: int = 4096
    owned_by: str = ""
    is_chat_model: bool = True
    size_bytes: Optional[int] = None

@dataclass
class ProviderHealthDTO:
    provider_id: str
    is_available: bool
    is_configured: bool
    active_model: str
    error_message: Optional[str] = None

class ILLMProvider(ABC):
    """Unified domain abstraction interface for all LLM text generation providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Immutable, versioned provider identifier (e.g. 'ollama', 'openrouter', 'groq', 'openai', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider display label."""
        pass

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """Flag indicating whether execution is local (zero latency/offline) or cloud API."""
        pass

    @abstractmethod
    async def get_capabilities(self) -> LLMProviderCapabilities:
        """Retrieve capability flags for the provider."""
        pass

    @abstractmethod
    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        """Dynamically discover available chat models from the provider API with TTL caching."""
        pass

    @abstractmethod
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """Execute non-streaming text generation."""
        pass

    @abstractmethod
    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        """Execute streaming text generation."""
        pass

    @abstractmethod
    async def check_health(self) -> ProviderHealthDTO:
        """Check API connectivity, credential validity, and active model status."""
        pass

class BaseLLMProvider(ILLMProvider):
    """Abstract base provider supplying sensible default implementations for common methods."""

    def set_model(self, model: str) -> None:
        """Update active default model at runtime."""
        self.default_model = model

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(supports_streaming=True, supports_model_discovery=True)

    async def check_health(self) -> ProviderHealthDTO:
        """Default health check with explicit credential validation prior to model listing."""
        has_creds = bool(getattr(self, "api_key", "")) or self.is_local
        default_m = getattr(self, "default_model", "unknown")
        
        if not has_creds:
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=False,
                is_configured=False,
                active_model=default_m,
                error_message="Missing API key in .env"
            )

        try:
            models = await self.list_models()
            is_avail = len(models) > 0
            model_ids = [m.id for m in models]
            def_m = getattr(self, "default_model", "unknown")
            # Prefer the persisted/resolved selection so the catalog reflects source of truth
            resolve_fn = getattr(self, "_resolve_model", None)
            resolved_m = def_m
            if callable(resolve_fn):
                try:
                    resolved_m = resolve_fn() or def_m
                except Exception:
                    pass
            if resolved_m and (not models or resolved_m in model_ids):
                active_m = resolved_m
            else:
                active_m = models[0].id if models else resolved_m
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=is_avail,
                is_configured=True,
                active_model=active_m,
                error_message=None if is_avail else "No models discovered"
            )
        except Exception as e:
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=False,
                is_configured=True,
                active_model=default_m,
                error_message=str(e)
            )
