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

const MOCK_MEDIA_ASSETS: MediaAsset[] = [
  {
    id: 'med_sample_01',
    title: 'Lecture 14: Attention Mechanisms in Transformers',
    description: 'Scaled Dot-Product Attention, Query-Key-Value vectors, and positional encoding functions.',
    duration: '42:15',
    wordCount: 1420,
    masteryScore: 94,
    thumbnailEmoji: '🎥',
    uploadedAt: '2 hours ago',
  },
  {
    id: 'med_sample_02',
    title: 'CNN & Backpropagation Fundamentals',
    description: 'Convolutional kernels, max pooling, and chain rule gradient calculations.',
    duration: '35:40',
    wordCount: 980,
    masteryScore: 88,
    thumbnailEmoji: '🧠',
    uploadedAt: 'Yesterday',
  },
  {
    id: 'med_sample_03',
    title: 'Linear Regression & Gradient Descent',
    description: 'Loss optimization, learning rate schedules, and Mean Squared Error minimization.',
    duration: '28:10',
    wordCount: 750,
    masteryScore: 100,
    thumbnailEmoji: '📈',
    uploadedAt: '3 days ago',
  },
];

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
            description: `Media Item ID ${id} stored in SQLite workspace collection.`,
            duration: '42:15',
            wordCount: 1420,
            masteryScore: 90,
            thumbnailEmoji: '🎥',
            uploadedAt: 'Recently',
          }));
          setAssets(realAssets);
        } else {
          // Empty workspace (no default mock replacement per design note)
          setAssets([]);
        }
      } catch (_err) {
        // Backend offline fallback
        setIsOffline(true);
        setAssets(MOCK_MEDIA_ASSETS);
      } finally {
        setLoading(false);
      }
    }
    fetchAssets();
  }, []);

  return { assets, loading, isOffline };
}
