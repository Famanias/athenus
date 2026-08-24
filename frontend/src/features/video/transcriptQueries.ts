import { queryOptions, useQuery } from '@tanstack/react-query';

import { getTranscript } from '@/services/mediaService';
import { queryClient } from '@/services/queryClient';

const DEFAULT_WORKSPACE_ID = 'default';

export function transcriptQueryKey(mediaId: string, workspaceId?: string | null) {
  return ['transcript', workspaceId || DEFAULT_WORKSPACE_ID, mediaId] as const;
}

export function transcriptQueryOptions(mediaId: string, workspaceId?: string | null) {
  return queryOptions({
    queryKey: transcriptQueryKey(mediaId, workspaceId),
    queryFn: () => getTranscript(mediaId, workspaceId || DEFAULT_WORKSPACE_ID),
    staleTime: 30_000,
  });
}

export function useTranscriptQuery(
  mediaId: string | null,
  workspaceId?: string | null
) {
  return useQuery({
    ...transcriptQueryOptions(mediaId || '', workspaceId),
    enabled: Boolean(mediaId),
  });
}

export async function refreshTranscriptQuery(
  mediaId: string,
  workspaceId?: string | null
) {
  const options = transcriptQueryOptions(mediaId, workspaceId);
  await queryClient.invalidateQueries({ queryKey: options.queryKey, exact: true });
  return queryClient.fetchQuery({ ...options, staleTime: 0 });
}
