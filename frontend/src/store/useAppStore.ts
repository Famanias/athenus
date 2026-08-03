import { create } from 'zustand';
import { createChatSlice, type ChatSlice, WELCOME_MESSAGE } from './chatSlice';
import type { WorkspaceContext } from '@/types/workspaceContext';
import type { BackendWorkspaceDTO } from '@/services/libraryService';
import type { ChatSessionDTO } from '@/services/chatService';

// ---------------------------------------------------------------------------
// UI Slice — view routing, workspace context, playback target & state recovery.
// ---------------------------------------------------------------------------

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
  isCmdPaletteOpen: boolean;
  isWorkspaceModalOpen: boolean;
  searchQuery: string;

  // Settings
  llmProvider: string;
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
  setCmdPaletteOpen: (isOpen: boolean) => void;
  setWorkspaceModalOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
  setProviderSettings: (llm: string, stt: string, gpu: boolean) => void;

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
  useAppStore.setState({ activeMediaId: mediaId, playbackSpeed });

  // Hydrate provider settings from backend SQLite store on boot
  getProviderSettings()
    .then((data) => {
      if (data) {
        useAppStore.setState({
          llmProvider: data.default_llm,
          sttProvider: data.default_stt,
          gpuAcceleration: data.gpu_acceleration,
        });
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
    isCmdPaletteOpen: false,
    isWorkspaceModalOpen: false,
    searchQuery: '',

    llmProvider: 'ollama',
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

    setCurrentTime: (time) => set({ currentTime: time }),
    setTargetSeekSeconds: (seconds) => set({ targetSeekSeconds: seconds }),
    setPlaybackSpeed: (speed) => {
      if (typeof window !== 'undefined') {
        localStorage.setItem('athenus_playback_speed', speed.toString());
      }
      set({ playbackSpeed: speed });
    },
    setCmdPaletteOpen: (isOpen) => set({ isCmdPaletteOpen: isOpen }),
    setWorkspaceModalOpen: (isOpen) => set({ isWorkspaceModalOpen: isOpen }),
    setSearchQuery: (query) => set({ searchQuery: query }),
    setProviderSettings: (llm, stt, gpu) =>
      set({ llmProvider: llm, sttProvider: stt, gpuAcceleration: gpu }),

    // --- 9-Step Workspace Switching Lifecycle ---
    switchWorkspace: (targetWorkspaceId: string) => {
      const state = get();
      // 1. Cancel in-flight generation flag
      state.setGenerating(false);
      // 2. Clear transient input state
      state.updateInput('');
      // 3. Update global context
      set({
        activeWorkspaceId: targetWorkspaceId,
        context: {
          workspaceId: targetWorkspaceId,
          sessionId: null,
          mediaId: null,
        },
      });
      // 4. Mark as lazy draft session until history loads
      state.setActiveSessionId(null, true);
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
      state.replaceMessages([WELCOME_MESSAGE]);
    },

    // --- Chat slice ---
    ...createChatSlice(...args),
  };
});
