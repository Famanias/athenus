import { formatSecondsToTimestamp } from '@/services/chatService';
import type { BackendTranscriptSegmentDTO } from '@/services/mediaService';

export interface TranscriptSegment {
  id: string;
  timestamp: string;
  start_seconds: number;
  end_seconds: number;
  speaker: string;
  text: string;
  isHighlighted?: boolean;
}

export function mapTranscriptSegments(
  segments: BackendTranscriptSegmentDTO[]
): TranscriptSegment[] {
  return segments.map((segment, index) => ({
    id: `seg_${index}`,
    timestamp: formatSecondsToTimestamp(segment.start_time),
    start_seconds: segment.start_time,
    end_seconds: segment.end_time,
    speaker: segment.speaker || 'Lecturer',
    text: segment.text,
  }));
}

export function timestampToSeconds(timestamp: string): number | null {
  const parts = timestamp.split(':');
  if (parts.length < 2 || parts.length > 3) return null;
  const values = parts.map(Number);
  if (values.some((value) => !Number.isFinite(value) || value < 0)) return null;
  if (parts.length === 2) return values[0] * 60 + values[1];
  return values[0] * 3600 + values[1] * 60 + values[2];
}

export function findActiveTranscriptSegment(
  segments: TranscriptSegment[],
  seconds: number
): number {
  const match = segments.findIndex(
    (segment) => seconds >= segment.start_seconds && seconds < segment.end_seconds
  );
  if (match !== -1) return match;
  if (segments.length > 0 && seconds >= segments[segments.length - 1].end_seconds) {
    return segments.length - 1;
  }
  return -1;
}
