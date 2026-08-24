import json
from threading import RLock
from time import time
from typing import Any, Optional

from sqlalchemy import text

from app.domain.common.cache_interface import ICacheStore


class SqliteKVCacheAdapter(ICacheStore):
    """Persistent JSON key-value cache backed by the application's SQLite DB."""

    def __init__(self, engine) -> None:
        self._engine = engine
        self._initialized = False
        self._lock = RLock()

    def _ensure_table(self) -> bool:
        if self._initialized:
            return True
        if self._engine is None:
            return False
        with self._lock:
            if self._initialized:
                return True
            with self._engine.begin() as connection:
                connection.execute(text("""
                    CREATE TABLE IF NOT EXISTS app_kv_cache (
                        cache_key TEXT PRIMARY KEY,
                        value_json TEXT NOT NULL,
                        expires_at REAL,
                        updated_at REAL NOT NULL
                    )
                """))
                connection.execute(text("""
                    CREATE INDEX IF NOT EXISTS ix_app_kv_cache_expires_at
                    ON app_kv_cache (expires_at)
                """))
            self._initialized = True
            return True

    def get(self, key: str) -> Optional[Any]:
        if not self._ensure_table():
            return None
        now = time()
        with self._lock, self._engine.begin() as connection:
            row = connection.execute(
                text("""
                    SELECT value_json, expires_at
                    FROM app_kv_cache
                    WHERE cache_key = :cache_key
                """),
                {"cache_key": key},
            ).first()
            if row is None:
                return None
            if row.expires_at is not None and float(row.expires_at) <= now:
                connection.execute(
                    text("DELETE FROM app_kv_cache WHERE cache_key = :cache_key"),
                    {"cache_key": key},
                )
                return None
            try:
                return json.loads(row.value_json)
            except (TypeError, json.JSONDecodeError):
                connection.execute(
                    text("DELETE FROM app_kv_cache WHERE cache_key = :cache_key"),
                    {"cache_key": key},
                )
                return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            self.delete(key)
            return
        if not self._ensure_table():
            return
        now = time()
        expires_at = now + ttl_seconds if ttl_seconds is not None else None
        encoded = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
        with self._lock, self._engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO app_kv_cache(cache_key, value_json, expires_at, updated_at)
                    VALUES (:cache_key, :value_json, :expires_at, :updated_at)
                    ON CONFLICT(cache_key) DO UPDATE SET
                        value_json = excluded.value_json,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                """),
                {
                    "cache_key": key,
                    "value_json": encoded,
                    "expires_at": expires_at,
                    "updated_at": now,
                },
            )

    def delete(self, key: str) -> bool:
        if not self._ensure_table():
            return False
        with self._lock, self._engine.begin() as connection:
            result = connection.execute(
                text("DELETE FROM app_kv_cache WHERE cache_key = :cache_key"),
                {"cache_key": key},
            )
            return bool(result.rowcount)

    def delete_prefix(self, prefix: str) -> int:
        if not self._ensure_table():
            return 0
        escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        with self._lock, self._engine.begin() as connection:
            result = connection.execute(
                text("""
                    DELETE FROM app_kv_cache
                    WHERE cache_key LIKE :pattern ESCAPE '\\'
                """),
                {"pattern": f"{escaped}%"},
            )
            return max(0, int(result.rowcount or 0))

    def clear(self) -> None:
        if not self._ensure_table():
            return
        with self._lock, self._engine.begin() as connection:
            connection.execute(text("DELETE FROM app_kv_cache"))

    def prune_expired(self) -> int:
        """Delete expired rows and return the number removed."""
        if not self._ensure_table():
            return 0
        with self._lock, self._engine.begin() as connection:
            result = connection.execute(
                text("DELETE FROM app_kv_cache WHERE expires_at IS NOT NULL AND expires_at <= :now"),
                {"now": time()},
            )
            return max(0, int(result.rowcount or 0))
