// useChat — coordinates async chat logic on top of the Zustand chat slice.
//
// State lives in the store (survives view unmount/remount).
// This hook owns only the async sendMessage workflow — no local useState.

import { useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { sendChatQuery, getChatHistory, mapBackendCitations } from '@/services/chatService';
import type { ChatMessage, Citation, AgentLog } from './types';

// Re-export types so consumers don't need to import from two places.
export type { ChatMessage, Citation, AgentLog };

export function useChat() {
  // Granular selectors — each subscriber only re-renders when its own slice changes.
  const messages        = useAppStore((s) => s.chat.messages);
  const evidence        = useAppStore((s) => s.chat.evidence);
  const agentLogs       = useAppStore((s) => s.chat.agentLogs);
  const inputQuery      = useAppStore((s) => s.chat.input);
  const isGenerating    = useAppStore((s) => s.chat.isGenerating);
  const isBackendUnavailable = useAppStore((s) => s.chat.backendUnavailable);

  const addMessage           = useAppStore((s) => s.addMessage);
  const replaceMessages      = useAppStore((s) => s.replaceMessages);
  const addEvidence          = useAppStore((s) => s.addEvidence);
  const updateInput          = useAppStore((s) => s.updateInput);
  const setGenerating        = useAppStore((s) => s.setGenerating);
  const setBackendUnavailable = useAppStore((s) => s.setBackendUnavailable);
  const clearConversation    = useAppStore((s) => s.clearConversation);

  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeMediaId     = useAppStore((s) => s.activeMediaId);

  useEffect(() => {
    async function loadHistory() {
      try {
        const history = await getChatHistory(activeWorkspaceId);
        if (history && history.length > 0) {
          const formatted: ChatMessage[] = history.map((h) => ({
            id: h.id,
            sender: h.sender,
            content: h.content,
            timestamp: h.timestamp,
            citations: h.citations ? mapBackendCitations(h.citations) : undefined,
          }));
          replaceMessages(formatted);
        }
      } catch {
        // Backend unavailable or empty history
      }
    }

    if (messages.length <= 1) {
      loadHistory();
    }
  }, [activeWorkspaceId]);


  const sendMessage = async (queryText?: string) => {
    const query = queryText ?? inputQuery;
    if (!query.trim() || isGenerating) return;

    const userMsg: ChatMessage = {
      id: `user_${Date.now()}`,
      sender: 'user',
      content: query,
      timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
    };

    addMessage(userMsg);
    updateInput('');
    setGenerating(true);

    try {
      const data = await sendChatQuery(query, activeWorkspaceId, activeMediaId ?? undefined);
      setBackendUnavailable(false);

      const mappedCitations = mapBackendCitations(data.citations, activeMediaId ?? '', 'Lecture Segment');

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: mappedCitations,
      };

      addMessage(assistantMsg);
      if (mappedCitations.length > 0) {
        addEvidence(mappedCitations);
      }
    } catch {
      setBackendUnavailable(true);

      const errorMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: `Backend Service Unavailable: Unable to process "${query}". Please ensure the FastAPI backend is running at http://localhost:8000.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      addMessage(errorMsg);
    } finally {
      setGenerating(false);
    }
  };

  return {
    messages,
    evidence,
    agentLogs,
    inputQuery,
    setInputQuery: updateInput,   // preserve the surface API ChatWorkspace.tsx expects
    sendMessage,
    isGenerating,
    isBackendUnavailable,
    clearConversation,
  };
}
