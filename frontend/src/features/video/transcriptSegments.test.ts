import { describe, expect, it } from 'vitest';

import {
  findActiveTranscriptSegment,
  mapTranscriptSegments,
  timestampToSeconds,
} from './transcriptSegments';

describe('transcript segment presentation', () => {
  const segments = mapTranscriptSegments([
    { start_time: 0, end_time: 5, text: 'Opening' },
    { start_time: 5, end_time: 12, text: 'Core idea', speaker: 'Tutor' },
  ]);

  it('maps persisted API segments into timestamped render rows', () => {
    expect(segments).toEqual([
      {
        id: 'seg_0',
        timestamp: '00:00',
        start_seconds: 0,
        end_seconds: 5,
        speaker: 'Lecturer',
        text: 'Opening',
      },
      {
        id: 'seg_1',
        timestamp: '00:05',
        start_seconds: 5,
        end_seconds: 12,
        speaker: 'Tutor',
        text: 'Core idea',
      },
    ]);
  });

  it('selects the correct row at boundaries and after the final segment', () => {
    expect(findActiveTranscriptSegment(segments, 0)).toBe(0);
    expect(findActiveTranscriptSegment(segments, 5)).toBe(1);
    expect(findActiveTranscriptSegment(segments, 99)).toBe(1);
  });

  it('parses rendered timestamps for seek interaction', () => {
    expect(timestampToSeconds('02:03')).toBe(123);
    expect(timestampToSeconds('01:02:03')).toBe(3723);
    expect(timestampToSeconds('invalid')).toBeNull();
  });
});
