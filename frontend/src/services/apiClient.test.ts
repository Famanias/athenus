import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { apiClient } from './apiClient';
import { queryClient } from './queryClient';

interface TranscriptResponse {
  media_id: string;
  full_text: string;
  segments: Array<{ start_time: number; end_time: number; text: string }>;
}

describe('apiClient GET freshness', () => {
  beforeEach(() => {
    queryClient.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    queryClient.clear();
  });

  it('observes transcript data that becomes available after processing', async () => {
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ media_id: 'media-1', full_text: '', segments: [] }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            media_id: 'media-1',
            full_text: 'Transcript ready',
            segments: [
              { start_time: 0, end_time: 5, text: 'Transcript ready' },
            ],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
    vi.stubGlobal('fetch', fetchMock);

    const processing = await apiClient<TranscriptResponse>(
      '/api/v1/media/media-1/transcript?workspace_id=default'
    );
    const completed = await apiClient<TranscriptResponse>(
      '/api/v1/media/media-1/transcript?workspace_id=default'
    );

    expect(processing.segments).toEqual([]);
    expect(completed.segments).toEqual([
      { start_time: 0, end_time: 5, text: 'Transcript ready' },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it('does not invalidate resource caches after an unrelated mutation', async () => {
    const resourceKey = ['api', '/api/v1/media/media-1/transcript'] as const;
    queryClient.setQueryData(resourceKey, { segments: [{ text: 'ready' }] });
    vi.stubGlobal(
      'fetch',
      vi.fn<typeof fetch>().mockResolvedValue(
        new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    );

    await apiClient<{ ok: boolean }>('/api/v1/learning/notes', {
      method: 'POST',
      body: JSON.stringify({ title: 'Unrelated note' }),
    });

    expect(queryClient.getQueryState(resourceKey)?.isInvalidated).toBe(false);
  });
});
