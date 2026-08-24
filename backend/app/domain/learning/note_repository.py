from copy import deepcopy
from typing import Dict, List, Optional, Protocol

from app.domain.learning.entities import Note, NoteFolder, NoteSection


TranscriptChunkRecord = Dict[str, object]


class NoteRepository(Protocol):
    """Persistence seam used by the note domain module."""

    def save_folder(self, folder: NoteFolder) -> NoteFolder: ...
    def get_folder(self, folder_id: str) -> Optional[NoteFolder]: ...
    def list_folders(self, workspace_id: str) -> List[NoteFolder]: ...
    def delete_folder(self, folder_id: str) -> bool: ...

    def save_note(self, note: Note) -> Note: ...
    def get_note(self, note_id: str) -> Optional[Note]: ...
    def list_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        unorganized: bool = False,
    ) -> List[Note]: ...
    def delete_note(self, note_id: str) -> bool: ...
    def replace_sections(self, note_id: str, sections: List[NoteSection]) -> int: ...

    def media_belongs_to_workspace(self, media_id: str, workspace_id: str) -> bool: ...
    def list_transcript_chunks(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
    ) -> List[TranscriptChunkRecord]: ...


class InMemoryNoteRepository:
    """Pure in-memory adapter for domain tests and offline composition."""

    def __init__(self) -> None:
        self._folders: Dict[str, NoteFolder] = {}
        self._notes: Dict[str, Note] = {}
        self._media_workspaces: Dict[str, str] = {}
        self._chunks: List[TranscriptChunkRecord] = []

    def save_folder(self, folder: NoteFolder) -> NoteFolder:
        self._folders[folder.id] = deepcopy(folder)
        return deepcopy(folder)

    def get_folder(self, folder_id: str) -> Optional[NoteFolder]:
        folder = self._folders.get(folder_id)
        return deepcopy(folder) if folder else None

    def list_folders(self, workspace_id: str) -> List[NoteFolder]:
        folders = [
            deepcopy(folder)
            for folder in self._folders.values()
            if folder.workspace_id == workspace_id
        ]
        folders.sort(key=lambda folder: folder.created_at)
        for folder in folders:
            folder.note_count = sum(
                1
                for note in self._notes.values()
                if note.workspace_id == workspace_id and note.folder_id == folder.id
            )
        return folders

    def delete_folder(self, folder_id: str) -> bool:
        if folder_id not in self._folders:
            return False
        note_ids = [
            note.id for note in self._notes.values() if note.folder_id == folder_id
        ]
        for note_id in note_ids:
            self._notes.pop(note_id, None)
        self._folders.pop(folder_id, None)
        return True

    def save_note(self, note: Note) -> Note:
        self._notes[note.id] = deepcopy(note)
        return deepcopy(note)

    def get_note(self, note_id: str) -> Optional[Note]:
        note = self._notes.get(note_id)
        return deepcopy(note) if note else None

    def list_notes(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
        folder_id: Optional[str] = None,
        unorganized: bool = False,
    ) -> List[Note]:
        notes = [note for note in self._notes.values() if note.workspace_id == workspace_id]
        if media_id is not None:
            notes = [note for note in notes if note.media_id == media_id]
        if folder_id is not None:
            notes = [note for note in notes if note.folder_id == folder_id]
        elif unorganized:
            notes = [note for note in notes if note.folder_id is None]
        notes.sort(key=lambda note: note.updated_at, reverse=True)
        return deepcopy(notes)

    def delete_note(self, note_id: str) -> bool:
        return self._notes.pop(note_id, None) is not None

    def replace_sections(self, note_id: str, sections: List[NoteSection]) -> int:
        note = self._notes.get(note_id)
        if note is None:
            return 0
        note.sections = deepcopy(sections)
        self._notes[note_id] = note
        return len(sections)

    def media_belongs_to_workspace(self, media_id: str, workspace_id: str) -> bool:
        return self._media_workspaces.get(media_id) == workspace_id

    def list_transcript_chunks(
        self,
        workspace_id: str,
        media_id: Optional[str] = None,
    ) -> List[TranscriptChunkRecord]:
        chunks = [
            chunk
            for chunk in self._chunks
            if chunk.get("workspace_id") == workspace_id
            and (media_id is None or chunk.get("media_id") == media_id)
        ]
        return deepcopy(chunks)

    def register_media(self, media_id: str, workspace_id: str) -> None:
        self._media_workspaces[media_id] = workspace_id

    def add_transcript_chunks(self, chunks: List[TranscriptChunkRecord]) -> None:
        self._chunks.extend(deepcopy(chunks))
