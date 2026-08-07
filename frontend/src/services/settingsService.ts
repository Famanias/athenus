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

export interface LocalProviderStatusDTO {
  provider_id: string;
  label: string;
  connected: boolean;
  version?: string;
  base_url?: string;
  error?: string;
}

export interface CatalogModelDTO {
  full_id: string;
  name: string;
  tag: string;
  provider_id: string;
  size_bytes?: number;
}

export interface LocalModelCatalogDTO {
  provider_id: string;
  models: CatalogModelDTO[];
  count: number;
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
  name?: string;
  context_window?: number;
  size_bytes?: number;
}

export interface ProviderCatalogProviderDTO {
  id: string;
  label: string;
  is_local?: boolean;
  is_configured?: boolean;
  is_available?: boolean;
  active_model?: string;
  error?: string;
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

export interface TestConnectionResponse {
  provider_id: string;
  is_available: boolean;
  is_configured: boolean;
  active_model: string;
  error?: string;
}

export async function getProviderCatalog(): Promise<ProviderCatalogResponse> {
  return apiClient<ProviderCatalogResponse>('/api/v1/settings/providers/catalog');
}

export async function testProviderConnection(providerId: string): Promise<TestConnectionResponse> {
  return apiClient<TestConnectionResponse>(`/api/v1/settings/providers/${providerId}/test`, {
    method: 'POST',
  });
}

export async function getLocalProviderStatus(providerId: string): Promise<LocalProviderStatusDTO> {
  return apiClient<LocalProviderStatusDTO>(`/api/v1/settings/providers/local/${providerId}`);
}

export async function getLocalProviderModels(providerId: string): Promise<LocalModelCatalogDTO> {
  return apiClient<LocalModelCatalogDTO>(`/api/v1/settings/providers/local/${providerId}/models`);
}

export async function clearAllData(): Promise<{ status: string; message: string }> {
  return apiClient<{ status: string; message: string }>('/api/v1/system/clear-data', {
    method: 'POST',
  });
}
