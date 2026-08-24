import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { queryClient } from '@/services/queryClient';
import {
  refreshTranscriptQuery,
  transcriptQueryKey,
  transcriptQueryOptions,
} from './transcriptQueries';

describe('transcript query policy', () => {
  beforeEach(() => queryClient.clear());

  afterEach(() => {
    vi.unstubAllGlobals();
    queryClient.clear();
  });

  it('isolates transcript state by workspace and media', () => {
    expect(transcriptQueryKey('media-1', 'workspace-a')).not.toEqual(
      transcriptQueryKey('media-1', 'workspace-b')
    );
    expect(transcriptQueryKey('media-1', 'workspace-a')).not.toEqual(
      transcriptQueryKey('media-2', 'workspace-a')
    );
  });

  it('refreshes the exact transcript after processing completes', async () => {
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
            full_text: 'Ready',
            segments: [{ start_time: 0, end_time: 5, text: 'Ready' }],
          }),
          { status: 200, headers: { 'Content-Type': 'application/json' } }
        )
      );
    vi.stubGlobal('fetch', fetchMock);

    const processing = await queryClient.fetchQuery(
      transcriptQueryOptions('media-1', 'workspace-a')
    );
    const completed = await refreshTranscriptQuery('media-1', 'workspace-a');

    expect(processing.segments).toEqual([]);
    expect(completed.segments).toEqual([
      { start_time: 0, end_time: 5, text: 'Ready' },
    ]);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});
