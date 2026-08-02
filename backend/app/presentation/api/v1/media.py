import asyncio
import os
import uuid
from fastapi import APIRouter, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from app.core.config import settings
from app.domain.media.entities import MediaItem, ProcessingStatus, MediaType
from app.infrastructure.events.event_bus import event_bus, DomainEvent

router = APIRouter()

# In-memory store for status tracking during development
in_memory_media_db: Dict[str, MediaItem] = {}
in_memory_transcripts_db: Dict[str, List[Dict[str, Any]]] = {}

class MediaUploadResponse(BaseModel):
    media_id: str
    workspace_id: str
    title: str
    status: str

class MediaStatusResponse(BaseModel):
    media_id: str
    status: str
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
        status=ProcessingStatus.PENDING
    )
    in_memory_media_db[media_id] = media_item

    # Emit MediaUploadedEvent asynchronously
    async def trigger_event():
        media_item.status = ProcessingStatus.TRANSCRIBING
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
    item = in_memory_media_db.get(media_id)
    if not item:
        raise HTTPException(status_code=404, detail="Media item not found")
    return MediaStatusResponse(
        media_id=item.id,
        status=item.status.value,
        error_message=item.error_message
    )

@router.get("/media/{media_id}/transcript", response_model=TranscriptResponse)
def get_transcript(media_id: str):
    segments = in_memory_transcripts_db.get(media_id, [])
    full_text = " ".join([s.get("text", "") for s in segments])
    return TranscriptResponse(
        media_id=media_id,
        full_text=full_text,
        segments=segments
    )

@router.get("/media/{media_id}/stream")
async def stream_media_processing_events(media_id: str):
    """Server-Sent Events (SSE) endpoint for live media processing updates."""
    async def event_generator():
        yield f"data: {{'media_id': '{media_id}', 'status': 'processing'}}\n\n"
        await asyncio.sleep(1)
        item = in_memory_media_db.get(media_id)
        status_val = item.status.value if item else "completed"
        yield f"data: {{'media_id': '{media_id}', 'status': '{status_val}'}}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
