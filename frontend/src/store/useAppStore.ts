import { create } from 'zustand';
import { createChatSlice, type ChatSlice } from './chatSlice';

// ---------------------------------------------------------------------------
// UI Slice — view routing, workspace selection, and global overlay state.
// Future slices (video, ingestion, …) compose alongside this one.
// ---------------------------------------------------------------------------

interface UISlice {
  activeView: string;
  activeWorkspaceId: string;
  activeMediaId: string | null;
  currentTime: string;
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
  setCmdPaletteOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
  setProviderSettings: (llm: string, stt: string, gpu: boolean) => void;
}

export type AppState = UISlice & ChatSlice;

export const useAppStore = create<AppState>()((...args) => ({
  // --- UI slice ---
  activeView: 'view-chat',
  activeWorkspaceId: 'default',
  activeMediaId: null,
  currentTime: '00:00',
  isCmdPaletteOpen: false,
  searchQuery: '',

  llmProvider: 'ollama',
  sttProvider: 'faster-whisper',
  gpuAcceleration: true,

  setActiveView: (viewId) => args[0]({ activeView: viewId }),
  setActiveWorkspaceId: (id) => args[0]({ activeWorkspaceId: id }),
  setActiveMediaId: (id) => args[0]({ activeMediaId: id }),
  setCurrentTime: (time) => args[0]({ currentTime: time }),
  setCmdPaletteOpen: (isOpen) => args[0]({ isCmdPaletteOpen: isOpen }),
  setSearchQuery: (query) => args[0]({ searchQuery: query }),
  setProviderSettings: (llm, stt, gpu) =>
    args[0]({ llmProvider: llm, sttProvider: stt, gpuAcceleration: gpu }),

  // --- Chat slice ---
  ...createChatSlice(...args),
}));
