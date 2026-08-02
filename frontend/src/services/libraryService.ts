import { apiClient } from './apiClient';
import { MediaAsset } from '@/features/library/useLibrary';

export interface BackendWorkspaceDTO {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  media_item_ids: string[];
}

export async function getWorkspaces(): Promise<BackendWorkspaceDTO[]> {
  return apiClient<BackendWorkspaceDTO[]>('/api/v1/workspaces');
}

export async function getWorkspace(workspaceId: string): Promise<BackendWorkspaceDTO> {
  return apiClient<BackendWorkspaceDTO>(`/api/v1/workspaces/${workspaceId}`);
}
