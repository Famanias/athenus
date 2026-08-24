import httpx
import json
import logging
import time
from typing import AsyncGenerator, List, Optional
from app.core.config import settings
from app.domain.ai.capabilities import (
    TextGenerationRequest,
    TextGenerationResponse,
)
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO

logger = logging.getLogger(__name__)

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

    def _get_client(self, timeout: Optional[httpx.Timeout] = None) -> httpx.AsyncClient:
        if self._http_client:
            return self._http_client
        if timeout is None:
            timeout = httpx.Timeout(timeout=None, connect=10.0)
        return httpx.AsyncClient(timeout=timeout)

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

        base_urls = [self.base_url, "http://ollama:11434", "http://host.docker.internal:11434", "http://localhost:11434"]
        unique_urls = []
        for u in base_urls:
            u_clean = u.rstrip("/")
            if u_clean and u_clean not in unique_urls:
                unique_urls.append(u_clean)

        client = self._get_client(timeout=httpx.Timeout(4.0))
        should_close = self._http_client is None

        try:
            for url_base in unique_urls:
                url = f"{url_base}/api/tags"
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
                            self.base_url = url_base
                            self._model_cache = discovered
                            self._cache_timestamp = now
                            return discovered
                except Exception as exc:
                    logger.debug("Ollama list_models probe failed for %s: %s", url_base, exc)
        finally:
            if should_close:
                await client.aclose()

        # Fallback catalog including requested models (llama3:8b, qwen3.6, gpt-oss:20b)
        fallback_models = [
            LLMModelMetadataDTO(id="llama3:8b", name="llama3:8b (Local Ollama)"),
            LLMModelMetadataDTO(id="qwen3.6", name="qwen3.6 (Local Ollama)"),
            LLMModelMetadataDTO(id="gpt-oss:20b", name="gpt-oss:20b (Local Ollama)"),
        ]
        if self.default_model not in [m.id for m in fallback_models]:
            fallback_models.insert(0, LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Local Ollama)"))

        self._model_cache = fallback_models
        self._cache_timestamp = now
        return fallback_models

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        base_urls = [self.base_url, "http://ollama:11434", "http://host.docker.internal:11434", "http://localhost:11434"]
        unique_urls = []
        for u in base_urls:
            u_clean = u.rstrip("/")
            if u_clean and u_clean not in unique_urls:
                unique_urls.append(u_clean)

        client = self._get_client(timeout=httpx.Timeout(timeout=None, connect=10.0))
        should_close = self._http_client is None

        resolved = self._resolve_model()
        candidates = []
        for m in [resolved, self.default_model, "llama3:8b"]:
            if m and m not in candidates:
                candidates.append(m)

        last_err_msg = ""

        try:
            for url_base in unique_urls:
                url = f"{url_base}/api/generate"
                for model_name in candidates:
                    payload = {
                        "model": model_name,
                        "prompt": request.prompt,
                        "system": request.system_prompt or "",
                        "stream": False,
                        "keep_alive": "30m",
                        "options": {
                            "temperature": request.temperature,
                            "num_predict": request.max_tokens or 512,
                        }
                    }
                    try:
                        response = await client.post(url, json=payload)
                        if response.status_code == 200:
                            data = response.json()
                            self.base_url = url_base
                            return TextGenerationResponse(
                                text=data.get("response", ""),
                                prompt_tokens=data.get("prompt_eval_count", 0),
                                completion_tokens=data.get("eval_count", 0),
                            )
                        elif response.status_code == 404 or "not found" in response.text.lower():
                            last_err_msg = f"Ollama model '{model_name}' is not pulled into the Ollama daemon. Run 'ollama pull {model_name}' in your terminal to install it."
                        else:
                            last_err_msg = f"Ollama HTTP {response.status_code}: {response.text[:150]}"
                    except Exception as exc:
                        last_err_msg = f"Failed connecting to Ollama at {url_base}: {exc}"
                        continue

            err_msg = last_err_msg or f"Ollama generation failed across candidates {candidates}. Ensure Ollama daemon is running."
            logger.error(err_msg)
            raise ValueError(err_msg)
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
            "keep_alive": "30m",
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens or 512,
            },
        }
        client = self._get_client(timeout=httpx.Timeout(timeout=None, connect=10.0))
        should_close = self._http_client is None

        try:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line:
                            chunk = json.loads(line)
                            yield chunk.get("response", "")
                    return
                else:
                    err_msg = f"Ollama stream HTTP {response.status_code}"
                    logger.error(err_msg)
                    raise RuntimeError(err_msg)
        except Exception as exc:
            logger.error("Ollama stream exception: %s", exc)
            raise RuntimeError(f"Ollama stream failed: {exc}") from exc
        finally:
            if should_close:
                await client.aclose()

