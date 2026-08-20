'use client';

import React from 'react';
import { formatSecondsToTimestamp } from '@/services/chatService';

export interface TranscriptSegmentDTO {
  id?: string;
  start_time?: number;
  end_time?: number;
  text: string;
  speaker?: string;
}

interface TranscriptViewProps {
  segments: TranscriptSegmentDTO[];
  loading?: boolean;
  onSeek?: (seconds: number) => void;
  onStartRecording?: () => void;
}

export const TranscriptView: React.FC<TranscriptViewProps> = ({
  segments,
  loading = false,
  onSeek,
  onStartRecording,
}) => {
  if (loading) {
    return (
      <div className="py-24 flex flex-col items-center justify-center space-y-3 text-on-surface-variant">
        <span className="material-symbols-outlined text-3xl animate-spin text-primary">sync</span>
        <p className="text-xs font-mono">Loading speech transcript...</p>
      </div>
    );
  }

  if (!segments || segments.length === 0) {
    return (
      <div className="py-20 px-6 text-center bg-surface-container-low border border-dashed border-outline-variant rounded-2xl flex flex-col items-center justify-center space-y-4 max-w-md mx-auto my-8">
        <div className="w-12 h-12 rounded-xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
          <span className="material-symbols-outlined text-2xl">mic</span>
        </div>
        <div>
          <h4 className="font-type-light text-base font-bold text-on-surface">No Transcript Available</h4>
          <p className="text-xs text-on-surface-variant mt-1 max-w-xs">
            Start a live audio recording using the microphone button below or select a transcribed lecture from your workspace library.
          </p>
        </div>
        {onStartRecording && (
          <button
            onClick={onStartRecording}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary border border-primary/20 text-xs font-semibold transition-all cursor-pointer"
          >
            <span className="material-symbols-outlined text-base">mic</span>
            <span>Start Live Dictation</span>
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3 p-1">
      <div className="flex items-center justify-between pb-2 border-b border-outline-variant/20 text-xs text-on-surface-variant font-mono">
        <span>{segments.length} Speech Utterances</span>
        <span>Click timestamp to seek</span>
      </div>

      <div className="space-y-2.5">
        {segments.map((seg, idx) => {
          const hasTime = seg.start_time !== undefined && seg.start_time !== null;
          const timeLabel = hasTime ? formatSecondsToTimestamp(seg.start_time!) : null;

          return (
            <div
              key={seg.id || idx}
              className="p-3 rounded-lg bg-surface-container-low border border-outline-variant/30 hover:border-outline-variant/80 transition-all flex items-start gap-3 group"
            >
              {/* Speaker / Turn Badge */}
              <div className="shrink-0 pt-0.5">
                <span className="w-6 h-6 rounded bg-surface-container-high flex items-center justify-center text-[10px] font-mono font-bold text-on-surface-variant">
                  {seg.speaker ? seg.speaker[0].toUpperCase() : `${idx + 1}`}
                </span>
              </div>

              {/* Segment Content */}
              <div className="flex-1 min-w-0 space-y-1">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-on-surface">
                    {seg.speaker || `Speaker Turn ${idx + 1}`}
                  </span>

                  {hasTime && (
                    <button
                      onClick={() => onSeek?.(seg.start_time!)}
                      className="text-[11px] font-mono text-primary bg-primary/10 hover:bg-primary/20 px-2 py-0.5 rounded border border-primary/20 transition-colors cursor-pointer"
                    >
                      {timeLabel}
                    </button>
                  )}
                </div>

                <p className="text-xs text-on-surface/90 leading-relaxed">{seg.text}</p>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
