import { useState, useEffect } from 'react';

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
  const [assets, setAssets] = useState<MediaAsset[]>(MOCK_MEDIA_ASSETS);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    // Attempt backend fetch if online
    async function fetchAssets() {
      try {
        setLoading(true);
        const res = await fetch('http://localhost:8000/api/v1/workspaces/ws_default');
        if (res.ok) {
          const data = await res.json();
          if (data.media_assets && data.media_assets.length > 0) {
            setAssets(data.media_assets);
          }
        }
      } catch (_err) {
        // Silent fallback to mock data
      } finally {
        setLoading(false);
      }
    }
    fetchAssets();
  }, []);

  return { assets, loading };
}
