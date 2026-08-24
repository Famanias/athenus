from app.infrastructure.db.models import NoteSectionTable, NoteTable


def test_note_foreign_keys_cascade_deletes():
    folder_foreign_key = next(iter(NoteTable.__table__.c.folder_id.foreign_keys))
    section_foreign_key = next(iter(NoteSectionTable.__table__.c.note_id.foreign_keys))

    assert folder_foreign_key.ondelete == "CASCADE"
    assert section_foreign_key.ondelete == "CASCADE"
