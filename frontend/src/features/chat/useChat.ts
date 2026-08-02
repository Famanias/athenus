import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { sendChatQuery, mapBackendCitations } from '@/services/chatService';

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

const INITIAL_MESSAGES: ChatMessage[] = [
  {
    id: 'msg_0',
    sender: 'assistant',
    content: 'Welcome to Athenus AI Learning Assistant! Upload your lecture videos or ask any question about your workspace content to get started.',
    timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
  },
];

const INITIAL_LOGS: AgentLog[] = [];

export function useChat() {
  const { activeWorkspaceId, activeMediaId } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [evidence, setEvidence] = useState<Citation[]>([]);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>(INITIAL_LOGS);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);
  const [isBackendUnavailable, setIsBackendUnavailable] = useState<boolean>(false);

  const sendMessage = async (queryText?: string) => {
    const query = queryText || inputQuery;
    if (!query.trim() || isGenerating) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    setMessages((prev) => [...prev, userMsg]);
    setInputQuery('');
    setIsGenerating(true);

    try {
      const data = await sendChatQuery(query, activeWorkspaceId || 'default', activeMediaId || undefined);
      setIsBackendUnavailable(false);

      const mappedCitations = mapBackendCitations(data.citations, activeMediaId || '', 'Lecture Segment');

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: mappedCitations,
      };

      setMessages((prev) => [...prev, assistantMsg]);
      if (mappedCitations.length > 0) {
        setEvidence(mappedCitations);
      }
    } catch (_err: any) {
      setIsBackendUnavailable(true);

      const errorMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: `Backend Service Unavailable: Unable to process "${query}". Please ensure the FastAPI backend is running at http://localhost:8000.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsGenerating(false);
    }
  };

  return {
    messages,
    evidence,
    agentLogs,
    inputQuery,
    setInputQuery,
    sendMessage,
    isGenerating,
    isBackendUnavailable,
  };
}
