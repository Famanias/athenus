'use client';

import React from 'react';
import type { NoteFolderDTO } from './useNotes';

export type NoteViewMode = 'transcript' | 'editor';

interface NoteTopToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  viewMode: NoteViewMode;
  onViewModeChange: (mode: NoteViewMode) => void;
  folders: NoteFolderDTO[];
  folderId: string | null;
  onFolderChange: (folderId: string | null) => void;
  hasTranscript?: boolean;
  saving?: boolean;
  disabled?: boolean;
}

export const NoteTopToolbar: React.FC<NoteTopToolbarProps> = ({
  title,
  onTitleChange,
  viewMode,
  onViewModeChange,
  folders,
  folderId,
  onFolderChange,
  hasTranscript = false,
  saving = false,
  disabled = false,
}) => {
  return (
    <div className="w-full space-y-3">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
        <div className="flex-1 min-w-0">
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
        </div>

        <div className="flex items-center shrink-0">
          <div className="flex items-center bg-surface-container-high p-1 rounded-lg border border-outline-variant/40">
            <button
              type="button"
              onClick={() => onViewModeChange('transcript')}
              className={`min-h-10 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 ${
                viewMode === 'transcript'
                  ? 'bg-surface text-on-surface shadow-xs font-semibold'
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
              className={`min-h-10 flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 ${
                viewMode === 'editor'
                  ? 'bg-surface text-on-surface shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px]" aria-hidden="true">notes</span>
              <span>Notes</span>
            </button>
          </div>

        </div>
      </div>

      <div className="flex items-center gap-3 text-xs text-on-surface-variant">
        <label htmlFor="note-folder" className="font-medium">Folder</label>
        <select
          id="note-folder"
          value={folderId ?? ''}
          onChange={(event) => onFolderChange(event.target.value || null)}
          disabled={disabled}
          className="min-h-9 max-w-56 rounded-md border border-outline-variant/40 bg-surface-container-high px-2 text-on-surface outline-none focus-visible:ring-2 focus-visible:ring-primary/60 disabled:opacity-50"
        >
          <option value="">Unorganized Notes</option>
          {folders.map((folder) => (
            <option key={folder.id} value={folder.id}>{folder.name}</option>
          ))}
        </select>
        <span className="font-mono text-[11px]" role="status" aria-live="polite">
          {saving ? 'Saving…' : disabled ? 'No note selected' : 'Saved'}
        </span>
      </div>
    </div>
  );
};
