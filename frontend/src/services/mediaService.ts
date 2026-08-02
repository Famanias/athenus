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

export async function getTranscript(mediaId: string): Promise<BackendTranscriptDTO> {
  return apiClient<BackendTranscriptDTO>(`/api/v1/media/${mediaId}/transcript`);
}

export async function uploadMedia(file: File, workspaceId = 'default'): Promise<MediaUploadDTO> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('workspace_id', workspaceId);

  return apiClient<MediaUploadDTO>('/api/v1/media/upload', {
    method: 'POST',
    body: formData,
  });
}

export function createMediaProcessingStream(mediaId: string): EventSource {
  return new EventSource(`${API_BASE_URL}/api/v1/media/${mediaId}/stream`);
}
