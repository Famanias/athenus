import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import engine, init_db

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable

client = TestClient(app)


def _seed_test_media_and_chunks(ws_id: str, media_id: str):
    init_db()
    with Session(engine) as session:
        media = MediaItemTable(
            id=media_id,
            workspace_id=ws_id,
            title="Operating Systems Lecture",
            file_path="/mock/os.mp4",
            status="completed",
        )
        session.add(media)

        c1 = TranscriptChunkTable(
            id=f"{media_id}_chunk_0",
            media_id=media_id,
            workspace_id=ws_id,
            text="Processes are isolated execution contexts with their own virtual address spaces.",
            start_time=0.0,
            end_time=25.0,
            chunk_index=0,
            word_count=12,
        )
        c2 = TranscriptChunkTable(
            id=f"{media_id}_chunk_1",
            media_id=media_id,
            workspace_id=ws_id,
            text="Threads share the same address space but have independent stack pointers and registers.",
            start_time=25.0,
            end_time=55.0,
            chunk_index=1,
            word_count=13,
        )
        session.add(c1)
        session.add(c2)
        session.commit()


def test_note_generation_endpoints_e2e():
    ws_id = f"ws_api_{uuid.uuid4().hex[:8]}"
    media_id = f"med_api_{uuid.uuid4().hex[:8]}"
    _seed_test_media_and_chunks(ws_id, media_id)

    # 1. POST create note v1
    create_res = client.post(f"/api/v1/learning/notes/{ws_id}?media_id={media_id}")
    assert create_res.status_code == 200
    note_v1 = create_res.json()
    assert note_v1["version"] == 1
    assert note_v1["status"] == "ready"
    assert len(note_v1["sections"]) >= 1
    assert note_v1["sections"][0]["start_time"] == 0.0

    note_id = note_v1["id"]

    # 2. GET list notes
    list_res = client.get(f"/api/v1/learning/notes/{ws_id}?media_id={media_id}")
    assert list_res.status_code == 200
    notes_list = list_res.json()
    assert len(notes_list) == 1
    assert notes_list[0]["id"] == note_id

    # 3. GET status
    status_res = client.get(f"/api/v1/learning/notes/{ws_id}/status?media_id={media_id}")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "ready"
    assert status_data["progress"] == 100

    # 4. GET version 1
    v1_res = client.get(f"/api/v1/learning/notes/{ws_id}/version/1?media_id={media_id}")
    assert v1_res.status_code == 200
    assert v1_res.json()["version"] == 1

    # 5. POST force new version (v2)
    create_v2_res = client.post(f"/api/v1/learning/notes/{ws_id}?media_id={media_id}&force_new_version=true")
    assert create_v2_res.status_code == 200
    note_v2 = create_v2_res.json()
    assert note_v2["version"] == 2
    assert note_v2["id"] != note_id

    # 6. GET latest note (should be v2)
    latest_res = client.get(f"/api/v1/learning/notes/{ws_id}/latest?media_id={media_id}")
    assert latest_res.status_code == 200
    assert latest_res.json()["version"] == 2

    # 7. GET note sections
    sec_res = client.get(f"/api/v1/learning/notes/{note_id}/sections")
    assert sec_res.status_code == 200
    sections = sec_res.json()
    assert len(sections) >= 1
    assert "heading" in sections[0]
    assert "body" in sections[0]
    assert "start_time" in sections[0]

    # 8. GET non-existent version returns 404
    v99_res = client.get(f"/api/v1/learning/notes/{ws_id}/version/99?media_id={media_id}")
    assert v99_res.status_code == 404
