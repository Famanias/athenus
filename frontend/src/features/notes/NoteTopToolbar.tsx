'use client';

import React from 'react';

export type NoteViewMode = 'transcript' | 'editor';

interface NoteTopToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  viewMode: NoteViewMode;
  onViewModeChange: (mode: NoteViewMode) => void;
  hasTranscript?: boolean;
  saving?: boolean;
  disabled?: boolean;
}

export const NoteTopToolbar: React.FC<NoteTopToolbarProps> = ({
  title,
  onTitleChange,
  viewMode,
  onViewModeChange,
  hasTranscript = false,
  saving = false,
  disabled = false,
}) => {
  return (
    <div className="w-full">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex-1 min-w-0 flex items-center gap-3">
          <label htmlFor="note-title" className="sr-only">Note title</label>
          <input
            id="note-title"
            type="text"
            value={title}
            onChange={(event) => onTitleChange(event.target.value)}
            placeholder="Untitled Note"
            disabled={disabled}
            className="w-full bg-transparent font-type-light text-2xl font-bold text-on-surface placeholder:text-on-surface-variant/40 outline-none focus-visible:ring-2 focus-visible:ring-primary/60 rounded px-1 -ml-1 tracking-tight disabled:opacity-50"
          />
          <span className="font-mono text-[11px] text-on-surface-variant shrink-0" role="status" aria-live="polite">
            {saving ? 'Saving…' : disabled ? '' : 'Saved'}
          </span>
        </div>

        <div className="flex items-center shrink-0">
          <div className="flex items-center bg-surface-container-high p-1 rounded-lg border border-outline-variant/40">
            <button
              type="button"
              onClick={() => onViewModeChange('transcript')}
              className={`min-h-10 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70 ${
                viewMode === 'transcript'
                  ? 'bg-secondary text-on-secondary shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]" aria-hidden="true">graphic_eq</span>
              <span>Transcript</span>
              {hasTranscript && <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" aria-hidden="true" />}
            </button>

            <button
              type="button"
              onClick={() => onViewModeChange('editor')}
              className={`min-h-10 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-secondary/70 ${
                viewMode === 'editor'
                  ? 'bg-secondary text-on-secondary shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]" aria-hidden="true">notes</span>
              <span>Notes</span>
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
