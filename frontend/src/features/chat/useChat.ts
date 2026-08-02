import { useAppStore } from '@/store/useAppStore';
import { sendChatQuery, mapBackendCitations } from '@/services/chatService';
import { ChatMessage, Citation, AgentLog } from './types';

export type { ChatMessage, Citation, AgentLog } from './types';

export function useChat() {
  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeMediaId = useAppStore((s) => s.activeMediaId);
  const messages = useAppStore((s) => s.chat.messages);
  const citations = useAppStore((s) => s.chat.citations);
  const agentLogs = useAppStore((s) => s.chat.logs);
  const inputQuery = useAppStore((s) => s.chat.input);
  const isGenerating = useAppStore((s) => s.chat.isGenerating);
  const isBackendUnavailable = useAppStore((s) => s.chat.backendUnavailable);

  const addMessage = useAppStore((s) => s.addMessage);
  const replaceCitations = useAppStore((s) => s.replaceCitations);
  const updateInput = useAppStore((s) => s.updateInput);
  const setGenerating = useAppStore((s) => s.setGenerating);
  const setBackendUnavailable = useAppStore((s) => s.setBackendUnavailable);

  const sendMessage = async (queryText?: string) => {
    const query = queryText || inputQuery;
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
      const data = await sendChatQuery(query, activeWorkspaceId || 'default', activeMediaId || undefined);
      setBackendUnavailable(false);

      const mappedCitations = mapBackendCitations(data.citations, activeMediaId || '', 'Lecture Segment');

      const assistantMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: data.answer,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: mappedCitations,
      };

      addMessage(assistantMsg);
      if (mappedCitations.length > 0) {
        replaceCitations(mappedCitations);
      }
    } catch (_err: any) {
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
    evidence: citations,
    agentLogs,
    inputQuery,
    setInputQuery: updateInput,
    sendMessage,
    isGenerating,
    isBackendUnavailable,
  };
}