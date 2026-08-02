import { StateCreator } from 'zustand';
import { ChatMessage, Citation, AgentLog } from '@/features/chat/types';

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'msg_0',
    sender: 'assistant',
    content: 'Welcome to Athenus AI Learning Assistant! Upload your lecture videos or ask any question about your workspace content to get started.',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  },
];

export interface ChatSlice {
  chat: {
    messages: ChatMessage[];
    citations: Citation[];
    logs: AgentLog[];
    input: string;
    isGenerating: boolean;
    backendUnavailable: boolean;
  };
  addMessage: (message: ChatMessage) => void;
  replaceMessages: (messages: ChatMessage[]) => void;
  clearConversation: () => void;
  addCitation: (citation: Citation) => void;
  replaceCitations: (citations: Citation[]) => void;
  addLog: (log: AgentLog) => void;
  replaceLogs: (logs: AgentLog[]) => void;
  updateInput: (input: string) => void;
  setGenerating: (isGenerating: boolean) => void;
  setBackendUnavailable: (unavailable: boolean) => void;
}

export const createChatSlice: StateCreator<ChatSlice> = (set) => ({
  chat: {
    messages: INITIAL_MESSAGES,
    citations: [],
    logs: [],
    input: '',
    isGenerating: false,
    backendUnavailable: false,
  },

  addMessage: (message) =>
    set((state) => ({
      chat: { ...state.chat, messages: [...state.chat.messages, message] },
    })),

  replaceMessages: (messages) =>
    set((state) => ({
      chat: { ...state.chat, messages },
    })),

  clearConversation: () =>
    set((state) => ({
      chat: {
        ...state.chat,
        messages: INITIAL_MESSAGES,
        citations: [],
        logs: [],
      },
    })),

  addCitation: (citation) =>
    set((state) => ({
      chat: { ...state.chat, citations: [...state.chat.citations, citation] },
    })),

  replaceCitations: (citations) =>
    set((state) => ({
      chat: { ...state.chat, citations },
    })),

  addLog: (log) =>
    set((state) => ({
      chat: { ...state.chat, logs: [...state.chat.logs, log] },
    })),

  replaceLogs: (logs) =>
    set((state) => ({
      chat: { ...state.chat, logs },
    })),

  updateInput: (input) =>
    set((state) => ({
      chat: { ...state.chat, input },
    })),

  setGenerating: (isGenerating) =>
    set((state) => ({
      chat: { ...state.chat, isGenerating },
    })),

  setBackendUnavailable: (unavailable) =>
    set((state) => ({
      chat: { ...state.chat, backendUnavailable: unavailable },
    })),
});