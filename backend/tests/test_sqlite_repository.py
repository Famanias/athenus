import pytest
from app.application.repositories.sqlite_media_repository import SqliteMediaRepository
from app.domain.media.entities import MediaItem, MediaType, ProcessingStatus
from app.domain.workspace.workspace_service import WorkspaceService
from app.infrastructure.db.session import init_db


@pytest.fixture(autouse=True)
def setup_database():
    init_db()


def test_sqlite_media_repository_crud():
    repo = SqliteMediaRepository()

    media_item = MediaItem(
        id="med_sqlite_test_1",
        workspace_id="default",
        title="SQLite Persistence Test Video",
        file_path="/tmp/test.mp4",
        media_type=MediaType.VIDEO,
        file_size_bytes=1024,
        status=ProcessingStatus.UPLOADED
    )

    # 1. Upsert
    repo.upsert(media_item)

    # 2. Get
    fetched = repo.get("med_sqlite_test_1")
    assert fetched is not None
    assert fetched.title == "SQLite Persistence Test Video"
    assert fetched.status == ProcessingStatus.UPLOADED

    # 3. Update Status
    repo.update_status("med_sqlite_test_1", ProcessingStatus.COMPLETED)
    updated = repo.get("med_sqlite_test_1")
    assert updated is not None
    assert updated.status == ProcessingStatus.COMPLETED

    # 4. Save & Get Transcript
    segments = [
        {"start_time": 0.0, "end_time": 5.0, "text": "Welcome to persistent Athenus."},
        {"start_time": 5.0, "end_time": 10.0, "text": "This transcript is stored in SQLite."}
    ]
    repo.save_transcript("med_sqlite_test_1", segments)
    fetched_segments = repo.get_transcript("med_sqlite_test_1")
    assert len(fetched_segments) == 2
    assert fetched_segments[0]["text"] == "Welcome to persistent Athenus."

    # 5. List by Workspace
    items = repo.list_by_workspace("default")
    assert any(i.id == "med_sqlite_test_1" for i in items)


def test_sqlite_workspace_service_persistence():
    service = WorkspaceService()
    ws = service.create_workspace("Persistent Workspace", "Description of persistent workspace", "star")
    assert ws.id is not None

    fetched = service.get_workspace(ws.id)
    assert fetched is not None
    assert fetched.name == "Persistent Workspace"
    assert fetched.description == "Description of persistent workspace"
