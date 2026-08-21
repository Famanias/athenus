'use client';

import React from 'react';
import { formatSecondsToTimestamp } from '@/services/chatService';

interface NoteBottomBarProps {
  isRecording: boolean;
  recordingDuration: number;
  audioLevel: number;
  isUploading: boolean;
  onToggleRecording: () => void;
  promptValue: string;
  onPromptChange: (val: string) => void;
  onGenerateNotes: () => void;
  generating: boolean;
}

export const NoteBottomBar: React.FC<NoteBottomBarProps> = ({
  isRecording,
  recordingDuration,
  audioLevel,
  isUploading,
  onToggleRecording,
  promptValue,
  onPromptChange,
  onGenerateNotes,
  generating,
}) => {
  return (
    <div className="w-full bg-surface-container-high/90 backdrop-blur-md border border-outline-variant/60 rounded-2xl p-2 px-3 shadow-lg flex items-center justify-between gap-3">
      {/* Left: Dedicated Audio Transcription / Recording Button */}
      <div className="flex items-center gap-2">
        <button
          onClick={onToggleRecording}
          disabled={isUploading || generating}
          title={isRecording ? 'Stop Recording and Transcribe' : 'Start Audio Transcription'}
          className={`relative flex items-center justify-center w-10 h-10 rounded-xl transition-all cursor-pointer shadow-sm ${
            isRecording
              ? 'bg-red-500 text-white animate-pulse shadow-red-500/30'
              : 'bg-surface-container-highest hover:bg-surface-container text-on-surface hover:text-primary'
          }`}
        >
          {isUploading ? (
            <span className="material-symbols-outlined text-lg animate-spin text-primary">sync</span>
          ) : isRecording ? (
            <span className="material-symbols-outlined text-lg">stop</span>
          ) : (
            <span className="material-symbols-outlined text-lg">mic</span>
          )}

          {/* Pulsing halo when recording */}
          {isRecording && (
            <span
              className="absolute -inset-1 rounded-xl bg-red-500/20 animate-ping pointer-events-none"
              style={{
                transform: `scale(${1 + audioLevel * 0.4})`,
              }}
            />
          )}
        </button>

        {/* Recording Duration Counter Badge */}
        {isRecording && (
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/30 text-red-400 font-mono text-xs font-semibold">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            <span>{formatSecondsToTimestamp(recordingDuration)}</span>
          </div>
        )}

        {isUploading && (
          <span className="text-xs font-mono text-primary animate-pulse">
            Transcribing audio...
          </span>
        )}
      </div>

      {/* Center: "Ask anything..." or Instruction Input */}
      <div className="flex-1 min-w-0">
        <input
          type="text"
          value={promptValue}
          onChange={(e) => onPromptChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !generating && !isRecording) {
              onGenerateNotes();
            }
          }}
          placeholder="Ask anything or add formatting instructions..."
          className="w-full bg-transparent text-xs text-on-surface placeholder:text-on-surface-variant/40 outline-none px-2 py-1.5 border-none"
        />
      </div>

      {/* Right: Generate Notes Action Button matching mockup.html */}
      <div className="flex items-center shrink-0">
        <button
          onClick={onGenerateNotes}
          disabled={generating || isRecording || isUploading}
          className={`flex items-center gap-2 px-4 py-2 rounded-xl border border-[#45464c] bg-[#273647] hover:bg-[#2f4155] text-[#e9c349] font-mono text-xs md:text-sm font-medium transition-all cursor-pointer select-none whitespace-nowrap shadow-sm ${
            generating
              ? 'opacity-60 cursor-wait'
              : 'hover:border-[#e9c349]/40 active:scale-[0.98]'
          }`}
        >
          {generating ? (
            <span className="material-symbols-outlined text-[15px] animate-spin text-[#e9c349]">sync</span>
          ) : (
            <svg
              className="w-[15px] h-[15px] shrink-0 text-[#e9c349]"
              viewBox="0 0 15 15"
              fill="none"
              aria-hidden="true"
            >
              <path
                d="M7.5 1l1.5 4.5L13.5 7l-4.5 1.5L7.5 13 6 8.5 1.5 7l4.5-1.5L7.5 1Z"
                stroke="currentColor"
                strokeWidth="1.2"
                strokeLinejoin="round"
              />
            </svg>
          )}
          <span>{generating ? 'Generating...' : 'Generate Notes'}</span>
        </button>
      </div>
    </div>
  );
};
