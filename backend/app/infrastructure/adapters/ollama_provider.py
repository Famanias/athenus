import httpx
from typing import Optional
from app.core.config import settings
from app.domain.ai.local_model_provider import (
    ILocalModelProvider,
    ProviderStatusDTO,
    ModelCatalogDTO,
    CatalogModelDTO,
)

class OllamaProviderAdapter(ILocalModelProvider):
    """Infrastructure adapter for local Ollama service daemon model discovery and health status."""

    def __init__(self, base_url: str = settings.OLLAMA_BASE_URL, timeout: float = settings.OLLAMA_TIMEOUT) -> None:
        self._base_url = base_url.rstrip("/")
        self.timeout = timeout

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def label(self) -> str:
        return "Ollama"

    @property
    def base_url(self) -> str:
        return self._base_url

    async def get_status(self) -> ProviderStatusDTO:
        """Fetch status and version from live Ollama REST daemon with timeout resilience."""
        url = f"{self._base_url}/api/version"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    version = data.get("version", "unknown")
                    return ProviderStatusDTO(
                        provider_id=self.provider_id,
                        label=self.label,
                        connected=True,
                        version=version,
                        base_url=self._base_url,
                        error=None
                    )
                return ProviderStatusDTO(
                    provider_id=self.provider_id,
                    label=self.label,
                    connected=False,
                    base_url=self._base_url,
                    error=f"Ollama HTTP {response.status_code}"
                )
        except Exception as e:
            return ProviderStatusDTO(
                provider_id=self.provider_id,
                label=self.label,
                connected=False,
                base_url=self._base_url,
                error=f"Ollama daemon unreachable ({str(e)})"
            )

    async def list_models(self) -> ModelCatalogDTO:
        """Fetch installed model tags from live Ollama REST API with timeout resilience."""
        url = f"{self._base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                if response.status_code == 200:
                    data = response.json()
                    raw_models = data.get("models", [])
                    catalog_dtos = []
                    for m in raw_models:
                        full_id = m.get("name", "")
                        if not full_id:
                            continue
                        name_parts = full_id.split(":")
                        name = name_parts[0]
                        tag = name_parts[1] if len(name_parts) > 1 else "latest"
                        catalog_dtos.append(
                            CatalogModelDTO(
                                full_id=full_id,
                                name=name,
                                tag=tag,
                                provider_id=self.provider_id,
                                size_bytes=m.get("size")
                            )
                        )
                    return ModelCatalogDTO(
                        provider_id=self.provider_id,
                        models=catalog_dtos,
                        count=len(catalog_dtos)
                    )
        except Exception:
            pass

        return ModelCatalogDTO(
            provider_id=self.provider_id,
            models=[],
            count=0
        )
