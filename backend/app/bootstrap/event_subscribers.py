from app.application.events.media_event_handlers import (
    on_chunks_indexed,
    on_media_uploaded,
    on_processing_failed,
    on_processing_started,
    on_stage_progress,
    on_transcript_completed,
)
from app.application.events.progress_store import ProgressStore
from app.application.repositories.media_repository import MediaRepository
from app.infrastructure.events.event_bus import EventBus

def register_media_subscribers(
    event_bus: EventBus,
    repo: MediaRepository,
    progress_store: ProgressStore
) -> None:
    """Register all domain event subscribers linking event bus to repository and progress store."""

    event_bus.subscribe(
        "MediaUploadedEvent",
        lambda e: on_media_uploaded(e, repo, progress_store)
    )
    event_bus.subscribe(
        "ProcessingStartedEvent",
        lambda e: on_processing_started(e, repo, progress_store)
    )
    event_bus.subscribe(
        "StageProgressEvent",
        lambda e: on_stage_progress(e, repo, progress_store)
    )
    event_bus.subscribe(
        "TranscriptCompletedEvent",
        lambda e: on_transcript_completed(e, repo, progress_store)
    )
    event_bus.subscribe(
        "ChunksIndexedEvent",
        lambda e: on_chunks_indexed(e, repo, progress_store)
    )
    event_bus.subscribe(
        "ProcessingFailedEvent",
        lambda e: on_processing_failed(e, repo, progress_store)
    )
