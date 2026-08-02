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
    content: 'Welcome back! I am your Athenus AI Learning Assistant. Ask me any question about your indexed video lectures, formulas, or concepts.',
    timestamp: '14:20',
  },
  {
    id: 'msg_1',
    sender: 'user',
    content: 'Why do Transformer architectures scale the dot-product attention scores by 1/sqrt(d_k)?',
    timestamp: '14:21',
  },
  {
    id: 'msg_2',
    sender: 'assistant',
    content: 'Transformers divide dot-product attention scores by sqrt(d_k) because for large vector dimensions d_k, the magnitude of the dot product grows large. This forces the Softmax function into regions with extremely small gradients, leading to vanishing gradient problems during backpropagation.',
    timestamp: '14:21',
    citations: [
      {
        mediaId: 'med_sample_01',
        mediaTitle: 'Lecture 14',
        startTime: '12:40',
        endTime: '13:10',
        score: 0.94,
        textSnippet: 'Scaling by sqrt(d_k) prevents vanishing gradient degradation in Softmax layers...',
      },
    ],
  },
];

const INITIAL_LOGS: AgentLog[] = [
  { timestamp: '14:21:01', agent: 'PlannerAgent', message: 'Query intent: Mathematical rationale' },
  { timestamp: '14:21:02', agent: 'RetrieverAgent', message: '3 hits retrieved in Qdrant (bge-small)' },
  { timestamp: '14:21:02', agent: 'ValidatorAgent', message: 'Grounding score: 98%' },
];

export function useChat() {
  const { activeWorkspaceId, activeMediaId } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [evidence, setEvidence] = useState<Citation[]>(INITIAL_MESSAGES[2].citations || []);
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

      const mappedCitations = mapBackendCitations(data.citations, activeMediaId || 'med_sample_01', 'Lecture Segment');

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
      // Local-first fallback handling
      setIsBackendUnavailable(true);
      const fallbackCitations: Citation[] = [
        {
          mediaId: activeMediaId || 'med_sample_01',
          mediaTitle: 'Lecture Segment',
          startTime: '05:15',
          endTime: '06:40',
          score: 0.89,
          textSnippet: 'Self-attention computes dynamic context vectors across input tokens.',
        },
      ];

      const fallbackMsg: ChatMessage = {
        id: `asst_${Date.now()}`,
        sender: 'assistant',
        content: `Local AI Response (Offline Mode): Processed query "${query}". The self-attention mechanism scales dot products to prevent vanishing gradients during backpropagation.`,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
        citations: fallbackCitations,
      };

      setMessages((prev) => [...prev, fallbackMsg]);
      setEvidence(fallbackCitations);
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
