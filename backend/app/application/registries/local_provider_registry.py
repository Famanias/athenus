from typing import Dict, List, Optional
from app.domain.ai.local_model_provider import ILocalModelProvider

class LocalModelProviderRegistry:
    """Lightweight application registry for local model providers using dependency injection."""

    def __init__(self) -> None:
        self._providers: Dict[str, ILocalModelProvider] = {}

    def register(self, provider: ILocalModelProvider) -> None:
        """Register a local model provider implementation."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> Optional[ILocalModelProvider]:
        """Look up a registered provider by its identifier."""
        return self._providers.get(provider_id.lower())

    def list_providers(self) -> List[ILocalModelProvider]:
        """List all registered local model providers."""
        return list(self._providers.values())
