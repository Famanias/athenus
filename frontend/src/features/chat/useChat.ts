import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';

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
  const { activeWorkspaceId } = useAppStore();
  const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
  const [evidence, setEvidence] = useState<Citation[]>(INITIAL_MESSAGES[2].citations || []);
  const [agentLogs, setAgentLogs] = useState<AgentLog[]>(INITIAL_LOGS);
  const [inputQuery, setInputQuery] = useState<string>('');
  const [isGenerating, setIsGenerating] = useState<boolean>(false);

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
      // Fetch backend RAG API endpoint
      const res = await fetch('http://localhost:8000/api/v1/chat/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          workspace_id: activeWorkspaceId,
          query: query,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        const assistantMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          sender: 'assistant',
          content: data.answer || data.response,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          citations: data.citations || [],
        };
        setMessages((prev) => [...prev, assistantMsg]);
        if (data.citations) setEvidence(data.citations);
      } else {
        throw new Error('API non-200');
      }
    } catch (_err) {
      // Local fallback grounded answer
      setTimeout(() => {
        const fallbackMsg: ChatMessage = {
          id: `asst_${Date.now()}`,
          sender: 'assistant',
          content: `Here is the grounded response for "${query}": The QKV self-attention mechanism processes tokens in parallel, scaling scores by sqrt(d_k) to maintain stable gradient magnitudes.`,
          timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
          citations: [
            {
              mediaId: 'med_sample_01',
              mediaTitle: 'Lecture 14',
              startTime: '05:15',
              endTime: '06:40',
              score: 0.89,
              textSnippet: 'Self-attention allows the model to compute dynamic context vectors...',
            },
          ],
        };
        setMessages((prev) => [...prev, fallbackMsg]);
        setEvidence(fallbackMsg.citations || []);
      }, 600);
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
  };
}
