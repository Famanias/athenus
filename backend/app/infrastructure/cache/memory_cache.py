from collections import OrderedDict
from dataclasses import dataclass
from threading import RLock
from time import monotonic
from typing import Any, Callable, Optional

from app.domain.common.cache_interface import ICacheStore


@dataclass
class _CacheEntry:
    value: Any
    expires_at: Optional[float]


class MemoryCacheAdapter(ICacheStore):
    """Thread-safe, bounded LRU cache with per-entry TTL support."""

    def __init__(
        self,
        maxsize: int = 1000,
        clock: Callable[[], float] = monotonic,
    ) -> None:
        if maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize
        self._clock = clock
        self._entries: "OrderedDict[str, _CacheEntry]" = OrderedDict()
        self._lock = RLock()

    def _is_expired(self, entry: _CacheEntry, now: float) -> bool:
        return entry.expires_at is not None and entry.expires_at <= now

    def _prune_expired(self, now: float) -> None:
        expired = [
            key for key, entry in self._entries.items()
            if self._is_expired(entry, now)
        ]
        for key in expired:
            self._entries.pop(key, None)

    def get(self, key: str) -> Optional[Any]:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if self._is_expired(entry, self._clock()):
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return entry.value

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        if ttl_seconds is not None and ttl_seconds <= 0:
            self.delete(key)
            return
        with self._lock:
            now = self._clock()
            self._prune_expired(now)
            expires_at = now + ttl_seconds if ttl_seconds is not None else None
            self._entries[key] = _CacheEntry(value=value, expires_at=expires_at)
            self._entries.move_to_end(key)
            while len(self._entries) > self.maxsize:
                self._entries.popitem(last=False)

    def delete(self, key: str) -> bool:
        with self._lock:
            return self._entries.pop(key, None) is not None

    def delete_prefix(self, prefix: str) -> int:
        with self._lock:
            keys = [key for key in self._entries if key.startswith(prefix)]
            for key in keys:
                self._entries.pop(key, None)
            return len(keys)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()

    def __len__(self) -> int:
        with self._lock:
            self._prune_expired(self._clock())
            return len(self._entries)
