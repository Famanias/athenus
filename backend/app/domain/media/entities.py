from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    AUDIO_EXTRACTION = "audio_extraction"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"

def validate_transition(current: ProcessingStatus, target: ProcessingStatus) -> bool:
    """Validates if status transition from current to target is allowed."""
    if current == target:
        return True
    if current == ProcessingStatus.FAILED:
        # Allow retry transitions from FAILED to any non-completed state
        return target != ProcessingStatus.COMPLETED
    if target == ProcessingStatus.FAILED:
        # Any non-terminal state can transition to FAILED
        return True
    
    # Normal forward pipeline progression
    allowed = {
        ProcessingStatus.PENDING: {ProcessingStatus.UPLOADED, ProcessingStatus.AUDIO_EXTRACTION, ProcessingStatus.TRANSCRIBING},
        ProcessingStatus.UPLOADED: {ProcessingStatus.AUDIO_EXTRACTION, ProcessingStatus.EXTRACTING_AUDIO, ProcessingStatus.TRANSCRIBING},
        ProcessingStatus.AUDIO_EXTRACTION: {ProcessingStatus.EXTRACTING_AUDIO, ProcessingStatus.TRANSCRIBING},
        ProcessingStatus.EXTRACTING_AUDIO: {ProcessingStatus.TRANSCRIBING},
        ProcessingStatus.TRANSCRIBING: {ProcessingStatus.CHUNKING, ProcessingStatus.EMBEDDING},
        ProcessingStatus.CHUNKING: {ProcessingStatus.EMBEDDING, ProcessingStatus.INDEXING},
        ProcessingStatus.EMBEDDING: {ProcessingStatus.INDEXING, ProcessingStatus.COMPLETED},
        ProcessingStatus.INDEXING: {ProcessingStatus.COMPLETED},
        ProcessingStatus.COMPLETED: set(),
    }
    return target in allowed.get(current, set())

class MediaType(str, Enum):
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"

@dataclass
class MediaItem:
    id: str
    workspace_id: str
    title: str
    file_path: str
    media_type: MediaType = MediaType.VIDEO
    file_size_bytes: int = 0
    duration_seconds: float = 0.0
    status: ProcessingStatus = ProcessingStatus.PENDING
    error_message: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
