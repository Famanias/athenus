from datetime import datetime
from typing import Optional

try:
    from sqlmodel import Field, SQLModel

    class SystemSettings(SQLModel, table=True):
        __tablename__ = "system_settings"
        id: str = Field(default="global", primary_key=True)
        default_llm: str = "ollama"
        selected_ollama_model: Optional[str] = None
        active_models: Optional[str] = None
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
        # Artifact lifecycle observability
        status: str = "ready"  # pending | generating | ready | failed
        # Grounding & provenance contract
        media_id: Optional[str] = Field(default=None, index=True)
        source_chunk_ids: Optional[str] = None
        start_time: Optional[float] = None
        end_time: Optional[float] = None
        # Semantic dedup embedding (JSON-encoded 384-dim vector)
        embedding: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class KnowledgeRelationTable(SQLModel, table=True):
        __tablename__ = "knowledge_relations"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        source_concept: str = Field(index=True)
        target_concept: str = Field(index=True)
        relation_type: str = "relates_to"
        weight: float = 1.0
        media_id: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class ConceptAliasTable(SQLModel, table=True):
        __tablename__ = "concept_aliases"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        concept_id: str = Field(index=True)
        alias: str
        normalized: str = Field(index=True)
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class ArtifactJobTable(SQLModel, table=True):
        __tablename__ = "artifact_jobs"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        artifact_type: str = Field(index=True)  # graph | flashcards | quiz
        target_key: str = Field(index=True)  # media_id for graph; deck/quiz id otherwise
        status: str = "pending"  # pending | generating | ready | failed
        stage: Optional[str] = "queued"  # queued | collect_context | llm_generation | validation | persist | ready
        progress: int = 0
        message: Optional[str] = None
        error_message: Optional[str] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class FlashcardDeckTable(SQLModel, table=True):
        __tablename__ = "flashcard_decks"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        name: str
        version: int = Field(default=1)
        status: str = "ready"  # pending | generating | ready | failed
        media_ids: Optional[str] = None
        concept_ids: Optional[str] = None
        source_chunk_ids: Optional[str] = None
        card_count: int = 0
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class FlashcardTable(SQLModel, table=True):
        __tablename__ = "flashcards"
        id: str = Field(primary_key=True)
        deck_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        concept_id: Optional[str] = Field(default=None, index=True)
        card_type: str = "basic"  # basic | cloze | definition | true_false
        front: str
        back: Optional[str] = None
        cloze_text: Optional[str] = None
        options_json: Optional[str] = None
        # Grounding & provenance contract
        media_id: Optional[str] = Field(default=None, index=True)
        source_chunk_ids: Optional[str] = None
        start_time: Optional[float] = None
        end_time: Optional[float] = None
        # SM-2 scheduling state (initial values copied into reviews)
        ease_factor: float = 2.5
        interval_days: int = 0
        repetitions: int = 0
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class FlashcardReviewTable(SQLModel, table=True):
        __tablename__ = "flashcard_reviews"
        id: str = Field(primary_key=True)
        flashcard_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        rating: int = 0  # SM-2 quality 0-4 (hard->perfect) or 1-4 recall scale
        ease_factor: float = 2.5
        interval_days: int = 0
        repetitions: int = 0
        reviewed_at: datetime = Field(default_factory=datetime.utcnow)

    class QuizTable(SQLModel, table=True):
        __tablename__ = "quizzes"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        title: str
        version: int = Field(default=1)
        status: str = "ready"  # pending | generating | ready | failed
        concept_ids: Optional[str] = None
        source_chunk_ids: Optional[str] = None
        question_count: int = 0
        created_at: datetime = Field(default_factory=datetime.utcnow)
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class QuizQuestionTable(SQLModel, table=True):
        __tablename__ = "quiz_questions"
        id: str = Field(primary_key=True)
        quiz_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        concept_id: Optional[str] = Field(default=None, index=True)
        question_text: str
        options_json: str
        correct_index: int = 0
        explanation: str
        # Grounding & provenance contract
        media_id: Optional[str] = Field(default=None, index=True)
        source_chunk_ids: Optional[str] = None
        start_time: Optional[float] = None
        end_time: Optional[float] = None
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class QuizAttemptTable(SQLModel, table=True):
        __tablename__ = "quiz_attempts"
        id: str = Field(primary_key=True)
        quiz_id: str = Field(index=True)
        workspace_id: str = Field(index=True)
        version: int = 1
        score: float = 0.0
        total_questions: int = 0
        correct_count: int = 0
        answers_json: Optional[str] = None
        time_taken: float = 0.0
        created_at: datetime = Field(default_factory=datetime.utcnow)

    class WorkspaceAnalyticsTable(SQLModel, table=True):
        __tablename__ = "workspace_analytics"
        workspace_id: str = Field(primary_key=True)
        total_media: int = 0
        total_concepts: int = 0
        total_flashcards: int = 0
        total_quiz_attempts: int = 0
        total_reviews: int = 0
        avg_quiz_score: float = 0.0
        total_study_seconds: float = 0.0
        review_streak_days: int = 0
        last_activity_at: Optional[datetime] = None
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class ConceptMasteryTable(SQLModel, table=True):
        __tablename__ = "concept_mastery"
        concept_id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        concept_name: str = ""
        mastery_level: float = 0.0  # 0.0 .. 1.0
        review_count: int = 0
        quiz_correct: int = 0
        quiz_attempts: int = 0
        last_reviewed_at: Optional[datetime] = None
        updated_at: datetime = Field(default_factory=datetime.utcnow)

    class StudySessionTable(SQLModel, table=True):
        __tablename__ = "study_sessions"
        id: str = Field(primary_key=True)
        workspace_id: str = Field(index=True)
        activity_type: str = "review"  # review | quiz | graph | flashcard
        started_at: datetime = Field(default_factory=datetime.utcnow)
        ended_at: Optional[datetime] = None
        duration_seconds: float = 0.0
        created_at: datetime = Field(default_factory=datetime.utcnow)

except ImportError:
    from sqlalchemy import Column, String, Float, Integer, DateTime, Text
    from app.infrastructure.db.session import Base

    class SystemSettings(Base):
        __tablename__ = "system_settings"
        id = Column(String, primary_key=True, default="global")
        default_llm = Column(String, default="ollama")
        selected_ollama_model = Column(String, nullable=True)
        active_models = Column(Text, nullable=True)
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
        status = Column(String, default="ready")
        media_id = Column(String, index=True, nullable=True)
        source_chunk_ids = Column(Text, nullable=True)
        start_time = Column(Float, nullable=True)
        end_time = Column(Float, nullable=True)
        embedding = Column(Text, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class KnowledgeRelationTable(Base):
        __tablename__ = "knowledge_relations"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        source_concept = Column(String, index=True, nullable=False)
        target_concept = Column(String, index=True, nullable=False)
        relation_type = Column(String, default="relates_to")
        weight = Column(Float, default=1.0)
        media_id = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class ConceptAliasTable(Base):
        __tablename__ = "concept_aliases"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        concept_id = Column(String, index=True, nullable=False)
        alias = Column(String, nullable=False)
        normalized = Column(String, index=True, nullable=False)
        created_at = Column(DateTime, default=datetime.utcnow)

    class ArtifactJobTable(Base):
        __tablename__ = "artifact_jobs"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        artifact_type = Column(String, index=True, nullable=False)
        target_key = Column(String, index=True, nullable=False)
        status = Column(String, default="pending")
        stage = Column(String, nullable=True, default="queued")
        progress = Column(Integer, default=0)
        message = Column(String, nullable=True)
        error_message = Column(String, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class FlashcardDeckTable(Base):
        __tablename__ = "flashcard_decks"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        name = Column(String, nullable=False)
        version = Column(Integer, default=1)
        status = Column(String, default="ready")
        media_ids = Column(Text, nullable=True)
        concept_ids = Column(Text, nullable=True)
        source_chunk_ids = Column(Text, nullable=True)
        card_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class FlashcardTable(Base):
        __tablename__ = "flashcards"
        id = Column(String, primary_key=True)
        deck_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        concept_id = Column(String, index=True, nullable=True)
        card_type = Column(String, default="basic")
        front = Column(Text, nullable=False)
        back = Column(Text, nullable=True)
        cloze_text = Column(Text, nullable=True)
        options_json = Column(Text, nullable=True)
        media_id = Column(String, index=True, nullable=True)
        source_chunk_ids = Column(Text, nullable=True)
        start_time = Column(Float, nullable=True)
        end_time = Column(Float, nullable=True)
        ease_factor = Column(Float, default=2.5)
        interval_days = Column(Integer, default=0)
        repetitions = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)

    class FlashcardReviewTable(Base):
        __tablename__ = "flashcard_reviews"
        id = Column(String, primary_key=True)
        flashcard_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        rating = Column(Integer, default=0)
        ease_factor = Column(Float, default=2.5)
        interval_days = Column(Integer, default=0)
        repetitions = Column(Integer, default=0)
        reviewed_at = Column(DateTime, default=datetime.utcnow)

    class QuizTable(Base):
        __tablename__ = "quizzes"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        title = Column(String, nullable=False)
        version = Column(Integer, default=1)
        status = Column(String, default="ready")
        concept_ids = Column(Text, nullable=True)
        source_chunk_ids = Column(Text, nullable=True)
        question_count = Column(Integer, default=0)
        created_at = Column(DateTime, default=datetime.utcnow)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class QuizQuestionTable(Base):
        __tablename__ = "quiz_questions"
        id = Column(String, primary_key=True)
        quiz_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        concept_id = Column(String, index=True, nullable=True)
        question_text = Column(Text, nullable=False)
        options_json = Column(Text, nullable=False)
        correct_index = Column(Integer, default=0)
        explanation = Column(Text, nullable=False)
        media_id = Column(String, index=True, nullable=True)
        source_chunk_ids = Column(Text, nullable=True)
        start_time = Column(Float, nullable=True)
        end_time = Column(Float, nullable=True)
        created_at = Column(DateTime, default=datetime.utcnow)

    class QuizAttemptTable(Base):
        __tablename__ = "quiz_attempts"
        id = Column(String, primary_key=True)
        quiz_id = Column(String, index=True, nullable=False)
        workspace_id = Column(String, index=True, nullable=False)
        version = Column(Integer, default=1)
        score = Column(Float, default=0.0)
        total_questions = Column(Integer, default=0)
        correct_count = Column(Integer, default=0)
        answers_json = Column(Text, nullable=True)
        time_taken = Column(Float, default=0.0)
        created_at = Column(DateTime, default=datetime.utcnow)

    class WorkspaceAnalyticsTable(Base):
        __tablename__ = "workspace_analytics"
        workspace_id = Column(String, primary_key=True)
        total_media = Column(Integer, default=0)
        total_concepts = Column(Integer, default=0)
        total_flashcards = Column(Integer, default=0)
        total_quiz_attempts = Column(Integer, default=0)
        total_reviews = Column(Integer, default=0)
        avg_quiz_score = Column(Float, default=0.0)
        total_study_seconds = Column(Float, default=0.0)
        review_streak_days = Column(Integer, default=0)
        last_activity_at = Column(DateTime, nullable=True)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class ConceptMasteryTable(Base):
        __tablename__ = "concept_mastery"
        concept_id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        concept_name = Column(String, default="")
        mastery_level = Column(Float, default=0.0)
        review_count = Column(Integer, default=0)
        quiz_correct = Column(Integer, default=0)
        quiz_attempts = Column(Integer, default=0)
        last_reviewed_at = Column(DateTime, nullable=True)
        updated_at = Column(DateTime, default=datetime.utcnow)

    class StudySessionTable(Base):
        __tablename__ = "study_sessions"
        id = Column(String, primary_key=True)
        workspace_id = Column(String, index=True, nullable=False)
        activity_type = Column(String, default="review")
        started_at = Column(DateTime, default=datetime.utcnow)
        ended_at = Column(DateTime, nullable=True)
        duration_seconds = Column(Float, default=0.0)
        created_at = Column(DateTime, default=datetime.utcnow)
