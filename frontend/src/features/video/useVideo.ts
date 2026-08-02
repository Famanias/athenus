import { useState, useRef } from 'react';
import { useAppStore } from '@/store/useAppStore';

export interface TranscriptSegment {
  id: string;
  timestamp: string;
  speaker: string;
  text: string;
  isHighlighted?: boolean;
}

const MOCK_TRANSCRIPT_SEGMENTS: TranscriptSegment[] = [
  {
    id: 'seg_1',
    timestamp: '00:15',
    speaker: 'Dr. Aris Thorne',
    text: 'Welcome to this deep dive session into Neural Architectures and Transformer Sequence Modeling.',
  },
  {
    id: 'seg_2',
    timestamp: '05:15',
    speaker: 'Dr. Aris Thorne',
    text: 'The self-attention mechanism allows the model to compute dynamic weights between Query vector Q and Key vector K.',
  },
  {
    id: 'seg_3',
    timestamp: '12:40',
    speaker: 'Dr. Aris Thorne',
    text: 'By scaling the dot product by sqrt(d_k), we prevent exploding gradient magnitudes during Softmax evaluation.',
    isHighlighted: true,
  },
  {
    id: 'seg_4',
    timestamp: '18:20',
    speaker: 'Dr. Aris Thorne',
    text: 'Positional encodings inject positional information using sine and cosine functions across dynamic frequencies.',
  },
  {
    id: 'seg_5',
    timestamp: '25:05',
    speaker: 'Dr. Aris Thorne',
    text: 'Multi-head attention projects Queries, Keys, and Values into h different subspaces simultaneously.',
  },
];

export function useVideo() {
  const { currentTime, setCurrentTime } = useAppStore();
  const [segments] = useState<TranscriptSegment[]>(MOCK_TRANSCRIPT_SEGMENTS);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const seekTo = (timestampStr: string) => {
    setCurrentTime(timestampStr);
    // Parse MM:SS to seconds
    const parts = timestampStr.split(':');
    if (parts.length === 2 && videoRef.current) {
      const seconds = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      videoRef.current.currentTime = seconds;
    }
  };

  return { currentTime, segments, videoRef, seekTo };
}
