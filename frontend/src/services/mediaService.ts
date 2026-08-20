import { apiClient } from './apiClient';
import { API_BASE_URL } from '@/config/env';

export interface BackendTranscriptSegmentDTO {
  start_time: number;
  end_time: number;
  text: string;
  speaker?: string;
}

export interface BackendTranscriptDTO {
  media_id: string;
  full_text: string;
  segments: BackendTranscriptSegmentDTO[];
}

export interface MediaUploadDTO {
  media_id: string;
  workspace_id: string;
  title: string;
  status: string;
}

/** Read-only file metadata returned by GET /media/{id}/info. */
export interface MediaInfoDTO {
  media_id: string;
  title: string;
  file_path: string;
  file_name: string;
  media_type: string;
  file_size_bytes: number;
  mime_type: string;
  url: string;
}

/** Fetch file metadata for the active document (read-only). */
export async function getMediaInfo(mediaId: string): Promise<MediaInfoDTO> {
  return apiClient<MediaInfoDTO>(`/api/v1/media/${encodeURIComponent(mediaId)}/info`);
}

export async function getTranscript(mediaId: string, workspaceId?: string): Promise<BackendTranscriptDTO> {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
  return apiClient<BackendTranscriptDTO>(`/api/v1/media/${encodeURIComponent(mediaId)}/transcript${query}`);
}

export async function uploadMedia(
  file: File,
  workspaceId = 'default',
  title?: string
): Promise<MediaUploadDTO> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workspace_id', workspaceId);
  if (title) {
    formData.append('title', title);
  }

  return apiClient<MediaUploadDTO>('/api/v1/media/upload', {
    method: 'POST',
    body: formData,
  });
}


export function createMediaProcessingStream(mediaId: string): EventSource {
  return new EventSource(`${API_BASE_URL}/api/v1/media/${encodeURIComponent(mediaId)}/stream`);
}

export function getMediaUrl(mediaId: string, workspaceId?: string): string {
  const query = workspaceId ? `?workspace_id=${encodeURIComponent(workspaceId)}` : '';
  return `${API_BASE_URL}/api/v1/media/${encodeURIComponent(mediaId)}/file${query}`;
}

export interface BackendDocumentPageDTO {
  page_number: number;
  text: string;
  page_type: string;
  section_title?: string;
}

export interface BackendDocumentPagesDTO {
  media_id: string;
  total_pages: number;
  pages: BackendDocumentPageDTO[];
}

export async function getDocumentPages(mediaId: string): Promise<BackendDocumentPagesDTO> {
  return apiClient<BackendDocumentPagesDTO>(`/api/v1/media/${encodeURIComponent(mediaId)}/pages`);
}
