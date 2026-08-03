import type { StateCreator } from 'zustand';
import type { ChatMessage, Citation, AgentLog } from '@/features/chat/types';

export interface ChatState {
  activeSessionId: string | null;
  isDraftSession: boolean;
  messages: ChatMessage[];
  evidence: Citation[];
  agentLogs: AgentLog[];
  input: string;
  isGenerating: boolean;
  isConversationLoading: boolean;
  backendUnavailable: boolean;
}

export interface ChatSlice {
  // Nested chat state — keeps root store clean and makes selectors precise.
  chat: ChatState;

  // Domain actions (describe what happened, not which variable changed).
  setActiveSessionId: (sessionId: string | null, isDraft?: boolean) => void;
  addMessage: (message: ChatMessage) => void;
  replaceMessages: (messages: ChatMessage[]) => void;
  clearConversation: () => void;
  addEvidence: (evidence: Citation[]) => void;
  addAgentLog: (log: AgentLog) => void;
  updateInput: (value: string) => void;
  setGenerating: (generating: boolean) => void;
  setConversationLoading: (loading: boolean) => void;
  setBackendUnavailable: (unavailable: boolean) => void;
}

export const createChatSlice: StateCreator<ChatSlice, [], [], ChatSlice> = (set) => ({
  chat: {
    activeSessionId: null,
    isDraftSession: true,
    messages: [],
    evidence: [],
    agentLogs: [],
    input: '',
    isGenerating: false,
    isConversationLoading: false,
    backendUnavailable: false,
  },

  setActiveSessionId: (sessionId, isDraft = false) =>
    set((state) => ({
      chat: {
        ...state.chat,
        activeSessionId: sessionId,
        isDraftSession: isDraft,
      },
    })),

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
        messages: [],
        evidence: [],
        agentLogs: [],
        input: '',
        isGenerating: false,
        isConversationLoading: false,
        backendUnavailable: false,
      },
    })),

  addEvidence: (evidence) =>
    set((state) => ({
      chat: { ...state.chat, evidence },
    })),

  addAgentLog: (log) =>
    set((state) => ({
      chat: { ...state.chat, agentLogs: [...state.chat.agentLogs, log] },
    })),

  updateInput: (value) =>
    set((state) => ({
      chat: { ...state.chat, input: value },
    })),

  setGenerating: (generating) =>
    set((state) => ({
      chat: { ...state.chat, isGenerating: generating },
    })),

  setConversationLoading: (loading) =>
    set((state) => ({
      chat: { ...state.chat, isConversationLoading: loading },
    })),

  setBackendUnavailable: (unavailable) =>
    set((state) => ({
      chat: { ...state.chat, backendUnavailable: unavailable },
    })),
});
