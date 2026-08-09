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

from app.domain.workspace.workspace_service import WorkspaceService

router = APIRouter()
workspace_service = WorkspaceService()

# Global repository instance
media_repository: MediaRepository = SqliteMediaRepository()

# ---------------------------------------------------------------------------
# Upload safety limits & modality detection
# ---------------------------------------------------------------------------
MAX_DOCUMENT_SIZE_MB = 100.0
MAX_DOCUMENT_SIZE_BYTES = int(MAX_DOCUMENT_SIZE_MB * 1024 * 1024)
MAX_MEDIA_SIZE_BYTES = 2 * 1024 * 1024 * 1024  # 2GB for video/audio

DOCUMENT_EXTENSIONS = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".xls", ".xlsx", ".epub", ".md", ".txt", ".odt", ".ods", ".odp"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}


def _detect_media_type(filename: Optional[str], content_type: Optional[str] = None) -> MediaType:
    ext = os.path.splitext(filename or "")[1].lower()
    if ext in DOCUMENT_EXTENSIONS:
        return MediaType.DOCUMENT
    if ext in AUDIO_EXTENSIONS:
        return MediaType.AUDIO
    if content_type:
        if content_type.startswith("application/pdf") or "pdf" in content_type:
            return MediaType.DOCUMENT
        if content_type.startswith("audio/"):
            return MediaType.AUDIO
    return MediaType.VIDEO


def _file_format(filename: Optional[str]) -> str:
    return os.path.splitext(filename or "")[1].lower().lstrip(".") or "unknown"

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

class MediaListResponse(BaseModel):
    id: str
    workspace_id: str
    title: str
    media_type: str
    file_size_bytes: int
    duration_seconds: float
    status: str
    created_at: Optional[str] = None

@router.post("/media/upload", response_model=MediaUploadResponse)
async def upload_media(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    workspace_id: str = Form("default"),
    title: Optional[str] = Form(None)
):
    media_id = f"med_{uuid.uuid4().hex[:8]}"
    item_title = title or file.filename or "Untitled Media"
    media_type = _detect_media_type(file.filename, file.content_type)

    max_bytes = MAX_DOCUMENT_SIZE_BYTES if media_type == MediaType.DOCUMENT else MAX_MEDIA_SIZE_BYTES
    size_label = "100MB" if media_type == MediaType.DOCUMENT else "2GB"

    os.makedirs(settings.UPLOADS_DIR, exist_ok=True)
    file_location = os.path.join(settings.UPLOADS_DIR, f"{media_id}_{file.filename}")

    total_bytes = 0
    try:
        with open(file_location, "wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"{item_title} exceeds the upload safety limit ({size_label}). "
                            f"File is {total_bytes / (1024 * 1024):.1f} MB. "
                            "Split the file into smaller parts and upload again."
                        )
                    )
                f.write(chunk)
    except HTTPException:
        if os.path.exists(file_location):
            try:
                os.remove(file_location)
            except OSError:
                pass
        raise

    media_item = MediaItem(
        id=media_id,
        workspace_id=workspace_id,
        title=item_title,
        file_path=file_location,
        media_type=media_type,
        file_size_bytes=total_bytes,
        status=ProcessingStatus.UPLOADED
    )
    media_repository.upsert(media_item)
    workspace_service.add_media_to_workspace(workspace_id, media_id)

    # Enqueue job in persistent SQLite ingestion worker
    from app.main import persistent_ingestion_worker
    if persistent_ingestion_worker:
        persistent_ingestion_worker.enqueue_media(
            media_id, workspace_id, file_location,
            media_type=media_type.value,
            file_format=_file_format(file.filename)
        )
    else:
        async def trigger_event():
            await event_bus.publish(DomainEvent(
                event_type="DocumentUploadedEvent" if media_type == MediaType.DOCUMENT else "MediaUploadedEvent",
                aggregate_id=media_id,
                payload={
                    "media_id": media_id,
                    "workspace_id": workspace_id,
                    "file_path": file_location,
                    "file_format": _file_format(file.filename),
                    "media_type": media_type.value
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

class DocumentPageDTO(BaseModel):
    page_number: int
    text: str
    page_type: str
    section_title: Optional[str] = None

class DocumentPagesResponse(BaseModel):
    media_id: str
    total_pages: int
    pages: List[DocumentPageDTO]

@router.get("/media/{media_id}/pages", response_model=DocumentPagesResponse)
def get_document_pages(media_id: str):
    """Fetch parsed document page sections for a document media item."""
    pages = media_repository.get_pages(media_id)
    return DocumentPagesResponse(
        media_id=media_id,
        total_pages=len(pages),
        pages=pages
    )

@router.get("/media/workspace/{workspace_id}", response_model=List[MediaListResponse])
def list_workspace_media(workspace_id: str):
    """List all media items (video/audio/document) in a workspace."""
    items = media_repository.list_by_workspace(workspace_id)
    return [
        MediaListResponse(
            id=item.id,
            workspace_id=item.workspace_id,
            title=item.title,
            media_type=item.media_type.value,
            file_size_bytes=item.file_size_bytes,
            duration_seconds=item.duration_seconds,
            status=item.status.value,
            created_at=item.created_at.isoformat() if item.created_at else None,
        )
        for item in items
    ]

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

