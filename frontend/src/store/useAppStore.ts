import { create } from 'zustand';
import { createChatSlice, type ChatSlice } from './chatSlice';
import type { WorkspaceContext } from '@/types/workspaceContext';
import type { BackendWorkspaceDTO } from '@/services/libraryService';
import type { ChatSessionDTO } from '@/services/chatService';

// ---------------------------------------------------------------------------
// UI Slice — view routing, workspace context, playback target & state recovery.
// ---------------------------------------------------------------------------

export interface BackgroundJob {
  job_id: string;
  media_id: string;
  workspace_id: string;
  title?: string;
  job_type: 'ingestion' | 'graph_extraction' | 'flashcard_gen' | 'quiz_gen';
  stage: 'queued' | 'uploaded' | 'audio_extraction' | 'transcription' | 'chunking' | 'vector_indexing' | 'graph_extraction' | 'ready' | 'completed' | 'failed' | 'document_parsing' | 'ocr_processing';
  progress: number;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'queued';
  message: string;
  error?: string;
  startedAt: string;
  updatedAt: string;
  history?: Array<{ stage: string; progress: number; status: string; timestamp: string }>;
}

interface UISlice {
  activeView: string;
  context: WorkspaceContext;
  workspaces: BackendWorkspaceDTO[];
  sessions: ChatSessionDTO[];
  activeWorkspaceId: string;
  activeMediaId: string | null;
  currentTime: string;
  targetSeekSeconds: number | null;
  playbackSpeed: number;
  isWorkspaceModalOpen: boolean;
  searchQuery: string;

  // Active source context (generalized document/PDF ingestion)
  activeDocumentId: string | null;
  activeSourceType: 'video' | 'pdf';
  currentPage: number | null;
  targetPage: number | null;

  // Background Task Engine Jobs Registry
  jobs: Record<string, BackgroundJob>;
  activeJobId: string | null;
  inspectedJobId: string | null;

  // Settings
  llmProvider: string;
  activeModel: string;
  sttProvider: string;
  gpuAcceleration: boolean;

  setActiveView: (viewId: string) => void;
  setWorkspaces: (workspaces: BackendWorkspaceDTO[]) => void;
  setSessions: (sessions: ChatSessionDTO[]) => void;
  setWorkspaceContext: (partialContext: Partial<WorkspaceContext>) => void;
  setActiveWorkspaceId: (id: string) => void;
  setActiveMediaId: (id: string | null) => void;
  setCurrentTime: (time: string) => void;
  setTargetSeekSeconds: (seconds: number | null) => void;
  setPlaybackSpeed: (speed: number) => void;
  setWorkspaceModalOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
  setProviderSettings: (llm: string, stt: string, gpu: boolean, activeModel?: string) => void;

  // Active source context actions (generalized document/PDF ingestion)
  setActiveDocumentId: (id: string | null) => void;
  setActiveSourceType: (type: 'video' | 'pdf') => void;
  setCurrentPage: (page: number | null) => void;
  setTargetPage: (page: number | null) => void;

  // Background Job Reducers (Pure State Mutations)
  upsertJob: (job: BackgroundJob) => void;
  removeJob: (jobId: string) => void;
  setJobHistory: (jobId: string, history: Array<{ stage: string; progress: number; status: string; timestamp: string }>) => void;
  setActiveJobId: (jobId: string | null) => void;
  setInspectedJobId: (jobId: string | null) => void;

  // 9-Step Workspace Lifecycle Actions
  switchWorkspace: (workspaceId: string) => void;
  switchSession: (sessionId: string | null) => void;
  initLazyNewChat: () => void;
}

import { getProviderSettings } from '@/services/settingsService';

export type AppState = UISlice & ChatSlice;

export function rehydrateStoredState() {
  if (typeof window === 'undefined') return;
  const mediaId = localStorage.getItem('athenus_active_media_id') || null;
  const savedSpeed = localStorage.getItem('athenus_playback_speed');
  const playbackSpeed = savedSpeed ? parseFloat(savedSpeed) : 1.0;
  const cachedModel = localStorage.getItem('athenus_active_model') || localStorage.getItem('athenus_selected_ollama_model') || '';

  // Set transient render cache to avoid layout flicker
  useAppStore.setState({
    activeMediaId: mediaId,
    playbackSpeed,
    ...(cachedModel ? { activeModel: cachedModel } : {}),
  });

  // Hydrate provider settings from backend SQLite store (Authoritative Source of Truth)
  getProviderSettings()
    .then((data) => {
      if (data) {
        const backendModel = data.selected_model || data.selected_ollama_model || '';
        useAppStore.setState({
          llmProvider: data.default_llm,
          activeModel: backendModel,
          sttProvider: data.default_stt,
          gpuAcceleration: data.gpu_acceleration,
        });
        if (backendModel) {
          localStorage.setItem('athenus_active_model', backendModel);
        }
      }
    })
    .catch(() => {});
}

export const useAppStore = create<AppState>()((...args) => {
  const [set, get] = args;

  return {
    // --- UI slice ---
    activeView: 'view-chat',
    context: {
      workspaceId: 'default',
      sessionId: null,
      mediaId: null,
    },
    workspaces: [],
    sessions: [],
    activeWorkspaceId: 'default',
    activeMediaId: null,
    currentTime: '00:00',
    targetSeekSeconds: null,
    playbackSpeed: 1.0,
    isWorkspaceModalOpen: false,
    searchQuery: '',

    // Active source context state (generalized document/PDF ingestion)
    activeDocumentId: null,
    activeSourceType: 'video',
    currentPage: null,
    targetPage: null,

    // Background Job Registry State
    jobs: {},
    activeJobId: null,
    inspectedJobId: null,

    llmProvider: 'ollama',
    activeModel: '',
    sttProvider: 'faster-whisper',
    gpuAcceleration: true,

    setActiveView: (viewId) => set({ activeView: viewId }),
    setWorkspaces: (workspaces) => set({ workspaces }),
    setSessions: (sessions) => set({ sessions }),
    setWorkspaceContext: (partialContext) =>
      set((state) => ({
        context: { ...state.context, ...partialContext },
        activeWorkspaceId: partialContext.workspaceId || state.activeWorkspaceId,
      })),

    setActiveWorkspaceId: (id) =>
      set((state) => ({
        activeWorkspaceId: id,
        context: { ...state.context, workspaceId: id },
      })),

    setActiveMediaId: (id) => {
      if (typeof window !== 'undefined') {
        if (id) localStorage.setItem('athenus_active_media_id', id);
        else localStorage.removeItem('athenus_active_media_id');
      }
      set((state) => ({
        activeMediaId: id,
        context: { ...state.context, mediaId: id },
      }));
    },

    // Pure Reducers for Background Job State Mutations (No side-effects)
    upsertJob: (job) =>
      set((state) => ({
        jobs: { ...state.jobs, [job.job_id]: { ...(state.jobs[job.job_id] || {}), ...job } },
      })),

    removeJob: (jobId) =>
      set((state) => {
        const newJobs = { ...state.jobs };
        delete newJobs[jobId];
        return {
          jobs: newJobs,
          activeJobId: state.activeJobId === jobId ? null : state.activeJobId,
          inspectedJobId: state.inspectedJobId === jobId ? null : state.inspectedJobId,
        };
      }),

    setJobHistory: (jobId, history) =>
      set((state) => ({
        jobs: {
          ...state.jobs,
          ...(state.jobs[jobId] ? { [jobId]: { ...state.jobs[jobId], history } } : {}),
        },
      })),

    setActiveJobId: (jobId) => set({ activeJobId: jobId }),
    setInspectedJobId: (jobId) => set({ inspectedJobId: jobId }),

    setCurrentTime: (time) => set({ currentTime: time }),
    setTargetSeekSeconds: (seconds) => set({ targetSeekSeconds: seconds }),
    setPlaybackSpeed: (speed) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('athenus_playback_speed', speed.toString());
      }
      set({ playbackSpeed: speed });
    },
    setWorkspaceModalOpen: (isOpen) => set({ isWorkspaceModalOpen: isOpen }),
    setSearchQuery: (query) => set({ searchQuery: query }),
    setProviderSettings: (llm, stt, gpu, activeModel) => {
      const modelToSave = activeModel ?? '';
      if (typeof window !== 'undefined' && modelToSave) {
        localStorage.setItem('athenus_active_model', modelToSave);
      }
      set({
        llmProvider: llm,
        activeModel: modelToSave,
        sttProvider: stt,
        gpuAcceleration: gpu,
      });
    },

    // Active source context actions (generalized document/PDF ingestion)
    setActiveDocumentId: (id) =>
      set((state) => ({
        activeDocumentId: id,
        context: { ...state.context, documentId: id },
      })),

    setActiveSourceType: (type) =>
      set((state) => ({
        activeSourceType: type,
        context: { ...state.context, sourceType: type },
      })),

    setCurrentPage: (page) =>
      set((state) => ({
        currentPage: page,
        context: { ...state.context, currentPage: page },
      })),

    setTargetPage: (page) => set({ targetPage: page }),

    // --- 9-Step Workspace Switching Lifecycle ---
    switchWorkspace: (targetWorkspaceId: string) => {
      const state = get();
      // 1. Cancel in-flight generation flag
      state.setGenerating(false);
      // 2. Clear transient input state
      state.updateInput('');
      // 3. Clear transient media selection for workspace isolation
      if (typeof window !== 'undefined') {
        localStorage.removeItem('athenus_active_media_id');
      }
      // 4. Update global context
      set({
        activeWorkspaceId: targetWorkspaceId,
        activeMediaId: null,
        activeDocumentId: null,
        activeSourceType: 'video',
        currentPage: null,
        targetPage: null,
        context: {
          workspaceId: targetWorkspaceId,
          sessionId: null,
          mediaId: null,
          documentId: null,
          sourceType: 'video',
          currentPage: null,
        },
      });
      // 5. Mark as lazy draft session until history loads
      state.setActiveSessionId(null, true);
      state.setConversationLoading(false);
    },

    switchSession: (sessionId: string | null) => {
      const state = get();
      state.setGenerating(false);
      state.updateInput('');
      set((prev) => ({
        activeView: 'view-chat',
        context: { ...prev.context, sessionId },
      }));
      state.setActiveSessionId(sessionId, !sessionId);
      state.setConversationLoading(false);
    },

    initLazyNewChat: () => {
      const state = get();
      state.setGenerating(false);
      state.updateInput('');
      set((prev) => ({
        context: { ...prev.context, sessionId: null },
        activeView: 'view-chat',
      }));
      state.setActiveSessionId(null, true);
      state.setConversationLoading(false);
      state.replaceMessages([]);
    },

    // --- Chat slice ---
    ...createChatSlice(...args),
  };
});
