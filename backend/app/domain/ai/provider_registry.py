import asyncio
import time
from typing import Dict, List, Optional, Any
from app.domain.ai.provider_interface import ILLMProvider, ProviderHealthDTO
from app.domain.ai.config_resolver import ProviderConfigResolver

class LLMProviderRegistry:
    """Centralized registry for resolving, listing, and querying LLM providers with concurrent health caching."""

    def __init__(self, config_resolver: Optional[ProviderConfigResolver] = None) -> None:
        self._providers: Dict[str, ILLMProvider] = {}
        self.config_resolver = config_resolver or ProviderConfigResolver()
        self._health_cache: Dict[str, ProviderHealthDTO] = {}
        self._health_cache_time: float = 0.0

    def register(self, provider: ILLMProvider) -> None:
        """Register an instantiated LLM provider adapter."""
        self._providers[provider.provider_id.lower()] = provider

    def get(self, provider_id: str) -> Optional[ILLMProvider]:
        """Resolve a registered provider adapter by ID."""
        return self._providers.get(provider_id.lower())

    def list_providers(self) -> List[Dict[str, Any]]:
        """List metadata for all registered providers."""
        return [
            {
                "id": p.provider_id,
                "name": p.name,
                "is_local": p.is_local,
            }
            for p in self._providers.values()
        ]

    def get_active_provider(self) -> ILLMProvider:
        """Resolve the currently active provider adapter based on config resolver."""
        active_id = self.config_resolver.get_active_provider_id()
        provider = self.get(active_id)
        if provider:
            return provider
        
        # Fallback to local ollama or first registered provider
        fallback = self.get("ollama")
        if fallback:
            return fallback
        if self._providers:
            return next(iter(self._providers.values()))
        raise RuntimeError("No LLM provider adapters are currently registered in LLMProviderRegistry.")

    async def get_catalog(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Build provider catalog concurrently using asyncio.gather with 30s TTL health caching."""
        now = time.time()
        use_cached_health = not force_refresh and (now - self._health_cache_time < 30.0)

        async def fetch_provider_info(p: ILLMProvider) -> Dict[str, Any]:
            if use_cached_health and p.provider_id in self._health_cache:
                health = self._health_cache[p.provider_id]
            else:
                health = await p.check_health()
                self._health_cache[p.provider_id] = health

            try:
                models = await p.list_models(force_refresh=force_refresh)
            except Exception:
                models = []

            return {
                "id": p.provider_id,
                "name": p.name,
                "is_local": p.is_local,
                "is_configured": health.is_configured,
                "is_available": health.is_available,
                "active_model": health.active_model,
                "models": [
                    {
                        "id": m.id,
                        "name": m.name,
                        "context_window": m.context_window,
                        "size_bytes": m.size_bytes,
                    }
                    for m in models
                ],
                "error": health.error_message,
            }

        if not self._providers:
            return []

        tasks = [fetch_provider_info(p) for p in self._providers.values()]
        catalog = await asyncio.gather(*tasks, return_exceptions=False)
        self._health_cache_time = now
        return catalog
