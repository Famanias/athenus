from app.application.events.progress_store import ProgressStore
from app.application.repositories.media_repository import MediaRepository
from app.domain.media.entities import ProcessingStatus
from app.domain.telemetry.telemetry_service import TelemetryService
from app.infrastructure.events.event_bus import DomainEvent

telemetry = TelemetryService()

async def on_media_uploaded(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    repo.update_status(media_id, ProcessingStatus.UPLOADED)
    progress.record_stage_progress(
        media_id=media_id,
        stage="upload",
        progress=100,
        message="Media uploaded successfully.",
        status="processing"
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage="queued",
        progress=5,
        message="File uploaded. Enqueued in persistent ingestion queue.",
        status="queued"
    )

async def on_processing_started(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    stage = event.payload.get("stage", "audio_extraction")
    repo.update_status(media_id, ProcessingStatus.AUDIO_EXTRACTION)
    progress.record_stage_progress(
        media_id=media_id,
        stage=stage,
        progress=event.payload.get("progress", 10),
        message=event.payload.get("message", "Extracting 16kHz mono WAV audio..."),
        status="processing"
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage=stage,
        progress=25,
        message=event.payload.get("message", "Extracting 16kHz mono WAV audio track..."),
        status="processing"
    )

async def on_stage_progress(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    stage = event.payload.get("stage", "transcription")
    progress_val = event.payload.get("progress", 50)
    message = event.payload.get("message", "Processing stage...")
    
    status_map = {
        "audio_extraction": ProcessingStatus.AUDIO_EXTRACTION,
        "transcription": ProcessingStatus.TRANSCRIBING,
        "chunking": ProcessingStatus.CHUNKING,
        "vector_indexing": ProcessingStatus.INDEXING,
    }
    target_status = status_map.get(stage, ProcessingStatus.TRANSCRIBING)
    repo.update_status(media_id, target_status)
    
    progress.record_stage_progress(
        media_id=media_id,
        stage=stage,
        progress=progress_val,
        message=message,
        status="processing"
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage=stage,
        progress=progress_val,
        message=message,
        status="processing"
    )

async def on_transcript_completed(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    segments = event.payload.get("segments", [])
    repo.save_transcript(media_id, segments)
    repo.update_status(media_id, ProcessingStatus.CHUNKING)
    progress.record_stage_progress(
        media_id=media_id,
        stage="transcription",
        progress=100,
        message="Speech transcription completed successfully.",
        status="processing"
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage="transcription",
        progress=60,
        message="Speech transcription completed.",
        status="processing"
    )

async def on_chunks_indexed(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    chunk_count = event.payload.get("chunk_count", 0)
    repo.update_status(media_id, ProcessingStatus.COMPLETED)
    progress.record_stage_progress(
        media_id=media_id,
        stage="vector_indexing",
        progress=100,
        message=f"Indexed {chunk_count} transcript chunks into Embedded Qdrant.",
        status="completed"
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage="vector_indexing",
        progress=85,
        message=f"Indexed {chunk_count} transcript chunks into Embedded Qdrant.",
        status="processing"
    )

async def on_document_parsed(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    document_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    pages = event.payload.get("pages", [])
    repo.save_pages(document_id, workspace_id, pages)
    progress.record_stage_progress(
        media_id=document_id,
        stage="document_parsing",
        progress=100,
        message="Document parsed successfully.",
        status="processing"
    )
    telemetry.record_progress(
        media_id=document_id,
        workspace_id=workspace_id,
        stage="document_parsing",
        progress=100,
        message="Document parsed successfully.",
        status="processing"
    )

async def on_processing_failed(event: DomainEvent, repo: MediaRepository, progress: ProgressStore) -> None:
    media_id = event.aggregate_id
    workspace_id = event.payload.get("workspace_id", "default")
    raw_err = event.payload.get("error")
    error_msg = str(raw_err).strip() if (raw_err and str(raw_err).strip()) else "Unknown ingestion error occurred."
    failed_stage = event.payload.get("stage", "pipeline")
    repo.update_status(media_id, ProcessingStatus.FAILED, error_message=error_msg)
    progress.record_stage_progress(
        media_id=media_id,
        stage=failed_stage,
        progress=0,
        message=f"Pipeline processing failed: {error_msg}",
        status="failed",
        error=error_msg
    )
    telemetry.record_progress(
        media_id=media_id,
        workspace_id=workspace_id,
        stage=failed_stage,
        progress=0,
        message=f"Pipeline processing failed: {error_msg}",
        status="failed",
        error=error_msg
    )
