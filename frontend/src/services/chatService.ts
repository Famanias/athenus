import { apiClient } from './apiClient';
import { Citation } from '@/features/chat/useChat';

export interface BackendCitationDTO {
  chunk_id?: string;
  start_time: number;
  end_time: number;
  text: string;
}

export interface BackendChatResponse {
  query: string;
  answer: string;
  citations: BackendCitationDTO[];
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
  defaultMediaId = 'med_sample_01',
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

export async function sendChatQuery(
  query: string,
  workspaceId = 'default',
  mediaId?: string
): Promise<BackendChatResponse> {
  return apiClient<BackendChatResponse>('/api/v1/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      workspace_id: workspaceId,
      media_id: mediaId,
    }),
  });
}
