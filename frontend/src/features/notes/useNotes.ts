import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface NoteFolderDTO {
  id: string;
  workspace_id: string;
  name: string;
  note_count: number;
  created_at: string | null;
  updated_at: string | null;
}

export interface NoteSectionDTO {
  id: string;
  note_id: string;
  workspace_id: string;
  heading: string;
  body: string;
  key_takeaways: string[];
  media_id: string | null;
  start_time: number | null;
  end_time: number | null;
  source_chunk_ids: string[];
  order_index: number;
  created_at: string | null;
}

export interface NoteDTO {
  id: string;
  workspace_id: string;
  title: string;
  folder_id: string | null;
  content: string | null;
  summary: string | null;
  media_id: string | null;
  version: number;
  status: string;
  action_items: string[];
  sections: NoteSectionDTO[];
  generation_method?: 'llm' | 'heuristic' | 'manual';
  fallback_reason?: string | null;
  provider_id?: string | null;
  model_id?: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ArtifactJobStatusDTO {
  artifact_type: string;
  target_key: string;
  status: string;
  stage: string | null;
  progress: number;
  message: string | null;
  error_message: string | null;
  updated_at: string | null;
}

export interface NoteChanges {
  title?: string;
  content?: string | null;
  folder_id?: string | null;
}

export interface NoteTranscriptSegmentDTO {
  start_time: number;
  end_time: number;
  text: string;
}

export interface NoteTranscriptDTO {
  media_id: string;
  full_text: string;
  segments: NoteTranscriptSegmentDTO[];
}

export async function transcribeNoteAudio(
  noteId: string,
  blob: Blob,
  workspaceId = 'default'
): Promise<NoteTranscriptDTO> {
  const formData = new FormData();
  const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
  const file = new File([blob], `note_audio_${Date.now()}.${ext}`, { type: blob.type });
  formData.append('file', file);
  formData.append('workspace_id', workspaceId);

  return apiClient<NoteTranscriptDTO>(
    `/api/v1/learning/notes/item/${encodeURIComponent(noteId)}/transcribe`,
    {
      method: 'POST',
      body: formData,
    }
  );
}

export async function getNoteTranscript(noteId: string): Promise<NoteTranscriptDTO> {
  return apiClient<NoteTranscriptDTO>(
    `/api/v1/learning/notes/item/${encodeURIComponent(noteId)}/transcript`
  );
}

export function useNotes() {
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const activeMediaId = useAppStore((state) => state.activeMediaId);
  const setActiveView = useAppStore((state) => state.setActiveView);

  const [folders, setFolders] = useState<NoteFolderDTO[]>([]);
  const [notes, setNotes] = useState<NoteDTO[]>([]);
  const [activeNote, setActiveNote] = useState<NoteDTO | null>(null);
  const [artifact, setArtifact] = useState<ArtifactJobStatusDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const workspaceRef = useRef(activeWorkspaceId);
  workspaceRef.current = activeWorkspaceId;

  const notify = useCallback((message: string) => {
    setToastMessage(message);
    window.setTimeout(() => setToastMessage(null), 3000);
  }, []);

  const refreshFolders = useCallback(async (): Promise<NoteFolderDTO[]> => {
    const workspaceId = workspaceRef.current;
    if (!workspaceId) return [];
    const data = await apiClient<NoteFolderDTO[]>(
      `/api/v1/learning/folders/${encodeURIComponent(workspaceId)}`
    );
    const list = Array.isArray(data) ? data : [];
    setFolders(list);
    return list;
  }, []);

  const refreshNotes = useCallback(async (): Promise<NoteDTO[]> => {
    const workspaceId = workspaceRef.current;
    if (!workspaceId) return [];
    const data = await apiClient<NoteDTO[]>(
      `/api/v1/learning/notes/${encodeURIComponent(workspaceId)}`
    );
    const list = Array.isArray(data) ? data : [];
    setNotes(list);
    return list;
  }, []);

  const selectNote = useCallback(async (noteId: string) => {
    setLoading(true);
    setError(null);
    try {
      const note = await apiClient<NoteDTO>(
        `/api/v1/learning/notes/item/${encodeURIComponent(noteId)}`
      );
      setActiveNote(note);
      return note;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to load selected note.');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  const createNote = useCallback(
    async (folderId?: string | null, title = 'Untitled Note', content?: string) => {
      const workspaceId = workspaceRef.current;
      if (!workspaceId) return null;
      try {
        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/${encodeURIComponent(workspaceId)}/item`,
          {
            method: 'POST',
            body: JSON.stringify({
              title: title.trim() || 'Untitled Note',
              folder_id: folderId || null,
              content: content || null,
            }),
          }
        );
        setActiveNote(note);
        setNotes((current) => [note, ...current]);
        await refreshFolders();
        notify('New note created');
        return note;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to create note.');
        return null;
      }
    },
    [notify, refreshFolders]
  );

  const updateNote = useCallback(
    async (changes: NoteChanges, noteId?: string) => {
      const targetNoteId = noteId || activeNote?.id;
      if (!targetNoteId) return null;
      setSaving(true);
      setError(null);
      try {
        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/item/${encodeURIComponent(targetNoteId)}`,
          {
            method: 'PATCH',
            body: JSON.stringify(changes),
          }
        );
        setActiveNote(note);
        setNotes((current) => current.map((item) => (item.id === note.id ? note : item)));
        await refreshFolders();
        return note;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to save note changes.');
        return null;
      } finally {
        setSaving(false);
      }
    },
    [activeNote?.id, refreshFolders]
  );

  const deleteNote = useCallback(
    async (noteId?: string) => {
      const targetNoteId = noteId || activeNote?.id;
      if (!targetNoteId) return false;
      try {
        await apiClient(`/api/v1/learning/notes/item/${encodeURIComponent(targetNoteId)}`, {
          method: 'DELETE',
        });
        const remaining = await refreshNotes();
        await refreshFolders();
        if (activeNote?.id === targetNoteId) {
          const next = remaining[0] || null;
          setActiveNote(next);
          if (next) {
            await selectNote(next.id);
          }
        }
        notify('Note deleted');
        return true;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to delete note.');
        return false;
      }
    },
    [activeNote?.id, notify, refreshFolders, refreshNotes, selectNote]
  );

  const createFolder = useCallback(
    async (name: string) => {
      const workspaceId = workspaceRef.current;
      if (!workspaceId || !name.trim()) return null;
      try {
        const folder = await apiClient<NoteFolderDTO>(
          `/api/v1/learning/folders/${encodeURIComponent(workspaceId)}`,
          { method: 'POST', body: JSON.stringify({ name: name.trim() }) }
        );
        setFolders((current) => [...current, folder]);
        notify(`Folder "${folder.name}" created`);
        return folder;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to create folder.');
        return null;
      }
    },
    [notify]
  );

  const renameFolder = useCallback(
    async (folderId: string, name: string) => {
      if (!name.trim()) return false;
      try {
        const folder = await apiClient<NoteFolderDTO>(
          `/api/v1/learning/folders/${encodeURIComponent(folderId)}`,
          { method: 'PATCH', body: JSON.stringify({ name: name.trim() }) }
        );
        setFolders((current) => current.map((item) => (item.id === folder.id ? folder : item)));
        notify(`Folder renamed to "${folder.name}"`);
        return true;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to rename folder.');
        return false;
      }
    },
    [notify]
  );

  const deleteFolder = useCallback(
    async (folderId: string) => {
      try {
        await apiClient(`/api/v1/learning/folders/${encodeURIComponent(folderId)}`, {
          method: 'DELETE',
        });
        await refreshFolders();
        const remaining = await refreshNotes();
        if (activeNote?.folder_id === folderId) {
          const next = remaining[0] || null;
          setActiveNote(next);
          if (next) {
            await selectNote(next.id);
          }
        }
        notify('Folder and its notes deleted');
        return true;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to delete folder.');
        return false;
      }
    },
    [activeNote?.folder_id, notify, refreshFolders, refreshNotes, selectNote]
  );

  const attachAudio = useCallback(
    async (mediaId: string, noteId?: string) => {
      const targetNoteId = noteId || activeNote?.id;
      if (!targetNoteId) return null;
      try {
        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/item/${encodeURIComponent(targetNoteId)}/attach-audio`,
          { method: 'POST', body: JSON.stringify({ media_id: mediaId }) }
        );
        setActiveNote(note);
        setNotes((current) => current.map((item) => (item.id === note.id ? note : item)));
        notify('Recording attached');
        return note;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to attach recording.');
        return null;
      }
    },
    [activeNote?.id, notify]
  );

  const transcribeAudioForNote = useCallback(
    async (noteId: string, blob: Blob): Promise<NoteTranscriptDTO | null> => {
      const workspaceId = workspaceRef.current || 'default';
      try {
        const result = await transcribeNoteAudio(noteId, blob, workspaceId);
        if (result?.media_id) {
          setActiveNote((current) =>
            current && current.id === noteId ? { ...current, media_id: result.media_id } : current
          );
          setNotes((current) =>
            current.map((item) =>
              item.id === noteId ? { ...item, media_id: result.media_id } : item
            )
          );
        }
        notify('Audio transcribed');
        return result;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to transcribe audio.');
        return null;
      }
    },
    [notify]
  );

  const generateNotes = useCallback(
    async (customInstruction?: string, noteId?: string) => {
      const targetNoteId = noteId || activeNote?.id;
      if (!targetNoteId) return null;
      setGenerating(true);
      setError(null);
      try {
        const query = customInstruction
          ? `?custom_instruction=${encodeURIComponent(customInstruction)}`
          : '';
        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/item/${encodeURIComponent(targetNoteId)}/generate${query}`,
          { method: 'POST' }
        );
        setActiveNote(note);
        setNotes((current) => current.map((item) => (item.id === note.id ? note : item)));
        await refreshFolders();
        if (note.generation_method === 'heuristic') {
          const reason = note.fallback_reason ? ` (${note.fallback_reason})` : '';
          notify(`Notes generated via fallback engine${reason}`);
        } else {
          notify('AI notes generated and saved');
        }
        return note;
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : 'Failed to generate study notes.');
        return null;
      } finally {
        setGenerating(false);
      }
    },
    [activeNote?.id, notify, refreshFolders]
  );

  const refreshArtifactStatus = useCallback(async () => {
    const workspaceId = workspaceRef.current;
    const mediaId = activeNote?.media_id || activeMediaId;
    if (!workspaceId || !mediaId) {
      setArtifact(null);
      return null;
    }
    try {
      const status = await apiClient<ArtifactJobStatusDTO | null>(
        `/api/v1/learning/notes/${encodeURIComponent(workspaceId)}/status?media_id=${encodeURIComponent(mediaId)}`
      );
      setArtifact(status);
      return status;
    } catch {
      return null;
    }
  }, [activeMediaId, activeNote?.media_id]);

  useEffect(() => {
    let cancelled = false;
    async function loadWorkspaceNotes() {
      if (!activeWorkspaceId) {
        setFolders([]);
        setNotes([]);
        setActiveNote(null);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const [, existingNotes] = await Promise.all([refreshFolders(), refreshNotes()]);
        if (!cancelled && existingNotes.length > 0 && !activeNote) {
          if (existingNotes[0]) await selectNote(existingNotes[0].id);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : 'Failed to load workspace notes.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    loadWorkspaceNotes();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceId, refreshFolders, refreshNotes, selectNote]);

  useEffect(() => {
    refreshArtifactStatus();
    const timer = window.setInterval(refreshArtifactStatus, 5000);
    return () => window.clearInterval(timer);
  }, [refreshArtifactStatus]);

  return {
    folders,
    notes,
    activeNote,
    artifact,
    loading,
    generating,
    saving,
    error,
    toastMessage,
    activeMediaId,
    createNote,
    selectNote,
    updateNote,
    deleteNote,
    createFolder,
    renameFolder,
    deleteFolder,
    attachAudio,
    transcribeAudioForNote,
    generateNotes,
    refreshNotes,
    refreshFolders,
    refreshArtifactStatus,
    setActiveView,
  };
}
