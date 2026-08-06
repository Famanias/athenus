import os
from fastapi.testclient import TestClient
from app.infrastructure.db.session import init_db, engine
from app.infrastructure.db.models import (
    MediaItemTable,
    ChatMessageTable,
    WorkspaceTable,
    FlashcardDeckTable,
    FlashcardTable,
    FlashcardReviewTable,
    QuizTable,
    QuizQuestionTable,
    QuizAttemptTable,
    KnowledgeConceptTable,
    KnowledgeRelationTable,
    WorkspaceAnalyticsTable,
    ConceptMasteryTable,
    StudySessionTable,
)
from app.application.events.progress_store import progress_store
from app.main import app

try:
    from sqlmodel import Session, select
except ImportError:
    from sqlalchemy import select
    from sqlalchemy.orm import Session


def test_system_clear_data_factory_reset():
    init_db()
    client = TestClient(app)

    uploads_dir = os.path.join(".", "data", "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    dummy_file = os.path.join(uploads_dir, "test_purge.mp4")
    with open(dummy_file, "w") as f:
        f.write("dummy video binary content")

    assert os.path.exists(dummy_file)

    # 1. Populate database records across media, chat, flashcards, quizzes, concepts & analytics
    with Session(engine) as session:
        session.merge(WorkspaceTable(id="default", name="Default Workspace"))
        session.add(MediaItemTable(
            id="med_purge_1",
            workspace_id="default",
            title="Test Video to Delete",
            file_path=dummy_file
        ))
        session.add(ChatMessageTable(
            id="msg_purge_1",
            session_id="sess_1",
            workspace_id="default",
            sender="user",
            content="Delete me"
        ))
        
        # Flashcards
        session.add(FlashcardDeckTable(id="deck_purge_1", workspace_id="default", name="Purge Deck", version=1))
        session.add(FlashcardTable(id="card_purge_1", deck_id="deck_purge_1", workspace_id="default", front="Q", back="A"))
        session.add(FlashcardReviewTable(id="rev_purge_1", flashcard_id="card_purge_1", workspace_id="default", rating=3))
        
        # Quizzes
        session.add(QuizTable(id="quiz_purge_1", workspace_id="default", title="Purge Quiz", version=1))
        session.add(QuizQuestionTable(id="q_purge_1", quiz_id="quiz_purge_1", workspace_id="default", question_text="Q?", options_json="[]", explanation="E"))
        session.add(QuizAttemptTable(id="att_purge_1", quiz_id="quiz_purge_1", workspace_id="default", score=100.0))

        # Concepts & Analytics
        session.add(KnowledgeConceptTable(id="con_purge_1", workspace_id="default", name="React"))
        session.add(KnowledgeRelationTable(id="rel_purge_1", workspace_id="default", source_concept="con_purge_1", target_concept="con_purge_1"))
        session.merge(WorkspaceAnalyticsTable(workspace_id="default", total_media=1, total_concepts=1))
        session.merge(ConceptMasteryTable(concept_id="con_purge_1", workspace_id="default", mastery_level=0.8))
        session.add(StudySessionTable(id="stud_purge_1", workspace_id="default", activity_type="review"))

        session.commit()

    # Populate progress store
    progress_store.record_stage_progress("med_purge_1", "upload", 100, "Uploaded", "completed")

    # 2. Invoke POST /api/v1/system/clear-data
    res = client.post("/api/v1/system/clear-data")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"

    # 3. Assert ALL database tables purged
    with Session(engine) as session:
        for model in [
            MediaItemTable,
            ChatMessageTable,
            FlashcardDeckTable,
            FlashcardTable,
            FlashcardReviewTable,
            QuizTable,
            QuizQuestionTable,
            QuizAttemptTable,
            KnowledgeConceptTable,
            KnowledgeRelationTable,
            WorkspaceAnalyticsTable,
            ConceptMasteryTable,
            StudySessionTable,
        ]:
            records = session.scalars(select(model)).all() if hasattr(session, "scalars") else session.exec(select(model)).all()
            assert len(records) == 0, f"Table {model.__tablename__} was not purged!"

        # Assert only the default workspace is re-created
        ws_records = session.scalars(select(WorkspaceTable)).all() if hasattr(session, "scalars") else session.exec(select(WorkspaceTable)).all()
        assert len(ws_records) == 1
        assert any(w.id == "default" for w in ws_records)

    # 4. Assert API exposes exactly one workspace (no stale in-memory leftovers)
    ws_list = client.get("/api/v1/workspaces")
    assert ws_list.status_code == 200
    assert len(ws_list.json()) == 1
    assert ws_list.json()[0]["id"] == "default"

    # 5. Assert disk uploads purged
    assert not os.path.exists(dummy_file)

    # 6. Assert progress store reset
    assert len(progress_store._snapshots) == 0

