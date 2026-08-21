'use client';

import React, { useEffect, useState } from 'react';
import { useNotes } from './useNotes';
import { useAudioRecorder } from './useAudioRecorder';
import { NoteTopToolbar, NoteViewMode } from './NoteTopToolbar';
import { NoteSummaryHeader } from './NoteSummaryHeader';
import { NoteSectionCard } from './NoteSectionCard';
import { TranscriptView, TranscriptSegmentDTO } from './TranscriptView';
import { ManualNotesEditor } from './ManualNotesEditor';
import { NoteBottomBar } from './NoteBottomBar';
import { getTranscript } from '@/services/mediaService';
import { useAppStore } from '@/store/useAppStore';

export const NotesWorkspace: React.FC = () => {
  const activeWorkspaceId = useAppStore((s) => s.activeWorkspaceId);
  const activeMediaId = useAppStore((s) => s.activeMediaId);

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

  const {
    isRecording,
    recordingDuration,
    audioLevel,
    isUploading,
    startRecording,
    stopRecording,
    uploadRecordedAudio,
  } = useAudioRecorder();

  // Local State
  const [selectedSpace, setSelectedSpace] = useState<string>('Personal');
  const [viewMode, setViewMode] = useState<NoteViewMode>('editor');
  const [noteTitle, setNoteTitle] = useState<string>('AI Engineering Intern Candidate Profile');
  const [manualContent, setManualContent] = useState<string>('');
  const [promptValue, setPromptValue] = useState<string>('');
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegmentDTO[]>([]);
  const [loadingTranscript, setLoadingTranscript] = useState<boolean>(false);
  const [searchQuery, setSearchQuery] = useState<string>('');

  // Sync title when activeNote changes
  useEffect(() => {
    if (activeNote?.title) {
      setNoteTitle(activeNote.title);
    }
  }, [activeNote]);

  // Load transcript segments when activeMediaId changes
  useEffect(() => {
    let cancelled = false;
    async function loadSegs() {
      if (!activeMediaId) {
        setTranscriptSegments([]);
        return;
      }
      setLoadingTranscript(true);
      try {
        const res = await getTranscript(activeMediaId, activeWorkspaceId || undefined);
        if (!cancelled && res?.segments) {
          setTranscriptSegments(res.segments);
        }
      } catch {
        if (!cancelled) setTranscriptSegments([]);
      } finally {
        if (!cancelled) setLoadingTranscript(false);
      }
    }
    loadSegs();
    return () => {
      cancelled = true;
    };
  }, [activeMediaId, activeWorkspaceId]);

  // Audio Recording Toggle Handler
  const handleToggleRecording = async () => {
    if (!isRecording) {
      const ok = await startRecording();
      if (ok) {
        setViewMode('transcript');
      }
    } else {
      const blob = await stopRecording();
      if (blob && activeWorkspaceId) {
        const res = await uploadRecordedAudio(
          blob,
          activeWorkspaceId,
          noteTitle || 'Live Audio Note'
        );
        if (res?.media_id) {
          useAppStore.setState({ activeMediaId: res.media_id });
          // Switch to transcript view and reload segments
          setViewMode('transcript');
          setTimeout(async () => {
            try {
              const tr = await getTranscript(res.media_id, activeWorkspaceId);
              if (tr?.segments) setTranscriptSegments(tr.segments);
            } catch {}
          }, 3000);
        }
      }
    }
  };

  // Generate Notes Handler
  const handleGenerateNotes = async () => {
    const note = await generateNotes(!!activeNote, promptValue.trim() || undefined);
    if (note) {
      setViewMode('editor');
    }
  };

  const handleNewNote = () => {
    setNoteTitle('Untitled Note');
    setManualContent('');
    setViewMode('editor');
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      {/* Left Spaces Secondary Sidebar */}
      <aside className="w-56 border-r border-outline-variant/30 bg-surface-container-lowest/70 flex flex-col justify-between p-3 shrink-0 select-none">
        <div className="space-y-4">
          {/* New Note Action */}
          <div className="space-y-2">
            <button
              onClick={handleNewNote}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-lg bg-surface-container-high/80 hover:bg-surface-container-highest text-on-surface text-xs font-semibold transition-all cursor-pointer border border-outline-variant/30 shadow-xs"
            >
              <span className="material-symbols-outlined text-[16px] text-primary">edit_square</span>
              <span>New note</span>
            </button>
          </div>

          {/* Private Spaces List */}
          <div className="space-y-1">
            <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant/60 font-semibold px-2">
              Private Spaces
            </span>
            <div className="space-y-0.5 pt-1">
              {[
                { name: 'Personal', icon: 'folder', count: 5 },
                { name: 'Meetings', icon: 'folder', count: 1 },
                { name: 'Videos', icon: 'folder', count: 0 },
                { name: 'Learning', icon: 'folder', count: 4 },
              ].map((space) => (
                <button
                  key={space.name}
                  onClick={() => setSelectedSpace(space.name)}
                  className={`w-full flex items-center justify-between px-2.5 py-1.5 rounded-lg text-xs font-medium transition-colors cursor-pointer ${
                    selectedSpace === space.name
                      ? 'bg-primary/10 text-primary font-semibold'
                      : 'text-on-surface-variant hover:bg-surface-container-high/50 hover:text-on-surface'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    <span className="material-symbols-outlined text-[15px]">{space.icon}</span>
                    <span>{space.name}</span>
                  </div>
                  {space.count > 0 && (
                    <span className="text-[11px] font-mono text-on-surface-variant/70">
                      {space.count}
                    </span>
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Team Spaces */}
          <div className="space-y-1 pt-2">
            <span className="text-[10px] font-mono uppercase tracking-wider text-on-surface-variant/60 font-semibold px-2">
              Team Spaces
            </span>
            <button className="w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs text-on-surface-variant hover:text-on-surface hover:bg-surface-container-high/50 transition-colors cursor-pointer">
              <span className="material-symbols-outlined text-[15px]">add</span>
              <span>New team space</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main Note Canvas */}
      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        {/* Top App / Note Toolbar */}
        <div className="p-6 pb-2 shrink-0">
          <NoteTopToolbar
            title={noteTitle}
            onTitleChange={setNoteTitle}
            viewMode={viewMode}
            onViewModeChange={setViewMode}
            hasTranscript={transcriptSegments.length > 0}
          />
        </div>

        {/* Completion Toast Banner */}
        {toastMessage && (
          <div className="mx-6 px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 font-mono text-xs font-semibold animate-pulse flex items-center justify-between shrink-0">
            <span>{toastMessage}</span>
            <span className="text-[10px] text-emerald-400/60 uppercase tracking-wider">Synced</span>
          </div>
        )}

        {/* Dynamic View Canvas Body */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-6 pt-2 pb-24 space-y-4">
          {/* Progress Bar & Stage Status */}
          {(generating || artifact?.status === 'generating') && (
            <div className="p-4 bg-surface-container-high/60 border border-primary/20 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-primary font-semibold flex items-center gap-2">
                  <span className="inline-block w-2 h-2 rounded-full bg-primary animate-ping" />
                  {artifact?.message || 'Synthesizing study notes...'}
                </span>
                <span className="text-on-surface-variant font-bold">{artifact?.progress || 20}%</span>
              </div>
              <div className="w-full bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                <div
                  className="bg-primary h-full transition-all duration-300 ease-out rounded-full"
                  style={{ width: `${Math.max(10, artifact?.progress || 20)}%` }}
                />
              </div>
            </div>
          )}

          {/* View Mode Switcher Dispatch */}
          {viewMode === 'transcript' && (
            <TranscriptView
              segments={transcriptSegments}
              loading={loadingTranscript}
              onSeek={(sec) => jumpToSource(activeMediaId, sec)}
              onStartRecording={handleToggleRecording}
            />
          )}

          {viewMode === 'editor' && (
            <div className="space-y-6">
              <ManualNotesEditor
                content={manualContent}
                onChange={setManualContent}
              />

              {/* Synthesized Notes Sections if available */}
              {activeNote && (
                <div className="pt-6 border-t border-outline-variant/30 space-y-6">
                  {/* Executive Summary & Action Items Header */}
                  <NoteSummaryHeader note={activeNote} />

                  {/* Sections List */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-xs font-mono uppercase tracking-wider text-on-surface-variant font-semibold">
                        Detailed Sections ({activeNote.sections?.length || 0})
                      </h3>
                      {notes.length > 1 && (
                        <div className="flex items-center gap-2 bg-surface-container-high px-2.5 py-1 rounded border border-outline-variant/40 text-xs font-mono">
                          <span className="text-on-surface-variant">Version:</span>
                          <select
                            value={selectedVersion || ''}
                            onChange={(e) => selectVersion(Number(e.target.value))}
                            className="bg-transparent text-primary outline-none cursor-pointer"
                          >
                            {notes.map((n) => (
                              <option key={n.id} value={n.version} className="bg-surface text-on-surface">
                                v{n.version}
                              </option>
                            ))}
                          </select>
                        </div>
                      )}
                    </div>

                    {activeNote.sections?.map((section, idx) => (
                      <NoteSectionCard
                        key={section.id || idx}
                        section={section}
                        index={idx}
                        onJumpToSource={jumpToSource}
                      />
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Floating Bottom AI Action Bar */}
        <NoteBottomBar
          isRecording={isRecording}
          recordingDuration={recordingDuration}
          audioLevel={audioLevel}
          isUploading={isUploading}
          onToggleRecording={handleToggleRecording}
          onGenerateNotes={handleGenerateNotes}
          generating={generating}
          promptValue={promptValue}
          onPromptChange={setPromptValue}
        />
      </main>
    </div>
  );
};
