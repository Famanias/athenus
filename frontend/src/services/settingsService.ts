import { apiClient } from './apiClient';

export interface ProviderSettingsDTO {
  default_llm: string;
  selected_ollama_model?: string;
  default_stt: string;
  gpu_acceleration: boolean;
  api_key?: string;
}

export interface ProviderSettingsResponse {
  default_llm: string;
  selected_ollama_model?: string;
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

export async function patchProviderSettings(
  payload: Partial<ProviderSettingsDTO>
): Promise<ProviderSettingsResponse> {
  return apiClient<ProviderSettingsResponse>('/api/v1/settings/providers', {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export interface ProviderCatalogModelDTO {
  id: string;
}

export interface ProviderCatalogProviderDTO {
  id: string;
  label: string;
  models: ProviderCatalogModelDTO[];
}

export interface ProviderCatalogSelectionDTO {
  provider: string;
  model: string | null;
}

export interface ProviderCatalogResponse {
  active: ProviderCatalogSelectionDTO;
  providers: ProviderCatalogProviderDTO[];
}

export async function getProviderCatalog(): Promise<ProviderCatalogResponse> {
  return apiClient<ProviderCatalogResponse>('/api/v1/settings/providers/catalog');
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
