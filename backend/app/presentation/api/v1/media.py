import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.application.events.progress_store import progress_store
from app.application.repositories.media_repository import MediaRepository
from app.application.repositories.sqlite_media_repository import SqliteMediaRepository
from app.core.config import settings
from app.domain.media.entities import MediaItem, MediaType, ProcessingStatus
from app.infrastructure.events.event_bus import DomainEvent, event_bus

router = APIRouter()

# Global repository instance
media_repository: MediaRepository = SqliteMediaRepository()

class MediaUploadResponse(BaseModel):
    media_id: str
    workspace_id: str
    title: str
    status: str

class MediaStatusResponse(BaseModel):
    media_id: str
    status: str
    overall_progress: int = 0
    message: str = ""
    error_message: Optional[str] = None

class TranscriptResponse(BaseModel):
    media_id: str
    full_text: str
    segments: List[Dict[str, Any]]

@router.post("/media/upload", response_model=MediaUploadResponse)
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace_id: str = Form("default"),
    title: Optional[str] = Form(None)
):
    media_id = f"med_{uuid.uuid4().hex[:8]}"
    item_title = title or file.filename or "Untitled Video"
    
    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    file_location = os.path.join(settings.UPLOADS_DIR, f"{media_id}_{file.filename}")
    
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    media_item = MediaItem(
        id=media_id,
        workspace_id=workspace_id,
        title=item_title,
        file_path=file_location,
        media_type=MediaType.VIDEO,
        file_size_bytes=len(content),
        status=ProcessingStatus.UPLOADED
    )
    media_repository.upsert(media_item)

    async def trigger_event():
        await event_bus.publish(DomainEvent(
            event_type="MediaUploadedEvent",
            aggregate_id=media_id,
            payload={
                "media_id": media_id,
                "workspace_id": workspace_id,
                "file_path": file_location
            }
        ))

    background_tasks.add_task(trigger_event)

    return MediaUploadResponse(
        media_id=media_id,
        workspace_id=workspace_id,
        title=item_title,
        status=media_item.status.value
    )

@router.get("/media/{media_id}/status", response_model=MediaStatusResponse)
def get_media_status(media_id: str):
    item = media_repository.get(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    
    snap = progress_store.snapshot(media_id) or {}
    return MediaStatusResponse(
        media_id=item.id,
        status=item.status.value,
        overall_progress=snap.get("overall_progress", 100 if item.status == ProcessingStatus.COMPLETED else 0),
        message=snap.get("message", f"Status: {item.status.value}"),
        error_message=item.error_message or snap.get("error")
    )

@router.get("/media/{media_id}/transcript", response_model=TranscriptResponse)
def get_transcript(media_id: str):
    segments = media_repository.get_transcript(media_id)
    full_text = " ".join([s.get("text", "") for s in segments])
    return TranscriptResponse(
        media_id=media_id,
        full_text=full_text,
        segments=segments
    )

@router.get("/media/{media_id}/file")
def get_media_file(media_id: str):
    """Serve the uploaded media file for playback in the video workspace."""
    item = media_repository.get(media_id)
    if not item or not item.file_path:
        raise HTTPException(status_code=404, detail="Media item not found")
    if not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Media file not found on disk")
    return FileResponse(item.file_path, filename=os.path.basename(item.file_path))

@router.get("/media/{media_id}/stream")
async def stream_media_processing_events(media_id: str):
    """Server-Sent Events (SSE) endpoint emitting real-time stage progress updates."""
    async def event_generator():
        queue: asyncio.Queue[Dict[str, Any]] = asyncio.Queue()

        # Replay latest snapshot immediately if present
        initial_snap = progress_store.snapshot(media_id)
        if initial_snap:
            yield f"data: {json.dumps(initial_snap)}\n\n"
            if initial_snap.get("status") in ("completed", "failed"):
                return

        def listener(m_id: str, snapshot: Dict[str, Any]):
            if m_id == media_id:
                queue.put_nowait(snapshot)

        unsubscribe = progress_store.subscribe(listener)

        try:
            while True:
                try:
                    snap = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(snap)}\n\n"
                    if snap.get("status") in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    # Heartbeat ping to keep connection alive
                    yield ": ping\n\n"
        finally:
            unsubscribe()

    return StreamingResponse(event_generator(), media_type="text/event-stream")

class ProcessingLogDTO(BaseModel):
    id: int
    media_id: str
    workspace_id: str
    stage: str
    status: str
    progress: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str

@router.get("/media/{media_id}/history", response_model=List[ProcessingLogDTO])
def get_media_processing_history(media_id: str):
    """Fetch complete timestamped ingestion processing log history for a media asset."""
    from app.infrastructure.db.models import ProcessingLogTable
    from app.infrastructure.db.session import engine
    try:
        from sqlmodel import Session, select
    except ImportError:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

    if not engine or not Session or not select:
        return []

    try:
        with Session(engine) as session:
            statement = select(ProcessingLogTable).where(ProcessingLogTable.media_id == media_id).order_by(ProcessingLogTable.created_at)
            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
            return [
                ProcessingLogDTO(
                    id=r.id or 0,
                    media_id=r.media_id,
                    workspace_id=r.workspace_id,
                    stage=r.stage,
                    status=r.status,
                    progress=r.progress,
                    message=r.message,
                    error_message=r.error_message,
                    timestamp=r.created_at.isoformat() if r.created_at else ""
                )
                for r in records
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

