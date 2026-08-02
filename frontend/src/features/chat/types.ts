// Shared types for the chat domain.
// Kept in a dedicated file so both the Zustand slice and useChat.ts
// import from one canonical source — no circular dependencies.

export interface Citation {
  mediaId: string;
  mediaTitle: string;
  startTime: string;
  endTime: string;
  score: number;
  textSnippet: string;
}

export interface ChatMessage {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: Citation[];
}

export interface AgentLog {
  timestamp: string;
  agent: string;
  message: string;
}
