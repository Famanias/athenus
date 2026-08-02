import { useState, useEffect } from 'react';
import { getWorkspaces } from '@/services/libraryService';

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

export function useLibrary() {
  const [assets, setAssets] = useState<MediaAsset[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [isOffline, setIsOffline] = useState<boolean>(false);

  useEffect(() => {
    async function fetchAssets() {
      try {
        setLoading(true);
        const workspaces = await getWorkspaces();
        setIsOffline(false);

        if (workspaces && workspaces.length > 0 && workspaces[0].media_item_ids.length > 0) {
          // Map real workspace media items
          const realAssets: MediaAsset[] = workspaces[0].media_item_ids.map((id, idx) => ({
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
  }, []);

  return { assets, loading, isOffline };
}
