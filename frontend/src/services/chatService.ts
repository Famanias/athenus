import { apiClient } from './apiClient';
import { Citation } from '@/features/chat/useChat';

export interface BackendCitationDTO {
  chunk_id?: string;
  start_time: number;
  end_time: number;
  text: string;
  // Generalized document/PDF ingestion fields (optional for backward compat)
  source_type?: 'video' | 'pdf';
  page_number?: number | null;
  section_title?: string | null;
  location?: Record<string, any> | null;
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
  session_id: string;
  citations: BackendCitationDTO[];
  context_provenance?: ContextProvenanceDTO;
}

export interface ChatSessionDTO {
  id: string;
  workspace_id: string;
  title: string;
  is_pinned: boolean;
  is_archived: boolean;
  last_message_at?: string | null;
  message_count: number;
  preview_text?: string | null;
  created_at: string;
  updated_at: string;
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
    // Generalized document/PDF ingestion fields (optional, backward-compat)
    sourceType: c.source_type,
    pageNumber: typeof c.page_number === 'number' ? c.page_number : undefined,
    sectionTitle: c.section_title || undefined,
    location: c.location || undefined,
  }));
}

export interface BackendChatMessageDTO {
  id: string;
  session_id: string;
  sender: 'user' | 'assistant';
  content: string;
  timestamp: string;
  citations?: BackendCitationDTO[];
}

export async function sendChatQuery(
  query: string,
  workspaceId = 'default',
  sessionId?: string | null,
  mediaId?: string,
  currentTimestamp?: number,
  selectedText?: string,
  documentId?: string,
  sourceType?: 'video' | 'pdf',
  currentPage?: number
): Promise<BackendChatResponse> {
  return apiClient<BackendChatResponse>('/api/v1/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      workspace_id: workspaceId,
      session_id: sessionId || undefined,
      media_id: mediaId,
      current_timestamp: currentTimestamp,
      selected_text: selectedText,
      document_id: documentId,
      source_type: sourceType,
      current_page: currentPage,
    }),
  });
}

export async function getWorkspaceSessions(workspaceId = 'default', includeArchived = true): Promise<ChatSessionDTO[]> {
  return apiClient<ChatSessionDTO[]>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/sessions?include_archived=${includeArchived}`);
}

export async function createWorkspaceSession(workspaceId: string, title?: string): Promise<ChatSessionDTO> {
  return apiClient<ChatSessionDTO>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/sessions`, {
    method: 'POST',
    body: JSON.stringify({ title }),
  });
}

export async function updateSession(sessionId: string, data: { title?: string; is_pinned?: boolean; is_archived?: boolean }): Promise<ChatSessionDTO> {
  return apiClient<ChatSessionDTO>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteSession(sessionId: string): Promise<{ status: string; deleted_session_id: string }> {
  return apiClient<{ status: string; deleted_session_id: string }>(`/api/v1/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
  });
}

export async function getChatHistory(workspaceId = 'default', sessionId?: string | null): Promise<BackendChatMessageDTO[]> {
  let url = `/api/v1/chat/history?workspace_id=${encodeURIComponent(workspaceId)}`;
  if (sessionId) {
    url += `&session_id=${encodeURIComponent(sessionId)}`;
  }
  return apiClient<BackendChatMessageDTO[]>(url);
}

export async function clearChatHistory(workspaceId = 'default', sessionId?: string | null): Promise<{ status: string; deleted_count: number }> {
  let url = `/api/v1/chat/history?workspace_id=${encodeURIComponent(workspaceId)}`;
  if (sessionId) {
    url += `&session_id=${encodeURIComponent(sessionId)}`;
  }
  return apiClient<{ status: string; deleted_count: number }>(url, {
    method: 'DELETE',
  });
}
