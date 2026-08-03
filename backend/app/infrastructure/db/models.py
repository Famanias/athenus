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

    class WorkspaceTable(Base):
        __tablename__ = "workspaces"
        id = Column(String, primary_key=True)
        name = Column(String, nullable=False)
        description = Column(String, nullable=True)
        icon = Column(String, nullable=True)
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


