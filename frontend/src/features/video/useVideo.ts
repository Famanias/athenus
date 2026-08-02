import { useState, useEffect, useRef } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getTranscript, getMediaUrl, BackendTranscriptSegmentDTO } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';

export interface TranscriptSegment {
  id: string;
  timestamp: string;
  speaker: string;
  text: string;
  isHighlighted?: boolean;
}

export function useVideo() {
  const { activeMediaId, currentTime, setCurrentTime } = useAppStore();
  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [hasTranscript, setHasTranscript] = useState<boolean>(false);
  const [mediaSrc, setMediaSrc] = useState<string>('');
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const mediaUrl = activeMediaId ? getMediaUrl(activeMediaId) : '';

  useEffect(() => {
    if (!activeMediaId) {
      setSegments([]);
      setHasTranscript(false);
      setMediaSrc('');
      return;
    }

    // Point the <video> element at the backend-served file.
    setMediaSrc(mediaUrl);

    async function fetchTranscript() {
      try {
        setLoading(true);
        const data = await getTranscript(activeMediaId!);
        if (data && data.segments && data.segments.length > 0) {
          const mapped: TranscriptSegment[] = data.segments.map((seg: BackendTranscriptSegmentDTO, idx: number) => ({
            id: `seg_${idx}`,
            timestamp: formatSecondsToTimestamp(seg.start_time),
            speaker: seg.speaker || 'Lecturer',
            text: seg.text,
          }));
          setSegments(mapped);
          setHasTranscript(true);
        } else {
          setSegments([]);
          setHasTranscript(false);
        }
      } catch (_err) {
        setSegments([]);
        setHasTranscript(false);
      } finally {
        setLoading(false);
      }
    }

    fetchTranscript();
  }, [activeMediaId, mediaUrl]);

  const seekTo = (timestampStr: string) => {
    setCurrentTime(timestampStr);
    const parts = timestampStr.split(':');
    if (parts.length === 2 && videoRef.current) {
      const seconds = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      videoRef.current.currentTime = seconds;
    }
  };

  return { currentTime, segments, mediaSrc, videoRef, seekTo, loading, hasTranscript };
}
