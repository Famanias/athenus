from datetime import datetime
from typing import Optional

try:
    from sqlmodel import Field, SQLModel
    
    class WorkspaceTable(SQLModel, table=True):
        __tablename__ = "workspaces"
        id: str = Field(primary_key=True)
        name: str
        description: Optional[str] = None
        icon: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class MediaItemTable(SQLModel, table=True):
        __tablename__ = "media_items"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        title: str
        file_path: str
        media_type: str = "video"
        file_size_bytes: int = 0
        duration_seconds: float = 0.0
        status: str = "pending"
        error_message: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class TranscriptChunkTable(SQLModel, table=True):
        __tablename__ = "transcript_chunks"
        id: str = Field(primary_key=True)
        media_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        text: str
        start_time: float
        end_time: float
        chunk_index: int
        word_count: int = 0
        created_at: datetime = Field(default_factory=datetime.utcnow)

except ImportError:
    from dataclasses import dataclass, field

    @dataclass
    class WorkspaceTable:
        id: str
        name: str
        description: Optional[str] = None
        icon: Optional[str] = None
        created_at: datetime = field(default_factory=datetime.utcnow)
        updated_at: datetime = field(default_factory=datetime.utcnow)

    @dataclass
    class MediaItemTable:
        id: str
        workspace_id: str
        title: str
        file_path: str
        media_type: str = "video"
        file_size_bytes: int = 0
        duration_seconds: float = 0.0
        status: str = "pending"
        error_message: Optional[str] = None
        created_at: datetime = field(default_factory=datetime.utcnow)
        updated_at: datetime = field(default_factory=datetime.utcnow)

    @dataclass
    class TranscriptChunkTable:
        id: str
        media_id: str
        workspace_id: str
        text: str
        start_time: float
        end_time: float
        chunk_index: int
        word_count: int = 0
        created_at: datetime = field(default_factory=datetime.utcnow)
