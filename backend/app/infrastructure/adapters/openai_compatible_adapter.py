import httpx
import json
import time
from typing import AsyncGenerator, Dict, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.exceptions import (
    LLMProviderError,
    LLMProviderAuthError,
    LLMProviderRateLimitError,
    LLMProviderTimeoutError,
    LLMProviderUnavailableError,
    LLMProviderBadRequestError,
)
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO, ProviderHealthDTO

NON_CHAT_KEYWORDS = (
    "embed", "embedding", "bge-", "rerank", "whisper", "guard", 
    "reward", "tts", "stt", "moderation", "transcription", "vector"
)

def default_is_chat_model(model_id: str) -> bool:
    """Predicate filtering out non-chat models (embeddings, rerankers, guardrails, STT/TTS)."""
    mid = model_id.lower()
    return not any(kw in mid for kw in NON_CHAT_KEYWORDS)

def _map_http_error(
    provider_id: str,
    provider_name: str,
    model_id: str,
    status_code: int,
    response_text: str,
    headers: httpx.Headers,
) -> LLMProviderError:
    err_detail = (response_text or "")[:300].strip()
    retry_after: Optional[float] = None
    raw_retry = headers.get("retry-after")
    if raw_retry:
        try:
            retry_after = float(raw_retry)
        except (ValueError, TypeError):
            pass

    if status_code in (401, 403):
        return LLMProviderAuthError(
            f"Authentication failed for {provider_name} ({status_code}): {err_detail}",
            provider_id=provider_id,
            model_id=model_id,
            status_code=status_code,
            raw_detail=err_detail,
        )
    elif status_code == 429:
        return LLMProviderRateLimitError(
            f"Rate limit exceeded for {provider_name}: {err_detail}",
            provider_id=provider_id,
            model_id=model_id,
            status_code=status_code,
            retry_after=retry_after,
            raw_detail=err_detail,
        )
    elif status_code in (400, 404, 422):
        return LLMProviderBadRequestError(
            f"Bad request to {provider_name} ({status_code}): {err_detail}",
            provider_id=provider_id,
            model_id=model_id,
            status_code=status_code,
            raw_detail=err_detail,
        )
    elif status_code in (500, 502, 503, 504):
        return LLMProviderUnavailableError(
            f"Provider {provider_name} unavailable ({status_code}): {err_detail}",
            provider_id=provider_id,
            model_id=model_id,
            status_code=status_code,
            retry_after=retry_after,
            raw_detail=err_detail,
        )
    else:
        return LLMProviderError(
            f"Provider {provider_name} error ({status_code}): {err_detail}",
            provider_id=provider_id,
            model_id=model_id,
            status_code=status_code,
            retry_after=retry_after,
            raw_detail=err_detail,
        )

class LLMStreamException(RuntimeError):
    """Raised when an LLM streaming response encounters an unrecoverable network or provider error mid-stream."""
    pass

class OpenAICompatibleProviderAdapter(BaseLLMProvider):
    """Generic, reusable Tier 1 adapter for any OpenAI-compatible provider (OpenRouter, Groq, OpenAI, DeepSeek, NIM, etc.)."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        base_url: str,
        api_key: Optional[str],
        default_model: str,
        is_local: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._provider_id = provider_id.lower()
        self._name = name
        self.base_url = base_url.rstrip("/")
        self._env_api_key = (api_key or "").strip()
        self.api_key = self._env_api_key
        self.default_model = default_model
        self._is_local = is_local
        self.extra_headers = extra_headers or {}
        self._http_client = http_client
        self._model_cache: List[LLMModelMetadataDTO] = []
        self._cache_timestamp: float = 0.0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return self._is_local

    def set_api_key(self, api_key: Optional[str]) -> None:
        """Update API key at runtime (uses transient key if provided, else falls back to .env key)."""
        if api_key and api_key.strip():
            self.api_key = api_key.strip()
        else:
            self.api_key = self._env_api_key
        # Clear model cache on key update
        self._model_cache = []
        self._cache_timestamp = 0.0

    def set_model(self, model: str) -> None:
        """Update active default model at runtime."""
        self.default_model = model

    def _resolve_model(self) -> str:
        """Resolve the active model from persisted per-provider settings, falling back to default."""
        try:
            from app.domain.settings.settings_service import SettingsService
            active_models = SettingsService().get_settings().active_models
            selected = (active_models or {}).get(self.provider_id)
            if selected:
                return selected
        except Exception:
            pass
        return self.default_model

    def _get_client(self) -> httpx.AsyncClient:
        return self._http_client or httpx.AsyncClient(timeout=30.0)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://athenus.local",
            "X-Title": "Athenus Knowledge OS",
            **self.extra_headers
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_vision=True,
            supports_function_calling=True,
            supports_model_discovery=True,
            max_context_window=128000
        )

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        now = time.time()
        # 1-Hour TTL Cache
        if not force_refresh and self._model_cache and (now - self._cache_timestamp < 3600.0):
            return self._model_cache

        if not self.api_key and not self.is_local:
            return [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Default)")]

        url = f"{self.base_url}/models"
        headers = self._build_headers()
        client = self._get_client()
        should_close = self._http_client is None

        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", [])
                discovered = []
                for m in raw_models:
                    mid = m.get("id", "")
                    if mid and default_is_chat_model(mid):
                        discovered.append(LLMModelMetadataDTO(
                            id=mid,
                            name=mid,
                            context_window=m.get("context_length", 4096),
                            owned_by=m.get("owned_by", self.provider_id),
                            is_chat_model=True
                        ))
                if discovered:
                    self._model_cache = discovered
                    self._cache_timestamp = now
                    return discovered
        except Exception:
            pass
        finally:
            if should_close:
                await client.aclose()

        # Fallback to default model
        return [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Default)")]

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        resolved_model = self._resolve_model()
        if not self.api_key and not self.is_local:
            raise LLMProviderAuthError(
                f"Missing API key for {self.name}. Please enter your {self.name} API Key in Settings or .env.",
                provider_id=self.provider_id,
                model_id=resolved_model,
            )

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": request.system_prompt or "You are Athenus AI Assistant."},
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 1024
        }
        if request.stop_sequences:
            payload["stop"] = request.stop_sequences

        client = self._get_client()
        should_close = self._http_client is None

        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices", [])
                content = choices[0]["message"]["content"] if choices else ""
                usage = data.get("usage", {})
                return TextGenerationResponse(
                    text=content,
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    finish_reason=choices[0].get("finish_reason", "stop") if choices else "stop"
                )
            else:
                raise _map_http_error(
                    self.provider_id,
                    self.name,
                    resolved_model,
                    resp.status_code,
                    resp.text,
                    resp.headers,
                )
        except httpx.TimeoutException as e:
            raise LLMProviderTimeoutError(
                f"Request to {self.name} timed out: {str(e)}",
                provider_id=self.provider_id,
                model_id=resolved_model,
            ) from e
        except httpx.NetworkError as e:
            raise LLMProviderUnavailableError(
                f"Failed to connect to {self.name}: {str(e)}",
                provider_id=self.provider_id,
                model_id=resolved_model,
            ) from e
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(
                f"Unexpected error communicating with {self.name}: {str(e)}",
                provider_id=self.provider_id,
                model_id=resolved_model,
            ) from e
        finally:
            if should_close:
                await client.aclose()

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        resolved_model = self._resolve_model()
        if not self.api_key and not self.is_local:
            raise LLMProviderAuthError(
                f"Missing API key for {self.name}. Please enter your {self.name} API Key in Settings or .env.",
                provider_id=self.provider_id,
                model_id=resolved_model,
            )

        url = f"{self.base_url}/chat/completions"
        headers = self._build_headers()
        payload = {
            "model": resolved_model,
            "messages": [
                {"role": "system", "content": request.system_prompt or "You are Athenus AI Assistant."},
                {"role": "user", "content": request.prompt}
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens or 1024,
            "stream": True
        }

        client = self._get_client()
        should_close = self._http_client is None

        try:
            async with client.stream("POST", url, headers=headers, json=payload) as resp:
                if resp.status_code != 200:
                    resp_text = await resp.aread()
                    raise _map_http_error(
                        self.provider_id,
                        self.name,
                        resolved_model,
                        resp.status_code,
                        resp_text.decode("utf-8", errors="replace"),
                        resp.headers,
                    )

                async for line in resp.aiter_lines():
                    if not line or not line.startswith("data:"):
                        continue
                    line_data = line[5:].strip()
                    if line_data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line_data)
                        choices = chunk.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
        except (LLMProviderError, LLMStreamException):
            raise
        except httpx.TimeoutException as e:
            raise LLMProviderTimeoutError(
                f"{self.name} streaming timed out: {str(e)}",
                provider_id=self.provider_id,
                model_id=resolved_model,
            ) from e
        except httpx.NetworkError as e:
            raise LLMProviderUnavailableError(
                f"{self.name} streaming network connection failed: {str(e)}",
                provider_id=self.provider_id,
                model_id=resolved_model,
            ) from e
        except Exception as e:
            raise LLMStreamException(f"{self.name} streaming failed mid-response: {str(e)}") from e
        finally:
            if should_close:
                await client.aclose()
