import { useState, useEffect } from 'react';
import { getWorkspaces } from '@/services/libraryService';
import { useAppStore } from '@/store/useAppStore';

export interface MediaAsset {
  id: string;
  title: string;
  description: string;
  duration: string;
  wordCount: number;
  masteryScore: number;
  thumbnailEmoji: string;
  uploadedAt: string;
}

export function useLibrary(targetWorkspaceId?: string) {
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isOffline, setIsOffline] = useState<boolean>(false);

  const effectiveWorkspaceId = targetWorkspaceId || activeWorkspaceId;

  useEffect(() => {
    async function fetchAssets() {
      try {
        setLoading(true);
        const workspaces = await getWorkspaces();
        setIsOffline(false);

        const currentWs =
          workspaces.find((w) => w.id === effectiveWorkspaceId) || workspaces[0];

        if (currentWs && currentWs.media_item_ids && currentWs.media_item_ids.length > 0) {
          const realAssets: MediaAsset[] = currentWs.media_item_ids.map((id, idx) => ({
            id,
            title: `Indexed Lecture ${idx + 1}`,
            description: `Media Item ID ${id} stored in workspace collection.`,
            duration: '00:00',
            wordCount: 0,
            masteryScore: 0,
            thumbnailEmoji: '🎥',
            uploadedAt: 'Recently',
          }));
          setAssets(realAssets);
        } else {
          setAssets([]);
        }
      } catch (_err) {
        setIsOffline(true);
        setAssets([]);
      } finally {
        setLoading(false);
      }
    }
    fetchAssets();
  }, [effectiveWorkspaceId]);

  return { assets, loading, isOffline };
}
