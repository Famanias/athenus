import asyncio
import hashlib
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from app.application.events.progress_store import progress_store
from app.application.repositories.media_repository import MediaRepository
from app.application.repositories.sqlite_media_repository import SqliteMediaRepository
from app.core.config import settings
from app.domain.media.entities import MediaItem, MediaType, ProcessingStatus
from app.infrastructure.events.event_bus import DomainEvent, event_bus
from app.infrastructure.cache.runtime import application_memory_cache, persistent_cache

from app.domain.workspace.workspace_service import WorkspaceService

router = APIRouter()
workspace_service = WorkspaceService(
    application_cache=application_memory_cache,
    persistent_cache=persistent_cache,
)

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
    filename = file.filename or "Untitled"
    ext = os.path.splitext(filename)[1].lower()

    doc_exts = {".pdf", ".docx", ".pptx", ".xlsx", ".epub", ".md", ".txt"}
    audio_exts = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".webm", ".ogg"}


    is_doc = ext in doc_exts
    is_audio = ext in audio_exts

    media_id = f"doc_{uuid.uuid4().hex[:8]}" if is_doc else f"med_{uuid.uuid4().hex[:8]}"
    item_title = title or filename

    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    file_location = os.path.join(settings.UPLOADS_DIR, f"{media_id}_{filename}")
    
    with open(file_location, "wb") as f:
        content = await file.read()
        f.write(content)

    file_size = len(content)

    # Enforce safety size limits (100MB for documents, 2GB for video/audio)
    if is_doc and file_size > 100 * 1024 * 1024:
        os.remove(file_location)
        raise HTTPException(
            status_code=413,
            detail="File size exceeds maximum allowed safety limit of 100MB for documents."
        )

    if is_doc:
        media_type = MediaType.DOCUMENT
    elif is_audio:
        media_type = MediaType.AUDIO
    else:
        media_type = MediaType.VIDEO

    media_item = MediaItem(
        id=media_id,
        workspace_id=workspace_id,
        title=item_title,
        file_path=file_location,
        media_type=media_type,
        file_size_bytes=file_size,
        status=ProcessingStatus.UPLOADED
    )
    media_repository.upsert(media_item)
    workspace_service.add_media_to_workspace(workspace_id, media_id)

    # Enqueue job in persistent SQLite ingestion worker
    import app.main
    if app.main.persistent_ingestion_worker:
        app.main.persistent_ingestion_worker.enqueue_media(media_id, workspace_id, file_location)
    else:
        event_name = "DocumentUploadedEvent" if is_doc else "MediaUploadedEvent"
        async def trigger_event():
            await event_bus.publish(DomainEvent(
                event_type=event_name,
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

class MediaJobResponse(BaseModel):
    job_id: str
    media_id: str
    workspace_id: str
    title: str
    status: str
    stage: str
    progress: int
    message: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

@router.get("/media/workspace/{workspace_id}/jobs", response_model=List[MediaJobResponse])
def get_workspace_media_jobs(workspace_id: str):
    """Retrieve all persistent ingestion jobs for a workspace sorted by created_at."""
    from app.infrastructure.db.session import engine
    try:
        from sqlmodel import Session, select
    except ImportError:
        from sqlalchemy import select
        from sqlalchemy.orm import Session

    if not engine or not Session or not select:
        return []
    try:
        from app.infrastructure.db.models import ArtifactJobTable, MediaItemTable
        with Session(engine) as session:
            stmt = (
                select(ArtifactJobTable)
                .where(
                    ArtifactJobTable.workspace_id == workspace_id,
                    ArtifactJobTable.artifact_type == "ingestion",
                )
                .order_by(ArtifactJobTable.created_at.desc())
            )
            jobs = session.scalars(stmt).all() if hasattr(session, "scalars") else session.exec(stmt).all()
            
            media_map = {}
            media_items = media_repository.list_workspace_media(workspace_id)
            for m in media_items:
                media_map[m.id] = m.title

            res = []
            for j in jobs:
                res.append(
                    MediaJobResponse(
                        job_id=j.id,
                        media_id=j.target_key,
                        workspace_id=j.workspace_id,
                        title=media_map.get(j.target_key, f"Video {j.target_key[:8]}"),
                        status=j.status,
                        stage=j.stage or "queued",
                        progress=j.progress,
                        message=j.message,
                        error_message=j.error_message,
                        created_at=j.created_at.isoformat() if j.created_at else None,
                        updated_at=j.updated_at.isoformat() if j.updated_at else None,
                    )
                )
            return res
    except Exception:
        return []

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
def get_media_file(media_id: str, request: Request):
    """Serve the uploaded media file for playback in the video workspace."""
    item = media_repository.get(media_id)
    if not item or not item.file_path:
        raise HTTPException(status_code=404, detail="Media item not found")
    if not os.path.exists(item.file_path):
        raise HTTPException(status_code=404, detail="Media file not found on disk")
    stat = os.stat(item.file_path)
    etag = '"' + hashlib.sha256(
        f"{item.id}:{stat.st_size}:{stat.st_mtime_ns}".encode("utf-8")
    ).hexdigest() + '"'
    cache_headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=31536000, immutable",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    return FileResponse(
        item.file_path,
        filename=os.path.basename(item.file_path),
        headers=cache_headers,
    )


class MediaInfoResponse(BaseModel):
    """Read-only document/media metadata used by the frontend document
    viewer to dispatch the appropriate format renderer (PDF / image / text /
    fallback). This endpoint is purely informational and does NOT touch the
    ingestion pipeline (AnyDoc, RapidOCR, vector indexing, etc.).
    """
    media_id: str
    title: str
    file_path: str
    file_name: str
    media_type: str
    file_size_bytes: int
    mime_type: str
    url: str


def _infer_mime_type(file_path: str) -> str:
    """Best-effort MIME type inference from file extension."""
    import mimetypes
    mime, _ = mimetypes.guess_type(file_path)
    return mime or "application/octet-stream"


@router.get("/media/{media_id}/info", response_model=MediaInfoResponse)
def get_media_info(media_id: str, request: Request, response: Response):
    """Return file metadata for the document viewer to choose the correct
    renderer. Read-only — does not affect ingestion state."""
    item = media_repository.get(media_id)
    if not item or not item.file_path:
        raise HTTPException(status_code=404, detail="Media item not found")

    file_path = item.file_path
    file_name = os.path.basename(file_path)
    file_size = (
        os.path.getsize(file_path)
        if os.path.exists(file_path)
        else (item.file_size_bytes or 0)
    )
    mime_type = _infer_mime_type(file_path)

    info = MediaInfoResponse(
        media_id=item.id,
        title=item.title or file_name,
        file_path=file_path,
        file_name=file_name,
        media_type=item.media_type.value if hasattr(item.media_type, "value") else str(item.media_type),
        file_size_bytes=file_size,
        mime_type=mime_type,
        url=f"/api/v1/media/{item.id}/file",
    )
    encoded = info.model_dump_json() if hasattr(info, "model_dump_json") else info.json()
    etag = '"' + hashlib.sha256(encoded.encode("utf-8")).hexdigest() + '"'
    cache_headers = {
        "ETag": etag,
        "Cache-Control": "private, max-age=30, stale-while-revalidate=30",
    }
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=cache_headers)
    response.headers.update(cache_headers)
    return info


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
        # pyrefly: ignore [missing-import]
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

