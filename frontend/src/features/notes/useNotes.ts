import { useCallback, useEffect, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

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
  summary: string | null;
  media_id: string | null;
  version: number;
  status: string;
  action_items: string[];
  sections: NoteSectionDTO[];
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

export function useNotes() {
  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeMediaId = useAppStore((s) => s.activeMediaId);
  const setActiveView = useAppStore((s) => s.setActiveView);

  const [notes, setNotes] = useState<NoteDTO[]>([]);
  const [activeNote, setActiveNote] = useState<NoteDTO | null>(null);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [artifact, setArtifact] = useState<ArtifactJobStatusDTO | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  const wsRef = useRef(activeWorkspaceId);
  wsRef.current = activeWorkspaceId;

  const refreshArtifactStatus = useCallback(async () => {
    const ws = wsRef.current;
    if (!ws) return null;
    try {
      const mediaQuery = activeMediaId ? `?media_id=${encodeURIComponent(activeMediaId)}` : '';
      const status = await apiClient<ArtifactJobStatusDTO | null>(
        `/api/v1/learning/notes/${encodeURIComponent(ws)}/status${mediaQuery}`
      );
      setArtifact(status);
      return status;
    } catch {
      return null;
    }
  }, [activeMediaId]);

  const refreshNotes = useCallback(async (): Promise<NoteDTO[]> => {
    const ws = wsRef.current;
    if (!ws) return [];
    try {
      const mediaQuery = activeMediaId ? `?media_id=${encodeURIComponent(activeMediaId)}` : '';
      const data = await apiClient<NoteDTO[]>(
        `/api/v1/learning/notes/${encodeURIComponent(ws)}${mediaQuery}`
      );
      const list = Array.isArray(data) ? data : [];
      setNotes(list);
      return list;
    } catch {
      setNotes([]);
      return [];
    }
  }, [activeMediaId]);

  const selectVersion = useCallback(
    async (version: number) => {
      const ws = wsRef.current;
      if (!ws) return;
      setSelectedVersion(version);
      try {
        const mediaQuery = activeMediaId ? `?media_id=${encodeURIComponent(activeMediaId)}` : '';
        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/${encodeURIComponent(ws)}/version/${version}${mediaQuery}`
        );
        setActiveNote(note);
      } catch {
        setError(`Failed to load note version ${version}`);
      }
    },
    [activeMediaId]
  );

  const generateNotes = useCallback(
    async (forceNewVersion = false, customInstruction?: string) => {
      const ws = wsRef.current;
      if (!ws) return null;
      setGenerating(true);
      setError(null);
      setToastMessage(null);
      try {
        const params = new URLSearchParams();
        if (activeMediaId) params.append('media_id', activeMediaId);
        if (forceNewVersion) params.append('force_new_version', 'true');
        if (customInstruction) params.append('custom_instruction', customInstruction);
        const queryStr = params.toString() ? `?${params.toString()}` : '';

        const note = await apiClient<NoteDTO>(
          `/api/v1/learning/notes/${encodeURIComponent(ws)}${queryStr}`,
          { method: 'POST' }
        );
        await refreshNotes();
        await refreshArtifactStatus();
        if (note && note.version) {
          await selectVersion(note.version);
          setToastMessage(`✅ Notes generated successfully (Version ${note.version})`);
          setTimeout(() => setToastMessage(null), 4000);
        }
        return note;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to generate study notes.';
        setError(msg);
        return null;
      } finally {
        setGenerating(false);
      }
    },
    [activeMediaId, refreshNotes, refreshArtifactStatus, selectVersion]
  );

  // Initial load
  useEffect(() => {
    let cancelled = false;
    async function init() {
      if (!wsRef.current) return;
      setLoading(true);
      setError(null);
      refreshArtifactStatus();
      try {
        const existing = await refreshNotes();
        if (cancelled) return;
        if (existing && existing.length > 0) {
          const latest = existing[0];
          setActiveNote(latest);
          setSelectedVersion(latest.version);
        } else {
          setActiveNote(null);
          setSelectedVersion(null);
        }
      } catch {
        if (!cancelled) setError('Failed to initialize notes view.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [activeWorkspaceId, activeMediaId, refreshNotes, refreshArtifactStatus]);

  // Periodic polling for status while generating
  useEffect(() => {
    if (!activeWorkspaceId) return;
    const timer = setInterval(() => {
      refreshArtifactStatus();
    }, 5000);
    return () => clearInterval(timer);
  }, [activeWorkspaceId, refreshArtifactStatus]);

  const jumpToSource = useCallback(
    (mediaId: string | null, seconds: number | null) => {
      const targetMedia = mediaId || activeMediaId;
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
    },
    [activeMediaId]
  );


  return {
    notes,
    activeNote,
    selectedVersion,
    artifact,
    loading,
    generating,
    error,
    toastMessage,
    activeMediaId,
    generateNotes,
    selectVersion,
    refreshNotes,
    refreshArtifactStatus,
    jumpToSource,
    setActiveView,
  };
}
