import uuid
from fastapi.testclient import TestClient
from app.main import app
from app.infrastructure.db.session import engine, init_db

try:
    from sqlmodel import Session
except ImportError:
    from sqlalchemy.orm import Session

from app.infrastructure.db.models import MediaItemTable, TranscriptChunkTable
from app.domain.ai.capabilities import SpeechToTextResponse, TranscriptSegmentDTO
from app.presentation.api.v1 import learning as learning_api

client = TestClient(app)


def test_user_can_create_and_list_note_folders():
    init_db()
    ws_id = f"ws_folders_{uuid.uuid4().hex[:8]}"

    create_res = client.post(
        f"/api/v1/learning/folders/{ws_id}",
        json={"name": "Research"},
    )
    assert create_res.status_code == 201
    folder = create_res.json()
    assert folder["name"] == "Research"
    assert folder["workspace_id"] == ws_id
    assert folder["note_count"] == 0

    list_res = client.get(f"/api/v1/learning/folders/{ws_id}")
    assert list_res.status_code == 200
    assert [item["id"] for item in list_res.json()] == [folder["id"]]


def test_user_can_create_and_retrieve_a_manual_note():
    init_db()
    ws_id = f"ws_note_item_{uuid.uuid4().hex[:8]}"
    folder = client.post(
        f"/api/v1/learning/folders/{ws_id}",
        json={"name": "Lectures"},
    ).json()

    create_res = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={
            "title": "Week 1",
            "folder_id": folder["id"],
            "content": "# Operating systems\n\nProcesses and threads.",
        },
    )
    assert create_res.status_code == 201
    created = create_res.json()
    assert created["title"] == "Week 1"
    assert created["folder_id"] == folder["id"]
    assert created["content"] == "# Operating systems\n\nProcesses and threads."
    assert created["generation_method"] == "manual"

    get_res = client.get(f"/api/v1/learning/notes/item/{created['id']}")
    assert get_res.status_code == 200
    assert get_res.json() == created


def test_user_can_edit_and_reorganize_a_note():
    init_db()
    ws_id = f"ws_note_edit_{uuid.uuid4().hex[:8]}"
    folder = client.post(
        f"/api/v1/learning/folders/{ws_id}",
        json={"name": "Inbox"},
    ).json()
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={"title": "Draft", "content": "Initial"},
    ).json()

    update_res = client.patch(
        f"/api/v1/learning/notes/item/{note['id']}",
        json={
            "title": "Final title",
            "content": "Saved markdown",
            "folder_id": folder["id"],
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["title"] == "Final title"
    assert updated["content"] == "Saved markdown"
    assert updated["folder_id"] == folder["id"]

    folder_notes = client.get(
        f"/api/v1/learning/notes/{ws_id}?folder_id={folder['id']}"
    ).json()
    assert [item["id"] for item in folder_notes] == [note["id"]]
    assert client.get(
        f"/api/v1/learning/notes/{ws_id}?unorganized=true"
    ).json() == []


def test_deleting_a_folder_cascades_to_notes_and_generated_sections():
    ws_id = f"ws_folder_delete_{uuid.uuid4().hex[:8]}"
    media_id = f"med_folder_delete_{uuid.uuid4().hex[:8]}"
    _seed_test_media_and_chunks(ws_id, media_id)
    folder = client.post(
        f"/api/v1/learning/folders/{ws_id}",
        json={"name": "Temporary"},
    ).json()
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}?media_id={media_id}"
    ).json()
    client.patch(
        f"/api/v1/learning/notes/item/{note['id']}",
        json={"folder_id": folder["id"]},
    )

    rename_res = client.patch(
        f"/api/v1/learning/folders/{folder['id']}",
        json={"name": "Archive"},
    )
    assert rename_res.status_code == 200
    assert rename_res.json()["name"] == "Archive"
    assert rename_res.json()["note_count"] == 1

    delete_res = client.delete(f"/api/v1/learning/folders/{folder['id']}")
    assert delete_res.status_code == 204
    assert client.get(f"/api/v1/learning/notes/item/{note['id']}").status_code == 404
    assert client.get(f"/api/v1/learning/notes/{note['id']}/sections").json() == []


def test_user_can_delete_a_note():
    init_db()
    ws_id = f"ws_note_delete_{uuid.uuid4().hex[:8]}"
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={"title": "Disposable"},
    ).json()

    delete_res = client.delete(f"/api/v1/learning/notes/item/{note['id']}")
    assert delete_res.status_code == 204
    assert client.get(f"/api/v1/learning/notes/item/{note['id']}").status_code == 404


def test_transcribed_audio_can_be_attached_to_a_note():
    ws_id = f"ws_note_audio_{uuid.uuid4().hex[:8]}"
    media_id = f"med_note_audio_{uuid.uuid4().hex[:8]}"
    _seed_test_media_and_chunks(ws_id, media_id)
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={"title": "Recorded lecture"},
    ).json()

    attach_res = client.post(
        f"/api/v1/learning/notes/item/{note['id']}/attach-audio",
        json={"media_id": media_id},
    )
    assert attach_res.status_code == 200
    assert attach_res.json()["media_id"] == media_id
    assert client.get(
        f"/api/v1/learning/notes/item/{note['id']}"
    ).json()["media_id"] == media_id


def test_note_audio_transcription_uses_injected_stt_capability(monkeypatch):
    ws_id = f"ws_note_stt_{uuid.uuid4().hex[:8]}"
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={"title": "Provider-independent recording"},
    ).json()

    class FakeSTTCapability:
        async def transcribe(self, request):
            return SpeechToTextResponse(
                text="Injected provider transcript",
                segments=[
                    TranscriptSegmentDTO(
                        start_time=0.0,
                        end_time=4.0,
                        text="Injected provider transcript",
                    )
                ],
                language_detected="en",
            )

    class FakeAIServiceBus:
        def get_stt_capability(self):
            return FakeSTTCapability()

    def concrete_adapter_must_not_be_constructed():
        raise AssertionError("note transcription constructed a concrete STT adapter")

    monkeypatch.setattr(
        "app.infrastructure.adapters.whisper_adapter.FasterWhisperSTTAdapter",
        concrete_adapter_must_not_be_constructed,
    )

    from app.main import ai_service_bus as production_ai_service_bus

    learning_api.set_ai_service_bus(FakeAIServiceBus())
    try:
        response = client.post(
            f"/api/v1/learning/notes/item/{note['id']}/transcribe",
            files={"file": ("recording.webm", b"fake audio", "audio/webm")},
            data={"workspace_id": ws_id},
        )
    finally:
        learning_api.set_ai_service_bus(production_ai_service_bus)

    assert response.status_code == 200
    assert response.json()["full_text"] == "Injected provider transcript"
    assert response.json()["segments"] == [
        {"start_time": 0.0, "end_time": 4.0, "text": "Injected provider transcript"}
    ]


def test_ai_generation_is_persisted_on_the_active_note():
    ws_id = f"ws_note_generate_{uuid.uuid4().hex[:8]}"
    media_id = f"med_note_generate_{uuid.uuid4().hex[:8]}"
    _seed_test_media_and_chunks(ws_id, media_id)
    note = client.post(
        f"/api/v1/learning/notes/{ws_id}/item",
        json={"title": "My lecture", "content": "Keep my manual notes"},
    ).json()
    client.post(
        f"/api/v1/learning/notes/item/{note['id']}/attach-audio",
        json={"media_id": media_id},
    )

    generate_res = client.post(
        f"/api/v1/learning/notes/item/{note['id']}/generate"
    )
    assert generate_res.status_code == 200
    generated = generate_res.json()
    assert generated["id"] == note["id"]
    assert generated["content"] == "Keep my manual notes"
    assert generated["summary"]
    assert generated["action_items"]
    assert generated["sections"]
    assert generated["generation_method"] in ("llm", "heuristic")

    persisted = client.get(
        f"/api/v1/learning/notes/item/{note['id']}"
    ).json()
    assert persisted == generated


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
