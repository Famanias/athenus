import asyncio
import hashlib
import unicodedata
from typing import List
from app.core.config import settings
from app.domain.ai.capabilities import IEmbeddingCapability
from app.domain.common.cache_interface import ICacheStore

class SentenceTransformersEmbeddingAdapter(IEmbeddingCapability):
    CACHE_TTL_SECONDS = 7 * 24 * 60 * 60

    def __init__(
        self,
        model_name: str = settings.EMBEDDING_MODEL_NAME,
        cache_store: ICacheStore | None = None,
        memory_cache: ICacheStore | None = None,
    ) -> None:
        self.model_name = model_name
        self._model = None
        self._cache_store = cache_store
        self._memory_cache = memory_cache
        self._compute_lock = asyncio.Lock()

    @staticmethod
    def _normalize_text(text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text or "")
        return " ".join(normalized.split())

    def _cache_key(self, text: str) -> str:
        digest = hashlib.sha256(self._normalize_text(text).encode("utf-8")).hexdigest()
        return f"embed:{self.model_name}:{digest}"

    def _cached(self, key: str) -> List[float] | None:
        if self._memory_cache is not None:
            value = self._memory_cache.get(key)
            if isinstance(value, list):
                return value
        if self._cache_store is not None:
            value = self._cache_store.get(key)
            if isinstance(value, list):
                if self._memory_cache is not None:
                    self._memory_cache.set(key, value, ttl_seconds=self.CACHE_TTL_SECONDS)
                return value
        return None

    def _store(self, key: str, vector: List[float]) -> None:
        if self._cache_store is not None:
            self._cache_store.set(key, vector, ttl_seconds=self.CACHE_TTL_SECONDS)
        if self._memory_cache is not None:
            self._memory_cache.set(key, vector, ttl_seconds=self.CACHE_TTL_SECONDS)

    def _get_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name)
            except Exception:
                self._model = "MOCK"
        return self._model

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []
        if self._cache_store is None and self._memory_cache is None:
            loop = asyncio.get_running_loop()
            return await loop.run_in_executor(None, self._embed_sync, texts)

        keys = [self._cache_key(text) for text in texts]
        results: List[List[float] | None] = [self._cached(key) for key in keys]
        if all(result is not None for result in results):
            return [result for result in results if result is not None]

        # Model execution is serialized and every miss is rechecked inside the
        # lock, preventing concurrent requests from stampeding the CPU/GPU.
        async with self._compute_lock:
            results = [self._cached(key) for key in keys]
            missing_keys: List[str] = []
            missing_texts: List[str] = []
            seen = set()
            for key, text, result in zip(keys, texts, results):
                if result is None and key not in seen:
                    seen.add(key)
                    missing_keys.append(key)
                    missing_texts.append(text)

            if missing_texts:
                loop = asyncio.get_running_loop()
                computed = await loop.run_in_executor(None, self._embed_sync, missing_texts)
                for key, vector in zip(missing_keys, computed):
                    self._store(key, vector)

            final = [self._cached(key) for key in keys]
            return [value if value is not None else [] for value in final]

    async def embed_query(self, query: str) -> List[float]:
        results = await self.embed_texts([query])
        return results[0]

    def _embed_sync(self, texts: List[str]) -> List[List[float]]:
        model = self._get_model()
        if model == "MOCK":
            # 384-dimensional mock embedding vector for testing fallback
            return [[0.01 * (i + 1) for i in range(384)] for _ in texts]
        embeddings = model.encode(texts, show_progress_bar=False)
        return [emb.tolist() for emb in embeddings]
