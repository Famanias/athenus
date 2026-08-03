// useChat — coordinates async chat logic on top of the Zustand chat slice.
//
// State lives in the store (survives view unmount/remount).
// This hook owns only the async sendMessage workflow — no local useState.

import { useEffect, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { sendChatQuery, getChatHistory, clearChatHistory, mapBackendCitations } from '@/services/chatService';
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
  const isConversationLoading = useAppStore((s) => s.chat.isConversationLoading);
  const activeSessionId = useAppStore((s) => s.chat.activeSessionId);
  const isDraftSession  = useAppStore((s) => s.chat.isDraftSession);

  const addMessage           = useAppStore((s) => s.addMessage);
  const replaceMessages      = useAppStore((s) => s.replaceMessages);
  const addEvidence          = useAppStore((s) => s.addEvidence);
  const updateInput          = useAppStore((s) => s.updateInput);
  const setGenerating        = useAppStore((s) => s.setGenerating);
  const setBackendUnavailable = useAppStore((s) => s.setBackendUnavailable);
  const setConversationLoading = useAppStore((s) => s.setConversationLoading);
  const storeClearConversation = useAppStore((s) => s.clearConversation);
  const setActiveSessionId   = useAppStore((s) => s.setActiveSessionId);

  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeMediaId     = useAppStore((s) => s.activeMediaId);

  // Synchronize chat history whenever workspace or session changes
  useEffect(() => {
    let isCancelled = false;

    async function loadHistory() {
      if (isDraftSession && !activeSessionId) {
        replaceMessages([]);
        addEvidence([]);
        setConversationLoading(false);
        return;
      }

      setConversationLoading(true);
      try {
        const history = await getChatHistory(activeWorkspaceId, activeSessionId);
        if (isCancelled) return;

        if (history && history.length > 0) {
          const formatted: ChatMessage[] = history.map((h) => ({
            id: h.id,
            sender: h.sender,
            content: h.content,
            timestamp: h.timestamp,
            citations: h.citations ? mapBackendCitations(h.citations) : undefined,
          }));
          replaceMessages(formatted);
          const lastAsst = formatted.filter((m) => m.sender === 'assistant').pop();
          if (lastAsst && lastAsst.citations) {
            addEvidence(lastAsst.citations);
          } else {
            addEvidence([]);
          }
        } else {
          replaceMessages([]);
          addEvidence([]);
        }
      } catch {
        if (!isCancelled) {
          replaceMessages([]);
          addEvidence([]);
        }
      } finally {
        if (!isCancelled) {
          setConversationLoading(false);
        }
      }
    }

    loadHistory();

    return () => {
      isCancelled = true;
    };
  }, [activeWorkspaceId, activeSessionId, isDraftSession, replaceMessages, addEvidence, setConversationLoading]);

  const handleClearConversation = useCallback(async () => {
    try {
      await clearChatHistory(activeWorkspaceId, activeSessionId);
    } catch {
      // Backend unavailable or error clearing history
    }
    storeClearConversation();
  }, [activeWorkspaceId, activeSessionId, storeClearConversation]);

  const sendMessage = async (queryText?: string, currentTimestamp?: number, selectedText?: string) => {
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
      const data = await sendChatQuery(
        query,
        activeWorkspaceId,
        activeSessionId,
        activeMediaId ?? undefined,
        currentTimestamp,
        selectedText
      );
      setBackendUnavailable(false);

      if (data.session_id && data.session_id !== activeSessionId) {
        setActiveSessionId(data.session_id, false);
      }

      const mappedCitations = mapBackendCitations(data.citations, activeMediaId ?? '', 'Lecture Segment');

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: mappedCitations,
      };

      addMessage(assistantMsg);
      addEvidence(mappedCitations);
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
    isConversationLoading,
    clearConversation: handleClearConversation,
  };
}
