import asyncio
import hashlib
import json
from threading import RLock
from typing import AsyncGenerator, Dict

from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.common.cache_interface import ICacheStore


class CachedTextGenerationAdapter:
    """Memoizes deterministic non-streaming generations behind provider semantics."""

    CACHE_TTL_SECONDS = 24 * 60 * 60
    MAX_CACHE_TEMPERATURE = 0.2

    def __init__(self, provider, cache_store: ICacheStore) -> None:
        self._provider = provider
        self._cache_store = cache_store
        self._locks: Dict[str, asyncio.Lock] = {}
        self._locks_guard = RLock()

    def __getattr__(self, name):
        return getattr(self._provider, name)

    @property
    def provider_id(self) -> str:
        return str(getattr(self._provider, "provider_id", self._provider.__class__.__name__))

    @property
    def name(self) -> str:
        return str(getattr(self._provider, "name", self.provider_id))

    @property
    def is_local(self) -> bool:
        return bool(getattr(self._provider, "is_local", False))

    def _model_id(self) -> str:
        resolver = getattr(self._provider, "_resolve_model", None)
        if callable(resolver):
            try:
                return str(resolver())
            except Exception:
                pass
        return str(getattr(self._provider, "default_model", "default"))

    def _cache_key(self, request: TextGenerationRequest) -> str:
        prompt_fingerprint = json.dumps(
            {
                "system": request.system_prompt or "",
                "prompt": request.prompt,
                "max_tokens": request.max_tokens,
                "stop_sequences": request.stop_sequences,
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        digest = hashlib.sha256(prompt_fingerprint.encode("utf-8")).hexdigest()
        workspace = request.workspace_id or "global"
        temperature = f"{request.temperature:.3f}"
        return (
            f"llm:ws:{workspace}:{self.provider_id}:{self._model_id()}:"
            f"{temperature}:{digest}"
        )

    @staticmethod
    def _decode(value) -> TextGenerationResponse | None:
        if not isinstance(value, dict) or not isinstance(value.get("text"), str):
            return None
        return TextGenerationResponse(
            text=value["text"],
            prompt_tokens=int(value.get("prompt_tokens", 0)),
            completion_tokens=int(value.get("completion_tokens", 0)),
            finish_reason=str(value.get("finish_reason", "stop")),
        )

    def _get_lock(self, key: str) -> asyncio.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, asyncio.Lock())

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        if request.force_refresh or request.temperature > self.MAX_CACHE_TEMPERATURE:
            return await self._provider.generate(request)

        key = self._cache_key(request)
        try:
            cached = self._decode(self._cache_store.get(key))
        except Exception:
            cached = None
        if cached is not None:
            return cached

        lock = self._get_lock(key)
        try:
            async with lock:
                try:
                    cached = self._decode(self._cache_store.get(key))
                except Exception:
                    cached = None
                if cached is not None:
                    return cached

                response = await self._provider.generate(request)
                try:
                    self._cache_store.set(
                        key,
                        {
                            "text": response.text,
                            "prompt_tokens": response.prompt_tokens,
                            "completion_tokens": response.completion_tokens,
                            "finish_reason": response.finish_reason,
                        },
                        ttl_seconds=self.CACHE_TTL_SECONDS,
                    )
                except Exception:
                    pass
                return response
        finally:
            with self._locks_guard:
                if not lock.locked():
                    self._locks.pop(key, None)

    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        async for chunk in self._provider.stream(request):
            yield chunk
