import httpx
import json
import time
from typing import AsyncGenerator, List, Optional
from app.core.config import settings
from app.domain.ai.capabilities import (
    TextGenerationRequest,
    TextGenerationResponse,
)
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO

class OllamaTextGenAdapter(BaseLLMProvider):
    """Local Ollama LLM provider adapter conforming to BaseLLMProvider."""

    def __init__(
        self,
        base_url: str = settings.OLLAMA_BASE_URL,
        default_model: str = settings.DEFAULT_LLM_MODEL,
        settings_service: Optional["object"] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._settings_service = settings_service
        self._http_client = http_client
        self._model_cache: List[LLMModelMetadataDTO] = []
        self._cache_timestamp: float = 0.0

    @property
    def provider_id(self) -> str:
        return "ollama"

    @property
    def name(self) -> str:
        return "Ollama (Local Daemon)"

    @property
    def is_local(self) -> bool:
        return True

    def set_model(self, model: str) -> None:
        """Update active default model at runtime."""
        self.default_model = model

    def _get_client(self) -> httpx.AsyncClient:
        return self._http_client or httpx.AsyncClient(timeout=10.0)

    def _resolve_model(self) -> str:
        """Resolve the active Ollama model from persisted settings, falling back to default."""
        try:
            settings_service = self._settings_service
            if settings_service is None:
                from app.domain.settings.settings_service import SettingsService
                settings_service = SettingsService()
            selected = settings_service.get_settings().selected_ollama_model
            if selected:
                return selected
        except Exception:
            pass
        return self.default_model

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_vision=False,
            supports_function_calling=False,
            supports_model_discovery=True,
            max_context_window=8192
        )

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        now = time.time()
        if not force_refresh and self._model_cache and (now - self._cache_timestamp < 30.0):
            return self._model_cache

        url = f"{self.base_url}/api/tags"
        client = self._get_client()
        should_close = self._http_client is None

        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("models", [])
                discovered = [
                    LLMModelMetadataDTO(
                        id=m.get("name", m.get("model", "")),
                        name=m.get("name", m.get("model", "")),
                        context_window=8192,
                        owned_by="ollama",
                        is_chat_model=True,
                        size_bytes=m.get("size")
                    )
                    for m in raw_models if m.get("name") or m.get("model")
                ]
                if discovered:
                    self._model_cache = discovered
                    self._cache_timestamp = now
                    return discovered
        except Exception:
            pass
        finally:
            if should_close:
                await client.aclose()

        fallback = [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Configured Default)")]
        return fallback

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        url = f"{self.base_url}/api/generate"
        client = self._get_client()
        should_close = self._http_client is None

        try:
            for model_name in [self._resolve_model(), "llama3", "llama3:8b"]:
                payload = {
                    "model": model_name,
                    "prompt": request.prompt,
                    "system": request.system_prompt or "",
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens or 512,
                    }
                }
                try:
                    response = await client.post(url, json=payload)
                    if response.status_code == 200:
                        data = response.json()
                        return TextGenerationResponse(
                            text=data.get("response", ""),
                            prompt_tokens=data.get("prompt_eval_count", 0),
                            completion_tokens=data.get("eval_count", 0),
                        )
                except Exception:
                    continue

            return TextGenerationResponse(
                text=f"Local AI Response (Ollama Offline Fallback): Processed request '{request.prompt[:40]}...'",
                prompt_tokens=30,
                completion_tokens=25
            )
        finally:
            if should_close:
                await client.aclose()

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self._resolve_model(),
            "prompt": request.prompt,
            "system": request.system_prompt or "",
            "stream": True,
        }
        client = self._get_client()
        should_close = self._http_client is None

        try:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            yield chunk.get("response", "")
                    return
        except Exception:
            pass
        finally:
            if should_close:
                await client.aclose()

        yield f"Local AI Stream (Ollama Offline Fallback): Processed request '{request.prompt[:30]}...'."
