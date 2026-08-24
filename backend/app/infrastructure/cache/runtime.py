from app.infrastructure.cache.memory_cache import MemoryCacheAdapter
from app.infrastructure.cache.sqlite_cache import SqliteKVCacheAdapter
from app.infrastructure.db.session import engine


# Shared caches make prefix invalidation visible across independently constructed
# domain modules while retaining a local-first, dependency-free runtime.
application_memory_cache = MemoryCacheAdapter(maxsize=2000)
persistent_cache = SqliteKVCacheAdapter(engine)
