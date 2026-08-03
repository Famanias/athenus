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

export interface DiscoveredModelDTO {
  full_id: string;
  model_name: string;
  tag: string;
  provider: string;
  size_bytes?: number;
}

export interface OllamaSettingsResponse {
  configured_dir?: string;
  resolved_dir?: string;
  valid: boolean;
  models_count: number;
  models: DiscoveredModelDTO[];
  error?: string;
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

export async function getOllamaSettings(): Promise<OllamaSettingsResponse> {
  return apiClient<OllamaSettingsResponse>('/api/v1/settings/ollama');
}

export async function updateOllamaDirectory(modelsDir: string): Promise<OllamaSettingsResponse> {
  return apiClient<OllamaSettingsResponse>('/api/v1/settings/ollama', {
    method: 'PUT',
    body: JSON.stringify({ models_dir: modelsDir }),
  });
}

export async function scanOllamaModels(): Promise<OllamaSettingsResponse> {
  return apiClient<OllamaSettingsResponse>('/api/v1/settings/ollama/scan', {
    method: 'POST',
  });
}

export async function clearAllData(): Promise<{ status: string; message: string }> {
  return apiClient<{ status: string; message: string }>('/api/v1/system/clear-data', {
    method: 'POST',
  });
}
