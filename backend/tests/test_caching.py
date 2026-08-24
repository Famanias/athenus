import asyncio

from sqlalchemy import create_engine, text

from app.domain.ai.cached_text_generation import CachedTextGenerationAdapter
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.infrastructure.adapters.sentence_transformers_adapter import (
    SentenceTransformersEmbeddingAdapter,
)
from app.infrastructure.cache.memory_cache import MemoryCacheAdapter
from app.infrastructure.cache.sqlite_cache import SqliteKVCacheAdapter


def test_memory_cache_enforces_ttl_lru_and_prefix_deletion():
    now = [100.0]
    cache = MemoryCacheAdapter(maxsize=2, clock=lambda: now[0])
    cache.set("kg:ws:a:nodes", [1], ttl_seconds=10)
    cache.set("kg:ws:a:edges", [2])
    assert cache.get("kg:ws:a:nodes") == [1]

    cache.set("other", 3)
    assert cache.get("kg:ws:a:edges") is None
    assert cache.delete_prefix("kg:ws:a:") == 1
    assert cache.get("kg:ws:a:nodes") is None

    cache.set("short", True, ttl_seconds=1)
    now[0] += 2
    assert cache.get("short") is None


def test_sqlite_cache_persists_values_and_escapes_prefixes(tmp_path):
    db_engine = create_engine(f"sqlite:///{tmp_path / 'cache.db'}")
    first = SqliteKVCacheAdapter(db_engine)
    first.set("embed:model_a:one", [0.1, 0.2], ttl_seconds=60)
    first.set("embed:model%:two", [0.3])

    second = SqliteKVCacheAdapter(db_engine)
    assert second.get("embed:model_a:one") == [0.1, 0.2]
    assert second.delete_prefix("embed:model%:") == 1
    assert second.get("embed:model_a:one") == [0.1, 0.2]
    assert second.delete("embed:model_a:one") is True


def test_embedding_cache_deduplicates_repeated_texts():
    class CountingEmbeddingAdapter(SentenceTransformersEmbeddingAdapter):
        def __init__(self):
            super().__init__(model_name="test-model", memory_cache=MemoryCacheAdapter())
            self.computed_batches = []

        def _embed_sync(self, texts):
            self.computed_batches.append(list(texts))
            return [[float(len(text))] for text in texts]

    async def run():
        adapter = CountingEmbeddingAdapter()
        first = await adapter.embed_texts(["same text", "same   text", "different"])
        second = await adapter.embed_query("same text")
        assert first == [[9.0], [9.0], [9.0]]
        assert second == [9.0]
        assert adapter.computed_batches == [["same text", "different"]]

    asyncio.run(run())


def test_deterministic_llm_cache_honors_temperature_and_force_refresh():
    class FakeProvider:
        provider_id = "fake"
        default_model = "model-1"
        name = "Fake"
        is_local = True

        def __init__(self):
            self.calls = 0

        async def generate(self, request):
            self.calls += 1
            return TextGenerationResponse(text=f"answer-{self.calls}")

        async def stream(self, request):
            yield "chunk"

    async def run():
        provider = FakeProvider()
        cached = CachedTextGenerationAdapter(provider, MemoryCacheAdapter())
        request = TextGenerationRequest(
            prompt="stable",
            temperature=0.1,
            workspace_id="ws-1",
        )
        assert (await cached.generate(request)).text == "answer-1"
        assert (await cached.generate(request)).text == "answer-1"
        assert provider.calls == 1

        request.force_refresh = True
        assert (await cached.generate(request)).text == "answer-2"
        request.force_refresh = False
        request.temperature = 0.8
        assert (await cached.generate(request)).text == "answer-3"

    asyncio.run(run())


def test_application_sqlite_connection_pragmas_are_enabled():
    from app.infrastructure.db.session import engine

    if engine is None or engine.dialect.name != "sqlite":
        return
    with engine.connect() as connection:
        assert connection.execute(text("PRAGMA synchronous")).scalar_one() == 1
        assert connection.execute(text("PRAGMA cache_size")).scalar_one() == -64000
        assert connection.execute(text("PRAGMA busy_timeout")).scalar_one() == 5000
