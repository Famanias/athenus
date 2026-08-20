'use client';

import React from 'react';

export type NoteViewMode = 'transcript' | 'editor' | 'enhanced';

interface NoteTopToolbarProps {
  title: string;
  onTitleChange: (title: string) => void;
  dateStr?: string;
  folderName?: string;
  viewMode: NoteViewMode;
  onViewModeChange: (mode: NoteViewMode) => void;
  hasTranscript: boolean;
  hasEnhanced: boolean;
  onExport?: () => void;
}

export const NoteTopToolbar: React.FC<NoteTopToolbarProps> = ({
  title,
  onTitleChange,
  dateStr = new Date().toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
  folderName = 'Personal',
  viewMode,
  onViewModeChange,
  hasTranscript,
  hasEnhanced,
  onExport,
}) => {
  return (
    <div className="space-y-3 pb-3 border-b border-outline-variant/30">
      {/* Top Row: Title + View Mode Segmented Switcher */}
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

        {/* Right Action Bar: Segmented Switcher + Export Actions */}
        <div className="flex items-center gap-3 shrink-0">
          {/* Segmented View Mode Switcher */}
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

            <button
              onClick={() => onViewModeChange('enhanced')}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all cursor-pointer ${
                viewMode === 'enhanced'
                  ? 'bg-surface text-primary shadow-xs font-semibold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-[15px] text-primary">sparkles</span>
              <span>Enhanced</span>
              {hasEnhanced && (
                <span className="w-1.5 h-1.5 rounded-full bg-primary" />
              )}
            </button>
          </div>

          {/* Quick Action Icons */}
          <div className="flex items-center gap-1 text-on-surface-variant">
            <button
              onClick={onExport}
              title="Export Notes"
              className="p-1.5 hover:bg-surface-container-high rounded-md hover:text-on-surface transition-colors cursor-pointer"
            >
              <span className="material-symbols-outlined text-lg">download</span>
            </button>
          </div>
        </div>
      </div>

      {/* Metadata Badges Row */}
      <div className="flex flex-wrap items-center gap-2 text-xs text-on-surface-variant">
        {/* Date Badge */}
        <span className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-surface-container-high/60 border border-outline-variant/30">
          <span className="material-symbols-outlined text-[14px]">calendar_today</span>
          <span>{dateStr}</span>
        </span>

        {/* Add Attendees Badge */}
        <button
          className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-surface-container-high/60 border border-outline-variant/30 hover:border-outline transition-colors cursor-pointer text-on-surface-variant hover:text-on-surface"
        >
          <span className="material-symbols-outlined text-[14px]">person_add</span>
          <span>Add attendees</span>
        </button>

        {/* Space / Folder Badge */}
        <span className="flex items-center gap-1 px-2.5 py-1 rounded-md bg-surface-container-high/60 border border-outline-variant/30">
          <span className="material-symbols-outlined text-[14px]">folder</span>
          <span>{folderName}</span>
        </span>
      </div>
    </div>
  );
};
