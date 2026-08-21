'use client';

import React, { useState, useRef, useEffect } from 'react';
import { formatSecondsToTimestamp } from '@/services/chatService';
import { AudioSourceMode } from './useAudioRecorder';

interface NoteBottomBarProps {
  isRecording: boolean;
  recordingDuration: number;
  audioLevel: number;
  isUploading: boolean;
  sourceMode: AudioSourceMode;
  onSourceModeChange: (mode: AudioSourceMode) => void;
  onToggleRecording: () => void;
  promptValue: string;
  onPromptChange: (val: string) => void;
  onGenerateNotes: () => void;
  generating: boolean;
}

const SOURCE_MODE_CONFIG: Record<
  AudioSourceMode,
  { label: string; shortLabel: string; icon: string; desc: string }
> = {
  both: {
    label: 'Mic & Speaker (All Audio)',
    shortLabel: 'All Audio',
    icon: 'hearing',
    desc: 'Transcribes both your microphone and computer audio (meetings, lectures, videos).',
  },
  mic: {
    label: 'Microphone Only',
    shortLabel: 'Mic Only',
    icon: 'mic',
    desc: 'Transcribes only your voice input via microphone.',
  },
  system: {
    label: 'Speaker Only',
    shortLabel: 'Speaker Only',
    icon: 'volume_up',
    desc: 'Transcribes only computer playback audio (videos, calls, lectures).',
  },
};

export const NoteBottomBar: React.FC<NoteBottomBarProps> = ({
  isRecording,
  recordingDuration,
  audioLevel,
  isUploading,
  sourceMode,
  onSourceModeChange,
  onToggleRecording,
  promptValue,
  onPromptChange,
  onGenerateNotes,
  generating,
}) => {
  const [selectorOpen, setSelectorOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setSelectorOpen(false);
      }
    };
    if (selectorOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [selectorOpen]);

  const currentMode = SOURCE_MODE_CONFIG[sourceMode] || SOURCE_MODE_CONFIG.both;

  return (
    <div className="w-full bg-surface-container-high/90 backdrop-blur-md border border-outline-variant/60 rounded-2xl p-2 px-3 shadow-lg flex items-center justify-between gap-3 relative">
      {/* Left: Dedicated Audio Transcription / Recording Button & Mode Selector */}
      <div className="flex items-center gap-2">
        {/* Source Mode Dropdown Trigger */}
        <div className="relative" ref={dropdownRef}>
          <button
            type="button"
            onClick={() => !isRecording && !isUploading && setSelectorOpen(!selectorOpen)}
            disabled={isRecording || isUploading}
            title={currentMode.desc}
            aria-haspopup="listbox"
            aria-expanded={selectorOpen}
            className={`flex items-center gap-1.5 px-2.5 py-2 rounded-xl text-xs font-medium transition-all select-none border border-outline-variant/40 ${
              isRecording
                ? 'bg-red-500/10 text-red-400 border-red-500/30 cursor-default'
                : 'bg-surface-container-highest/80 hover:bg-surface-container-highest text-on-surface hover:text-primary cursor-pointer'
            }`}
          >
            <span className="material-symbols-outlined text-[16px] shrink-0 text-primary">
              {currentMode.icon}
            </span>
            <span className="hidden sm:inline-block font-mono text-[11px]">
              {currentMode.shortLabel}
            </span>
            {!isRecording && (
              <span className="material-symbols-outlined text-[14px] opacity-60">
                arrow_drop_down
              </span>
            )}
          </button>

          {/* Mode Selector Popover */}
          {selectorOpen && !isRecording && (
            <div
              role="listbox"
              aria-label="Select audio source mode"
              className="absolute bottom-full left-0 mb-2 w-64 rounded-xl border border-outline-variant/50 bg-surface-container-highest shadow-2xl p-1.5 z-50 flex flex-col gap-1 backdrop-blur-xl animate-in fade-in zoom-in-95 duration-100"
            >
              <div className="px-2.5 py-1 text-[10px] font-mono uppercase tracking-wider text-on-surface-variant/70 border-b border-outline-variant/30">
                Capture Audio Source
              </div>
              {(Object.keys(SOURCE_MODE_CONFIG) as AudioSourceMode[]).map((modeKey) => {
                const config = SOURCE_MODE_CONFIG[modeKey];
                const active = sourceMode === modeKey;
                return (
                  <button
                    key={modeKey}
                    type="button"
                    role="option"
                    aria-selected={active}
                    onClick={() => {
                      onSourceModeChange(modeKey);
                      setSelectorOpen(false);
                    }}
                    className={`flex items-start gap-2.5 px-2.5 py-2 rounded-lg text-left transition-colors cursor-pointer ${
                      active
                        ? 'bg-primary/15 text-primary font-medium'
                        : 'hover:bg-surface-container text-on-surface'
                    }`}
                  >
                    <span className="material-symbols-outlined text-[18px] shrink-0 mt-0.5">
                      {config.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <div className="text-xs flex items-center justify-between">
                        <span>{config.label}</span>
                        {active && (
                          <span className="material-symbols-outlined text-[15px] text-primary">
                            check
                          </span>
                        )}
                      </div>
                      <div className="text-[10px] text-on-surface-variant/80 mt-0.5 line-clamp-2 leading-tight">
                        {config.desc}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {/* Record / Stop Button */}
        <button
          onClick={onToggleRecording}
          disabled={isUploading || generating}
          title={isRecording ? 'Stop Recording and Transcribe' : `Start Audio Transcription (${currentMode.label})`}
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
