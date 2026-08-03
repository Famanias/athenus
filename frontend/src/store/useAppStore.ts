import { create } from 'zustand';
import { createChatSlice, type ChatSlice } from './chatSlice';

// ---------------------------------------------------------------------------
// UI Slice — view routing, workspace selection, playback target & state recovery.
// ---------------------------------------------------------------------------

interface UISlice {
  activeView: string;
  activeWorkspaceId: string;
  activeMediaId: string | null;
  currentTime: string;
  targetSeekSeconds: number | null;
  playbackSpeed: number;
  isCmdPaletteOpen: boolean;
  searchQuery: string;

  // Settings
  llmProvider: string;
  sttProvider: string;
  gpuAcceleration: boolean;

  setActiveView: (viewId: string) => void;
  setActiveWorkspaceId: (id: string) => void;
  setActiveMediaId: (id: string | null) => void;
  setCurrentTime: (time: string) => void;
  setTargetSeekSeconds: (seconds: number | null) => void;
  setPlaybackSpeed: (speed: number) => void;
  setCmdPaletteOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
  setProviderSettings: (llm: string, stt: string, gpu: boolean) => void;
}

export type AppState = UISlice & ChatSlice;

export function rehydrateStoredState() {
  if (typeof window === 'undefined') return;
  const mediaId = localStorage.getItem('athenus_active_media_id') || null;
  const savedSpeed = localStorage.getItem('athenus_playback_speed');
  const playbackSpeed = savedSpeed ? parseFloat(savedSpeed) : 1.0;
  useAppStore.setState({ activeMediaId: mediaId, playbackSpeed });
}

export const useAppStore = create<AppState>()((...args) => ({
  // --- UI slice ---
  activeView: 'view-chat',
  activeWorkspaceId: 'default',
  activeMediaId: null,
  currentTime: '00:00',
  targetSeekSeconds: null,
  playbackSpeed: 1.0,
  isCmdPaletteOpen: false,
  searchQuery: '',

  llmProvider: 'ollama',
  sttProvider: 'faster-whisper',
  gpuAcceleration: true,

  setActiveView: (viewId) => args[0]({ activeView: viewId }),
  setActiveWorkspaceId: (id) => args[0]({ activeWorkspaceId: id }),
  setActiveMediaId: (id) => {
    if (typeof window !== 'undefined') {
      if (id) localStorage.setItem('athenus_active_media_id', id);
      else localStorage.removeItem('athenus_active_media_id');
    }
    args[0]({ activeMediaId: id });
  },
  setCurrentTime: (time) => args[0]({ currentTime: time }),
  setTargetSeekSeconds: (seconds) => args[0]({ targetSeekSeconds: seconds }),
  setPlaybackSpeed: (speed) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('athenus_playback_speed', speed.toString());
    }
    args[0]({ playbackSpeed: speed });
  },
  setCmdPaletteOpen: (isOpen) => args[0]({ isCmdPaletteOpen: isOpen }),
  setSearchQuery: (query) => args[0]({ searchQuery: query }),
  setProviderSettings: (llm, stt, gpu) =>
    args[0]({ llmProvider: llm, sttProvider: stt, gpuAcceleration: gpu }),

  // --- Chat slice ---
  ...createChatSlice(...args),
}));
