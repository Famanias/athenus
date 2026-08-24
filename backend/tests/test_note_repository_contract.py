import ast
from pathlib import Path

from app.domain.learning.note_repository import InMemoryNoteRepository
from app.domain.learning.note_service import NoteService


def test_note_module_persists_through_repository_interface():
    repository = InMemoryNoteRepository()
    notes = NoteService(repository=repository)

    folder = notes.create_folder("workspace-1", "Lectures")
    note = notes.create_manual_note(
        "workspace-1",
        title="Week 1",
        folder_id=folder.id,
        content="Initial content",
    )

    updated = notes.update_note(
        note.id,
        {"title": "Week 1 revised", "content": "Updated content"},
    )

    assert updated is not None
    assert notes.get_note(note.id) == updated
    assert updated.title == "Week 1 revised"
    assert updated.content == "Updated content"
    assert notes.list_folders("workspace-1")[0].note_count == 1


def test_deleting_folder_cascades_through_repository_interface():
    repository = InMemoryNoteRepository()
    notes = NoteService(repository=repository)
    folder = notes.create_folder("workspace-1", "Temporary")
    note = notes.create_manual_note("workspace-1", folder_id=folder.id)

    assert notes.delete_folder(folder.id) is True
    assert notes.get_note(note.id) is None
    assert notes.get_note_sections(note.id) == []


def test_note_service_has_no_database_or_concrete_stt_imports():
    service_path = (
        Path(__file__).parents[1]
        / "app"
        / "domain"
        / "learning"
        / "note_service.py"
    )
    tree = ast.parse(service_path.read_text(encoding="utf-8"))
    imports = [
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    ]

    assert not any(module.startswith("app.infrastructure.db") for module in imports)
    assert not any("faster_whisper" in module for module in imports)
