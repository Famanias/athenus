import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session


class ProgressStore:
    """Central store tracking media ingestion snapshots and broadcasting SSE updates."""

    def __init__(self) -> None:
        self._snapshots: Dict[str, Dict[str, Any]] = {}
        self._listeners: Set[Callable[[str, Dict[str, Any]], None]] = set()

    def record_stage_progress(
        self,
        media_id: str,
        stage: str,
        progress: int,
        message: str,
        status: str = "processing",
        error: Optional[str] = None
    ) -> Dict[str, Any]:
        """Record or update stage progress, persist audit log to SQLite, and emit snapshot event."""
        existing = self._snapshots.get(media_id, {})
        stage_history = existing.get("stage_history", {})
        stage_history[stage] = {
            "progress": progress,
            "message": message,
            "status": status,
            "updated_at": datetime.utcnow().isoformat()
        }

        snapshot = {
            "media_id": media_id,
            "current_stage": stage,
            "overall_progress": progress,
            "message": message,
            "status": status,
            "error": error,
            "stage_history": stage_history,
            "timestamp": datetime.utcnow().isoformat()
        }

        self._snapshots[media_id] = snapshot

        # Persist audit record to SQLite ProcessingLogTable
        if engine and Session:
            try:
                from app.infrastructure.db.models import MediaItemTable, ProcessingLogTable
                with Session(engine) as session:
                    db_media = session.get(MediaItemTable, media_id)
                    workspace_id = db_media.workspace_id if db_media else "default"
                    log_entry = ProcessingLogTable(
                        media_id=media_id,
                        workspace_id=workspace_id,
                        stage=stage,
                        status=status,
                        progress=progress,
                        message=message,
                        error_message=error
                    )
                    session.add(log_entry)
                    session.commit()
            except Exception:
                pass

        # Notify listeners synchronously/asynchronously
        for listener in list(self._listeners):
            try:
                listener(media_id, snapshot)
            except Exception:
                pass

        return snapshot

    def snapshot(self, media_id: str) -> Optional[Dict[str, Any]]:
        """Return the current progress snapshot for a media item."""
        return self._snapshots.get(media_id)

    def is_complete(self, media_id: str) -> bool:
        """Check if media processing is complete."""
        snap = self.snapshot(media_id)
        return snap is not None and snap.get("status") == "completed"

    def subscribe(self, listener: Callable[[str, Dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe to progress updates. Returns unsubscribe function."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)


# System-wide singleton progress store
progress_store = ProgressStore()
