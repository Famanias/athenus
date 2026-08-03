import type { StateCreator } from 'zustand';
import type { ChatMessage, Citation, AgentLog } from '@/features/chat/types';

// The welcome message that initialises every new session.
export const WELCOME_MESSAGE: ChatMessage = {
  id: 'msg_0',
  sender: 'assistant',
  content:
    'Welcome to Athenus AI Learning Assistant! Upload your lecture videos or ask any question about your workspace content to get started.',
  timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
};

export interface ChatState {
  activeSessionId: string | null;
  isDraftSession: boolean;
  messages: ChatMessage[];
  evidence: Citation[];
  agentLogs: AgentLog[];
  input: string;
  isGenerating: boolean;
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
  setBackendUnavailable: (unavailable: boolean) => void;
}

export const createChatSlice: StateCreator<ChatSlice, [], [], ChatSlice> = (set) => ({
  chat: {
    activeSessionId: null,
    isDraftSession: true,
    messages: [WELCOME_MESSAGE],
    evidence: [],
    agentLogs: [],
    input: '',
    isGenerating: false,
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
      chat: { ...state.chat, messages: messages.length > 0 ? messages : [WELCOME_MESSAGE] },
    })),

  clearConversation: () =>
    set((state) => ({
      chat: {
        ...state.chat,
        messages: [WELCOME_MESSAGE],
        evidence: [],
        agentLogs: [],
        input: '',
        isGenerating: false,
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

  setBackendUnavailable: (unavailable) =>
    set((state) => ({
      chat: { ...state.chat, backendUnavailable: unavailable },
    })),
});
