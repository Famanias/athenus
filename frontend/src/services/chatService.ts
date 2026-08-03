import { apiClient } from './apiClient';
import { Citation } from '@/features/chat/useChat';

export interface BackendCitationDTO {
  chunk_id?: string;
  start_time: number;
  end_time: number;
  text: string;
}

export interface ContextProvenanceDTO {
  media_title?: string;
  timestamp?: string;
  timestamp_range?: string;
  segment_count?: number;
  selected_text?: string;
}

export interface BackendChatResponse {
  query: string;
  answer: string;
  citations: BackendCitationDTO[];
  context_provenance?: ContextProvenanceDTO;
}

export function formatSecondsToTimestamp(seconds: number): string {
  if (isNaN(seconds) || seconds < 0) return '00:00';
  const totalSeconds = Math.floor(seconds);
  const mins = Math.floor(totalSeconds / 60);
  const secs = totalSeconds % 60;
  const mm = mins < 10 ? `0${mins}` : `${mins}`;
  const ss = secs < 10 ? `0${secs}` : `${secs}`;
  return `${mm}:${ss}`;
}

export function mapBackendCitations(
  citations: BackendCitationDTO[],
  defaultMediaId = '',
  defaultMediaTitle = 'Lecture Segment'
): Citation[] {
  if (!Array.isArray(citations)) return [];

  return citations.map((c) => ({
    mediaId: defaultMediaId,
    mediaTitle: defaultMediaTitle,
    startTime: formatSecondsToTimestamp(c.start_time),
    endTime: formatSecondsToTimestamp(c.end_time),
    score: 0.9,
    textSnippet: c.text || '',
  }));
}

export interface BackendChatMessageDTO {
  id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: BackendCitationDTO[];
}

export async function sendChatQuery(
  query: string,
  workspaceId = 'default',
  mediaId?: string,
  currentTimestamp?: number,
  selectedText?: string
): Promise<BackendChatResponse> {
  return apiClient<BackendChatResponse>('/api/v1/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      workspace_id: workspaceId,
      media_id: mediaId,
      current_timestamp: currentTimestamp,
      selected_text: selectedText,
    }),
  });
}

export async function getChatHistory(workspaceId = 'default'): Promise<BackendChatMessageDTO[]> {
  return apiClient<BackendChatMessageDTO[]>(`/api/v1/chat/history?workspace_id=${encodeURIComponent(workspaceId)}`);
}

