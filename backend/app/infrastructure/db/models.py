from datetime import datetime
from typing import Optional

try:
    from sqlmodel import Field, SQLModel

    class SystemSettings(SQLModel, table=True):
        __tablename__ = "system_settings"
        id: str = Field(default="global", primary_key=True)
        default_llm: str = "ollama"
        selected_ollama_model: Optional[str] = None
        ollama_models_dir: Optional[str] = None
        default_stt: str = "faster-whisper"
        default_embedding: str = "BAAI/bge-small-en-v1.5"
        gpu_acceleration: bool = True
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class WorkspaceTable(SQLModel, table=True):
        __tablename__ = "workspaces"
        id: str = Field(primary_key=True)
        name: str
        description: Optional[str] = None
        icon: Optional[str] = None
        is_pinned: bool = False
        is_archived: bool = False
        settings_json: Optional[str] = None
        last_accessed_at: datetime = Field(default_factory=datetime.utcnow)
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

    class TranscriptSegmentTable(SQLModel, table=True):
        __tablename__ = "transcript_segments"
        id: Optional[int] = Field(default=None, primary_key=True)
        media_id: str = Field(index=True)
        start_time: float
        end_time: float
        text: str

    class ChatSessionTable(SQLModel, table=True):
        __tablename__ = "chat_sessions"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        title: str = "Chat Session"
        is_pinned: bool = False
        is_archived: bool = False
        last_message_at: Optional[datetime] = None
        message_count: int = 0
        preview_text: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class ChatMessageTable(SQLModel, table=True):
        __tablename__ = "chat_messages"
        id: str = Field(primary_key=True)
        session_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        sender: str
        content: str
        citations_json: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class ProcessingLogTable(SQLModel, table=True):
        __tablename__ = "processing_logs"
        id: Optional[int] = Field(default=None, primary_key=True)
        media_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        stage: str
        status: str = "processing"
        progress: int = 0
        message: Optional[str] = None
        error_message: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class KnowledgeConceptTable(SQLModel, table=True):
        __tablename__ = "knowledge_concepts"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        name: str = Field(index=True)
        description: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class KnowledgeRelationTable(SQLModel, table=True):
        __tablename__ = "knowledge_relations"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        source_concept: str = Field(index=True)
        target_concept: str = Field(index=True)
        relation_type: str = "relates_to"
        created_at: datetime = Field(default_factory=datetime.utcnow)

except ImportError:
    from sqlalchemy import Column, String, Float, Integer, DateTime, Text
    from app.infrastructure.db.session import Base

    class SystemSettings(Base):
        __tablename__ = "system_settings"
        id = Column(String, primary_key=True, default="global")
        default_llm = Column(String, default="ollama")
        selected_ollama_model = Column(String, nullable=True)
        ollama_models_dir = Column(String, nullable=True)
        default_stt = Column(String, default="faster-whisper")
        default_embedding = Column(String, default="BAAI/bge-small-en-v1.5")
        gpu_acceleration = Column(Integer, default=1)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class WorkspaceTable(Base):
        __tablename__ = "workspaces"
        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        description = Column(String, nullable=True)
        icon = Column(String, nullable=True)
        is_pinned = Column(Integer, default=0)
        is_archived = Column(Integer, default=0)
        settings_json = Column(String, nullable=True)
        last_accessed_at = Column(DateTime, default=datetime.utcnow)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class MediaItemTable(Base):
        __tablename__ = "media_items"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        title = Column(String, nullable=False)
        file_path = Column(String, nullable=False)
        media_type = Column(String, default="video")
        file_size_bytes = Column(Integer, default=0)
        duration_seconds = Column(Float, default=0.0)
        status = Column(String, default="pending")
        error_message = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class TranscriptChunkTable(Base):
        __tablename__ = "transcript_chunks"
        id = Column(String, primary_key=True)
        media_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        text = Column(Text, nullable=False)
        start_time = Column(Float, nullable=False)
        end_time = Column(Float, nullable=False)
        chunk_index = Column(Integer, nullable=False)
        word_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)

    class TranscriptSegmentTable(Base):
        __tablename__ = "transcript_segments"
        id = Column(Integer, primary_key=True, autoincrement=True)
        media_id = Column(String, index=True, nullable=False)
        start_time = Column(Float, nullable=False)
        end_time = Column(Float, nullable=False)
        text = Column(Text, nullable=False)

    class ChatSessionTable(Base):
        __tablename__ = "chat_sessions"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        title = Column(String, default="Chat Session")
        is_pinned = Column(Integer, default=0)
        is_archived = Column(Integer, default=0)
        last_message_at = Column(DateTime, nullable=True)
        message_count = Column(Integer, default=0)
        preview_text = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class ChatMessageTable(Base):
        __tablename__ = "chat_messages"
        id = Column(String, primary_key=True)
        session_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        sender = Column(String, nullable=False)
        content = Column(Text, nullable=False)
        citations_json = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class ProcessingLogTable(Base):
        __tablename__ = "processing_logs"
        id = Column(Integer, primary_key=True, autoincrement=True)
        media_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        stage = Column(String, nullable=False)
        status = Column(String, default="processing")
        progress = Column(Integer, default=0)
        message = Column(String, nullable=True)
        error_message = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class KnowledgeConceptTable(Base):
        __tablename__ = "knowledge_concepts"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        name = Column(String, index=True, nullable=False)
        description = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class KnowledgeRelationTable(Base):
        __tablename__ = "knowledge_relations"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        source_concept = Column(String, index=True, nullable=False)
        target_concept = Column(String, index=True, nullable=False)
        relation_type = Column(String, default="relates_to")
        created_at = Column(DateTime, default=datetime.utcnow)


