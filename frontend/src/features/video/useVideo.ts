import { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getTranscript, BackendTranscriptSegmentDTO } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';

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
  const { activeMediaId, currentTime, setCurrentTime } = useAppStore();
  const [segments, setSegments] = useState<TranscriptSegment[]>(MOCK_TRANSCRIPT_SEGMENTS);
  const [loading, setLoading] = useState<boolean>(false);
  const [hasTranscript, setHasTranscript] = useState<boolean>(true);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  useEffect(() => {
    if (!activeMediaId) return;

    async function fetchTranscript() {
      try {
        setLoading(true);
        const data = await getTranscript(activeMediaId!);
        if (data.segments && data.segments.length > 0) {
          const mapped: TranscriptSegment[] = data.segments.map((seg: BackendTranscriptSegmentDTO, idx: number) => ({
            id: `seg_${idx}`,
            timestamp: formatSecondsToTimestamp(seg.start_time),
            speaker: seg.speaker || 'Lecturer',
            text: seg.text,
          }));
          setSegments(mapped);
          setHasTranscript(true);
        } else {
          setSegments(MOCK_TRANSCRIPT_SEGMENTS);
          setHasTranscript(true);
        }
      } catch (_err) {
        // Fallback
        setSegments(MOCK_TRANSCRIPT_SEGMENTS);
        setHasTranscript(true);
      } finally {
        setLoading(false);
      }
    }

    fetchTranscript();
  }, [activeMediaId]);

  const seekTo = (timestampStr: string) => {
    setCurrentTime(timestampStr);
    const parts = timestampStr.split(':');
    if (parts.length === 2 && videoRef.current) {
      const seconds = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      videoRef.current.currentTime = seconds;
    }
  };

  return { currentTime, segments, videoRef, seekTo, loading, hasTranscript };
}
