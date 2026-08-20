'use client';

import React from 'react';
import { useNotes } from './useNotes';
import { NoteSummaryHeader } from './NoteSummaryHeader';
import { NoteSectionCard } from './NoteSectionCard';
import { Button } from '@/components/ui/Button';

export const NotesWorkspace: React.FC = () => {
  const {
    notes,
    activeNote,
    selectedVersion,
    artifact,
    loading,
    generating,
    error,
    toastMessage,
    generateNotes,
    selectVersion,
    jumpToSource,
  } = useNotes();

  const isJobRunning = generating || artifact?.status === 'generating';

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-5xl mx-auto space-y-6 w-full">
      {/* Completion Toast Notification */}
      {toastMessage && (
        <div className="px-4 py-2.5 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 font-mono text-xs font-semibold animate-pulse flex items-center justify-between">
          <span>{toastMessage}</span>
          <span className="text-[10px] text-emerald-400/60 uppercase tracking-wider">Synced</span>
        </div>
      )}

      {/* Header Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-type-light text-2xl font-bold text-on-surface flex items-center gap-2.5">
            <span className="material-symbols-outlined text-primary text-2xl">auto_stories</span>
            AI Synthesis & Study Notes
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            Structured, versioned study notes extracted directly from lecture transcripts and documents.
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Version Selector Dropdown */}
          {notes.length > 1 && (
            <div className="flex items-center gap-2 bg-surface-container-high px-3 py-1.5 rounded-lg border border-outline-variant/50">
              <span className="text-xs text-on-surface-variant font-mono">Version:</span>
              <select
                value={selectedVersion || ''}
                onChange={(e) => selectVersion(Number(e.target.value))}
                className="bg-transparent text-xs font-mono text-primary outline-none cursor-pointer"
              >
                {notes.map((n) => (
                  <option key={n.id} value={n.version} className="bg-surface text-on-surface">
                    v{n.version} ({n.sections?.length || 0} sections)
                  </option>
                ))}
              </select>
            </div>
          )}

          {activeNote && (
            <span className="font-mono text-xs text-secondary bg-secondary/10 px-3 py-1.5 rounded border border-secondary/30">
              Active v{activeNote.version}
            </span>
          )}

          <Button
            onClick={() => generateNotes(!!activeNote)}
            disabled={isJobRunning}
            icon={isJobRunning ? 'sync' : 'auto_awesome'}
            variant="primary"
          >
            {isJobRunning
              ? 'Generating...'
              : activeNote
              ? `Regenerate (v${(activeNote.version || 1) + 1})`
              : 'Generate Notes'}
          </Button>
        </div>
      </div>

      {/* Progress Bar & Stage Status */}
      {isJobRunning && artifact && (
        <div className="p-4 bg-surface-container-high/60 border border-primary/20 rounded-xl space-y-2">
          <div className="flex items-center justify-between text-xs font-mono">
            <span className="text-primary font-semibold flex items-center gap-2">
              <span className="inline-block w-2 h-2 rounded-full bg-primary animate-ping" />
              {artifact.message || 'Synthesizing lecture notes...'}
            </span>
            <span className="text-on-surface-variant font-bold">{artifact.progress || 20}%</span>
          </div>
          <div className="w-full bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
            <div
              className="bg-primary h-full transition-all duration-300 ease-out rounded-full"
              style={{ width: `${Math.max(10, artifact.progress || 20)}%` }}
            />
          </div>
        </div>
      )}

      {/* Error Banner */}
      {error && (
        <div className="p-4 bg-error/10 border border-error/30 rounded-lg text-error text-xs flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">error</span>
          <span>{error}</span>
        </div>
      )}

      {/* Main Content Area */}
      {loading ? (
        <div className="py-20 flex flex-col items-center justify-center text-on-surface-variant space-y-3">
          <span className="material-symbols-outlined text-3xl animate-spin text-primary">sync</span>
          <p className="text-xs font-mono">Loading study notes...</p>
        </div>
      ) : activeNote ? (
        <div className="space-y-6">
          {/* Executive Summary & Action Items Header */}
          <NoteSummaryHeader note={activeNote} />

          {/* Sections List */}
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-mono uppercase tracking-wider text-on-surface-variant font-semibold">
                Detailed Lecture Sections ({activeNote.sections?.length || 0})
              </h3>
              <span className="text-[11px] text-on-surface-variant/70">
                Click any timestamp badge to seek video player
              </span>
            </div>

            {activeNote.sections && activeNote.sections.length > 0 ? (
              activeNote.sections.map((section, idx) => (
                <NoteSectionCard
                  key={section.id || idx}
                  section={section}
                  index={idx}
                  onJumpToSource={jumpToSource}
                />
              ))
            ) : (
              <div className="p-8 text-center bg-surface-container-low border border-dashed border-outline-variant rounded-xl text-on-surface-variant text-xs">
                No sections recorded in this note version.
              </div>
            )}
          </div>
        </div>
      ) : (
        /* Empty State */
        <div className="py-16 px-6 text-center bg-surface-container-low border border-dashed border-outline-variant rounded-2xl flex flex-col items-center justify-center space-y-4 max-w-lg mx-auto">
          <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center text-primary">
            <span className="material-symbols-outlined text-3xl">menu_book</span>
          </div>
          <div>
            <h3 className="font-type-light text-lg font-bold text-on-surface">No Study Notes Yet</h3>
            <p className="text-xs text-on-surface-variant max-w-sm mt-1">
              Generate structured, timestamp-grounded notes with summaries, key takeaways, and action items from your uploaded lectures and documents.
            </p>
          </div>
          <Button
            onClick={() => generateNotes(false)}
            disabled={isJobRunning}
            icon="auto_awesome"
            variant="primary"
            className="mt-2"
          >
            Generate First Notes
          </Button>
        </div>
      )}
    </div>
  );
};
