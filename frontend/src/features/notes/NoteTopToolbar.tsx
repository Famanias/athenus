'use client';

import React from 'react';

export type NoteViewMode = 'transcript' | 'editor';

interface NoteTopToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  viewMode: NoteViewMode;
  onViewModeChange: (mode: NoteViewMode) => void;
  hasTranscript?: boolean;
}

export const NoteTopToolbar: React.FC<NoteTopToolbarProps> = ({
  title,
  onTitleChange,
  viewMode,
  onViewModeChange,
  hasTranscript = false,
}) => {
  return (
    <div className="w-full">
      {/* Top Row: Title + Transcript | Notes Segmented Switcher */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        {/* Note Title Input */}
        <div className="flex-1 min-w-0">
          <input
            type="text"
            value={title}
            onChange={(e) => onTitleChange(e.target.value)}
            placeholder="Untitled Note..."
            className="w-full bg-transparent font-type-light text-2xl font-bold text-on-surface placeholder:text-on-surface-variant/40 outline-none focus:ring-0 border-none px-0 tracking-tight"
          />
        </div>

        {/* Right Action Bar: Segmented Switcher */}
        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center bg-surface-container-high p-1 rounded-lg border border-outline-variant/40">
            <button
              onClick={() => onViewModeChange('transcript')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                viewMode === 'transcript'
                  ? 'bg-surface text-on-surface shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">graphic_eq</span>
              <span>Transcript</span>
              {hasTranscript && (
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              )}
            </button>

            <button
              onClick={() => onViewModeChange('editor')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                viewMode === 'editor'
                  ? 'bg-surface text-on-surface shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]">notes</span>
              <span>Notes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

