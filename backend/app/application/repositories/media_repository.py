from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
from app.domain.media.entities import MediaItem, ProcessingStatus

class MediaRepository(ABC):
    """Abstract interface for Media asset storage and status management."""

    @abstractmethod
    def upsert(self, item: MediaItem) -> None:
        pass

    @abstractmethod
    def get(self, media_id: str) -> Optional[MediaItem]:
        pass

    @abstractmethod
    def update_status(
        self,
        media_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None
    ) -> None:
        pass

    @abstractmethod
    def save_transcript(self, media_id: str, segments: List[Dict[str, Any]]) -> None:
        pass

    @abstractmethod
    def get_transcript(self, media_id: str) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def list_by_workspace(self, workspace_id: str) -> List[MediaItem]:
        pass

    @abstractmethod
    def save_pages(self, media_id: str, workspace_id: str, pages: List[Dict[str, Any]]) -> None:
        """Persist parsed document page sections for a media/document item."""
        pass

    @abstractmethod
    def get_pages(self, media_id: str) -> List[Dict[str, Any]]:
        """Retrieve parsed document page sections ordered by page number."""
        pass


class InMemoryMediaRepository(MediaRepository):
    """Thread-safe concrete in-memory repository implementation."""

    def __init__(self) -> None:
        self._media_db: Dict[str, MediaItem] = {}
        self._transcripts_db: Dict[str, List[Dict[str, Any]]] = {}
        self._pages_db: Dict[str, List[Dict[str, Any]]] = {}

    def upsert(self, item: MediaItem) -> None:
        self._media_db[item.id] = item

    def get(self, media_id: str) -> Optional[MediaItem]:
        return self._media_db.get(media_id)

    def update_status(
        self,
        media_id: str,
        status: ProcessingStatus,
        error_message: Optional[str] = None
    ) -> None:
        item = self._media_db.get(media_id)
        if item:
            item.status = status
            if error_message:
                item.error_message = error_message

    def save_transcript(self, media_id: str, segments: List[Dict[str, Any]]) -> None:
        self._transcripts_db[media_id] = segments

    def get_transcript(self, media_id: str) -> List[Dict[str, Any]]:
        return self._transcripts_db.get(media_id, [])

    def list_by_workspace(self, workspace_id: str) -> List[MediaItem]:
        return [
            item for item in self._media_db.values()
            if item.workspace_id == workspace_id
        ]

    def save_pages(self, media_id: str, workspace_id: str, pages: List[Dict[str, Any]]) -> None:
        self._pages_db[media_id] = pages

    def get_pages(self, media_id: str) -> List[Dict[str, Any]]:
        return self._pages_db.get(media_id, [])
