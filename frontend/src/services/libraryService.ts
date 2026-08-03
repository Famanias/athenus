import { apiClient } from './apiClient';

export interface BackendWorkspaceDTO {
  id: string;
  name: string;
  description?: string;
  icon?: string;
  is_pinned?: boolean;
  is_archived?: boolean;
  last_accessed_at?: string;
  media_item_ids: string[];
}

export interface ActiveWorkspaceDTO {
  active_workspace_id: string;
}

export async function getWorkspaces(includeArchived = true): Promise<BackendWorkspaceDTO[]> {
  return apiClient<BackendWorkspaceDTO[]>(`/api/v1/workspaces?include_archived=${includeArchived}`);
}

export async function getActiveWorkspace(): Promise<ActiveWorkspaceDTO> {
  return apiClient<ActiveWorkspaceDTO>('/api/v1/workspaces/active');
}

export async function activateWorkspace(workspaceId: string): Promise<ActiveWorkspaceDTO> {
  return apiClient<ActiveWorkspaceDTO>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}/activate`, {
    method: 'POST',
  });
}

export async function getWorkspace(workspaceId: string): Promise<BackendWorkspaceDTO> {
  return apiClient<BackendWorkspaceDTO>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`);
}

export async function createWorkspace(data: {
  name: string;
  description?: string;
  icon?: string;
  is_pinned?: boolean;
}): Promise<BackendWorkspaceDTO> {
  return apiClient<BackendWorkspaceDTO>('/api/v1/workspaces', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateWorkspace(
  workspaceId: string,
  data: {
    name?: string;
    description?: string;
    icon?: string;
    is_pinned?: boolean;
    is_archived?: boolean;
  }
): Promise<BackendWorkspaceDTO> {
  return apiClient<BackendWorkspaceDTO>(`/api/v1/workspaces/${encodeURIComponent(workspaceId)}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

export async function deleteWorkspace(workspaceId: string): Promise<{ status: string; deleted_workspace_id: string; active_workspace_id: string }> {
  return apiClient<{ status: string; deleted_workspace_id: string; active_workspace_id: string }>(
    `/api/v1/workspaces/${encodeURIComponent(workspaceId)}`,
    {
      method: 'DELETE',
    }
  );
}
