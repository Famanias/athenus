import { create } from 'zustand';

export interface AppState {
  activeView: string;
  activeWorkspaceId: string;
  activeMediaId: string | null;
  currentTime: string;
  isCmdPaletteOpen: boolean;
  searchQuery: string;

  // Actions
  setActiveView: (viewId: string) => void;
  setActiveWorkspaceId: (id: string) => void;
  setActiveMediaId: (id: string | null) => void;
  setCurrentTime: (time: string) => void;
  setCmdPaletteOpen: (isOpen: boolean) => void;
  setSearchQuery: (query: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  activeView: 'view-chat',
  activeWorkspaceId: 'ws_ml_default',
  activeMediaId: 'med_sample_01',
  currentTime: '12:40',
  isCmdPaletteOpen: false,
  searchQuery: '',

  setActiveView: (viewId) => set({ activeView: viewId }),
  setActiveWorkspaceId: (id) => set({ activeWorkspaceId: id }),
  setActiveMediaId: (id) => set({ activeMediaId: id }),
  setCurrentTime: (time) => set({ currentTime: time }),
  setCmdPaletteOpen: (isOpen) => set({ isCmdPaletteOpen: isOpen }),
  setSearchQuery: (query) => set({ searchQuery: query }),
}));
