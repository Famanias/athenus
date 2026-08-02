import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { UISlice, createUISlice } from './uiSlice';
import { ChatSlice, createChatSlice } from './chatSlice';

export type AppState = UISlice & ChatSlice;

export const useAppStore = create<AppState>()(
  devtools(
    (...args) => ({
      ...createUISlice(...args),
      ...createChatSlice(...args),
    })
  )
);