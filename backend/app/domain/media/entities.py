from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    COMPLETED = "completed"
    FAILED = "failed"

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
