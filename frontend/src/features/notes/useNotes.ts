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
    setError(null);
    try {
      const note = await apiClient<NoteDTO>(
        `/api/v1/learning/notes/item/${encodeURIComponent(noteId)}`
      );
      setActiveNote(note);
      return note;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to load note.');
      return null;
    }
  }, []);

  const createNote = useCallback(async (folderId: string | null = null) => {
    const workspaceId = workspaceRef.current;
    if (!workspaceId) return null;
    setError(null);
    try {
      const note = await apiClient<NoteDTO>(
        `/api/v1/learning/notes/${encodeURIComponent(workspaceId)}/item`,
        {
          method: 'POST',
          body: JSON.stringify({ title: 'Untitled Note', folder_id: folderId, content: '' }),
        }
      );
      setActiveNote(note);
      setNotes((current) => [note, ...current]);
      await refreshFolders();
      notify('Note created');
      return note;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to create note.');
      return null;
    }
  }, [notify, refreshFolders]);

  const updateNote = useCallback(async (noteId: string, changes: NoteChanges) => {
    setSaving(true);
    setError(null);
    try {
      const note = await apiClient<NoteDTO>(
        `/api/v1/learning/notes/item/${encodeURIComponent(noteId)}`,
        { method: 'PATCH', body: JSON.stringify(changes) }
      );
      setNotes((current) => current.map((item) => item.id === note.id ? note : item));
      setActiveNote((current) => current?.id === note.id ? note : current);
      if ('folder_id' in changes) await refreshFolders();
      return note;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to save note.');
      return null;
    } finally {
      setSaving(false);
    }
  }, [refreshFolders]);

  const deleteNote = useCallback(async (noteId: string) => {
    try {
      await apiClient<void>(`/api/v1/learning/notes/item/${encodeURIComponent(noteId)}`, {
        method: 'DELETE',
      });
      const remaining = await refreshNotes();
      if (activeNote?.id === noteId) {
        if (remaining[0]) await selectNote(remaining[0].id);
        else setActiveNote(null);
      }
      await refreshFolders();
      notify('Note deleted');
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to delete note.');
      return false;
    }
  }, [activeNote?.id, notify, refreshFolders, refreshNotes, selectNote]);

  const createFolder = useCallback(async (name: string) => {
    const workspaceId = workspaceRef.current;
    if (!workspaceId) return null;
    try {
      const folder = await apiClient<NoteFolderDTO>(
        `/api/v1/learning/folders/${encodeURIComponent(workspaceId)}`,
        { method: 'POST', body: JSON.stringify({ name }) }
      );
      setFolders((current) => [...current, folder]);
      notify('Folder created');
      return folder;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to create folder.');
      return null;
    }
  }, [notify]);

  const renameFolder = useCallback(async (folderId: string, name: string) => {
    try {
      const folder = await apiClient<NoteFolderDTO>(
        `/api/v1/learning/folders/${encodeURIComponent(folderId)}`,
        { method: 'PATCH', body: JSON.stringify({ name }) }
      );
      setFolders((current) => current.map((item) => item.id === folder.id ? folder : item));
      notify('Folder renamed');
      return folder;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to rename folder.');
      return null;
    }
  }, [notify]);

  const deleteFolder = useCallback(async (folderId: string) => {
    try {
      await apiClient<void>(`/api/v1/learning/folders/${encodeURIComponent(folderId)}`, {
        method: 'DELETE',
      });
      setFolders((current) => current.filter((folder) => folder.id !== folderId));
      const remaining = await refreshNotes();
      if (activeNote?.folder_id === folderId) {
        if (remaining[0]) await selectNote(remaining[0].id);
        else setActiveNote(null);
      }
      notify('Folder and its notes deleted');
      return true;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to delete folder.');
      return false;
    }
  }, [activeNote?.folder_id, notify, refreshNotes, selectNote]);

  const attachAudio = useCallback(async (mediaId: string, noteId?: string) => {
    const targetNoteId = noteId || activeNote?.id;
    if (!targetNoteId) return null;
    try {
      const note = await apiClient<NoteDTO>(
        `/api/v1/learning/notes/item/${encodeURIComponent(targetNoteId)}/attach-audio`,
        { method: 'POST', body: JSON.stringify({ media_id: mediaId }) }
      );
      setActiveNote(note);
      setNotes((current) => current.map((item) => item.id === note.id ? note : item));
      notify('Recording attached');
      return note;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Failed to attach recording.');
      return null;
    }
  }, [activeNote?.id, notify]);

  const generateNotes = useCallback(async (customInstruction?: string, noteId?: string) => {
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
      setNotes((current) => current.map((item) => item.id === note.id ? note : item));
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
  }, [activeNote?.id, notify, refreshFolders]);

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
    async function initialize() {
      if (!workspaceRef.current) return;
      setLoading(true);
      setError(null);
      try {
        const [, existingNotes] = await Promise.all([refreshFolders(), refreshNotes()]);
        if (!cancelled) {
          if (existingNotes[0]) await selectNote(existingNotes[0].id);
          else setActiveNote(null);
        }
      } catch (cause) {
        if (!cancelled) {
          setError(cause instanceof Error ? cause.message : 'Failed to initialize notes.');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    initialize();
    return () => { cancelled = true; };
  }, [activeWorkspaceId, refreshFolders, refreshNotes, selectNote]);

  useEffect(() => {
    refreshArtifactStatus();
    const timer = window.setInterval(refreshArtifactStatus, 5000);
    return () => window.clearInterval(timer);
  }, [refreshArtifactStatus]);

  const jumpToSource = useCallback((mediaId: string | null, seconds: number | null) => {
    const targetMedia = mediaId || activeNote?.media_id || activeMediaId;
    if (!targetMedia || seconds == null) return;
    const { activeSourceType, activeDocumentId } = useAppStore.getState();
    if (activeSourceType === 'pdf' || targetMedia === activeDocumentId) {
      useAppStore.setState({
        activeDocumentId: targetMedia,
        targetPage: Math.max(1, Math.floor(seconds)),
        activeView: 'view-video',
      });
    } else {
      useAppStore.setState({
        activeMediaId: targetMedia,
        targetSeekSeconds: seconds,
        activeView: 'view-video',
      });
    }
  }, [activeMediaId, activeNote?.media_id]);

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
    generateNotes,
    refreshNotes,
    refreshFolders,
    refreshArtifactStatus,
    jumpToSource,
    setActiveView,
  };
}
