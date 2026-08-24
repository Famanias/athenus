from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheStore(ABC):
    """Small, storage-independent key-value cache interface.

    Values must be JSON serializable when the persistent SQLite adapter is used.
    Implementations treat an omitted TTL as an entry without automatic expiry.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """Return a live value, or ``None`` when absent or expired."""

    @abstractmethod
    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        """Insert or replace a value."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Delete one entry and report whether it existed."""

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all entries whose keys start with ``prefix``."""

    @abstractmethod
    def clear(self) -> None:
        """Delete every entry in this store."""


class NullCacheStore(ICacheStore):
    """No-op cache used when a composition root does not provide an adapter."""

    def get(self, key: str) -> Optional[Any]:
        return None

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: Optional[float] = None,
    ) -> None:
        return None

    def delete(self, key: str) -> bool:
        return False

    def delete_prefix(self, prefix: str) -> int:
        return 0

    def clear(self) -> None:
        return None
