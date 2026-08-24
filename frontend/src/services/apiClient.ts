import { API_BASE_URL } from '@/config/env';
import { queryClient } from '@/services/queryClient';

export class ApiError extends Error {
  status?: number;
  isNetworkError: boolean;

  constructor(message: string, status?: number, isNetworkError = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.isNetworkError = isNetworkError;
  }
}

async function executeRequest<T>(
  url: string,
  options: RequestInit,
  headers: Headers
): Promise<T> {
  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const errorText = await response.text().catch(() => '');
    throw new ApiError(
      errorText || `API error ${response.status}: ${response.statusText}`,
      response.status,
      false
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export async function apiClient<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = endpoint.startsWith('http') ? endpoint : `${API_BASE_URL}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  try {
    const method = (options.method || 'GET').toUpperCase();
    if (method === 'GET') {
      const isLiveStatus = endpoint.includes('/status') || endpoint.includes('/jobs');
      const queryOptions = {
        queryKey: ['api', url],
        queryFn: () => executeRequest<T>(url, options, headers),
        staleTime: isLiveStatus ? 0 : 30_000,
      };
      if (isLiveStatus) {
        return await queryClient.fetchQuery(queryOptions);
      }
      return await queryClient.ensureQueryData({
        ...queryOptions,
        revalidateIfStale: true,
      });
    }
    const result = await executeRequest<T>(url, options, headers);
    await queryClient.invalidateQueries({ queryKey: ['api'] });
    return result;
  } catch (error: any) {
    if (error instanceof ApiError) {
      throw error;
    }
    throw new ApiError(
      error?.message || 'Network error: Failed to connect to Athenus backend',
      undefined,
      true
    );
  }
}
