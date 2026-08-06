import asyncio
import os
import shutil
from typing import Dict, Any
from fastapi import HTTPException
from app.application.events.progress_store import progress_store
from app.domain.workspace.workspace_service import WorkspaceService
from app.infrastructure.adapters.qdrant_adapter import EmbeddedQdrantVectorStoreAdapter
from app.infrastructure.db.models import (
    MediaItemTable,
    TranscriptChunkTable,
    TranscriptSegmentTable,
    ChatSessionTable,
    ChatMessageTable,
    ProcessingLogTable,
    KnowledgeConceptTable,
    KnowledgeRelationTable,
    ConceptAliasTable,
    ArtifactJobTable,
    FlashcardDeckTable,
    FlashcardTable,
    FlashcardReviewTable,
    QuizTable,
    QuizQuestionTable,
    QuizAttemptTable,
    WorkspaceAnalyticsTable,
    ConceptMasteryTable,
    StudySessionTable,
    WorkspaceTable,
    SystemSettings,
)
from app.infrastructure.db.session import engine

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


class SystemResetService:
    """Service orchestrating atomic system resets (Clear my Data / Factory Reset)."""

    _reset_lock = asyncio.Lock()

    def __init__(self) -> None:
        self.vector_store = EmbeddedQdrantVectorStoreAdapter()
        self.workspace_service = WorkspaceService()

    async def perform_factory_reset(self) -> Dict[str, Any]:
        if self._reset_lock.locked():
            raise HTTPException(status_code=409, detail="System reset is already in progress.")

        async with self._reset_lock:
            # 1. Clear in-memory active tasks/snapshots
            progress_store._snapshots.clear()

            # 2. Clear Qdrant Vector Collection Points
            try:
                if self.vector_store._client:
                    self.vector_store._client.delete_collection(self.vector_store.collection_name)
                    from qdrant_client.models import Distance, VectorParams
                    self.vector_store._client.create_collection(
                        collection_name=self.vector_store.collection_name,
                        vectors_config=VectorParams(size=384, distance=Distance.COSINE)
                    )
                self.vector_store._fallback_memory.clear()
            except Exception:
                pass

            # 3. Purge ALL SQLite Tables (preserving table structures)
            if engine and Session:
                try:
                    with Session(engine) as session:
                        for table in [
                            FlashcardReviewTable,
                            FlashcardTable,
                            FlashcardDeckTable,
                            QuizAttemptTable,
                            QuizQuestionTable,
                            QuizTable,
                            ConceptMasteryTable,
                            WorkspaceAnalyticsTable,
                            StudySessionTable,
                            ConceptAliasTable,
                            KnowledgeRelationTable,
                            KnowledgeConceptTable,
                            ArtifactJobTable,
                            ChatMessageTable,
                            ChatSessionTable,
                            TranscriptSegmentTable,
                            TranscriptChunkTable,
                            ProcessingLogTable,
                            MediaItemTable,
                            WorkspaceTable,
                            SystemSettings,
                        ]:
                            statement = select(table)
                            records = session.scalars(statement).all() if hasattr(session, "scalars") else session.exec(statement).all()
                            for r in records:
                                session.delete(r)
                        session.commit()
                except Exception as e:
                    raise HTTPException(status_code=500, detail=f"Failed to reset SQLite database: {str(e)}")

            # 4. Delete Uploaded Video/Audio Files from Disk
            possible_dirs = {
                os.path.abspath(os.path.join(".", "data", "uploads")),
                os.path.abspath(os.path.join("..", "data", "uploads")),
                os.path.join(".", "data", "uploads"),
            }
            for uploads_dir in possible_dirs:
                if os.path.exists(uploads_dir):
                    try:
                        for filename in os.listdir(uploads_dir):
                            file_path = os.path.join(uploads_dir, filename)
                            if os.path.isfile(file_path) or os.path.islink(file_path):
                                try:
                                    os.unlink(file_path)
                                except Exception:
                                    pass
                            elif os.path.isdir(file_path):
                                try:
                                    shutil.rmtree(file_path)
                                except Exception:
                                    pass
                    except Exception:
                        pass

            # 5. Re-create Clean Default Workspace in SQLite
            self.workspace_service._workspaces.clear()
            self.workspace_service.create_workspace(
                name="Machine Learning & Deep Learning",
                description="Default learning workspace for indexed lecture videos.",
                icon="psychology",
                workspace_id="default"
            )

            return {
                "status": "ok",
                "message": "Application data successfully cleared. Default workspace re-initialized."
            }
