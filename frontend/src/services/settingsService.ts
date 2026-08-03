import { apiClient } from './apiClient';

export interface ProviderSettingsDTO {
  default_llm: string;
  default_stt: string;
  gpu_acceleration: boolean;
  api_key?: string;
}

export interface ProviderSettingsResponse {
  default_llm: string;
  default_stt: string;
  default_embedding: string;
  gpu_acceleration: boolean;
  api_key?: string;
  status: string;
}

export async function getProviderSettings(): Promise<ProviderSettingsResponse> {
  return apiClient<ProviderSettingsResponse>('/api/v1/settings/providers');
}

export async function saveProviderSettings(
  payload: ProviderSettingsDTO
): Promise<ProviderSettingsResponse> {
  return apiClient<ProviderSettingsResponse>('/api/v1/settings/providers', {
    method: 'PUT',
    body: JSON.stringify(payload),
  });
}

export async function clearAllData(): Promise<{ status: string; message: string }> {
  return apiClient<{ status: string; message: string }>('/api/v1/system/clear-data', {
    method: 'POST',
  });
}
