import { create } from 'zustand';

export interface AppState {
  activeView: string;
  activeWorkspaceId: string;
  activeMediaId: string | null;
  currentTime: string;
  isCmdPaletteOpen: boolean;
  searchQuery: string;

  // Settings State
  llmProvider: string;
  sttProvider: string;
  gpuAcceleration: boolean;

  // Actions
  setActiveView: (viewId: string) => void;
  setActiveWorkspaceId: (id: string) => void;
  setActiveMediaId: (id: string | null) => void;
  setCurrentTime: (time: string) => void;
  setCmdPaletteOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
  setProviderSettings: (llm: string, stt: string, gpu: boolean) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeView: 'view-chat',
  activeWorkspaceId: 'default',
  activeMediaId: 'med_sample_01',
  currentTime: '12:40',
  isCmdPaletteOpen: false,
  searchQuery: '',

  llmProvider: 'ollama',
  sttProvider: 'faster-whisper',
  gpuAcceleration: true,

  setActiveView: (viewId) => set({ activeView: viewId }),
  setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),
  setActiveMediaId: (id) => set({ activeMediaId: id }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setCmdPaletteOpen: (isOpen) => set({ isCmdPaletteOpen: isOpen }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setProviderSettings: (llm, stt, gpu) =>
    set({ llmProvider: llm, sttProvider: stt, gpuAcceleration: gpu }),
}));
