'use client';

import React, { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { useNotes, type NoteDTO, getNoteTranscript } from './useNotes';
import { useAudioRecorder } from './useAudioRecorder';
import { NoteTopToolbar, NoteViewMode } from './NoteTopToolbar';
import { NoteSummaryHeader } from './NoteSummaryHeader';
import { NoteSectionCard } from './NoteSectionCard';
import { TranscriptView, TranscriptSegmentDTO } from './TranscriptView';
import { ManualNotesEditor } from './ManualNotesEditor';
import { NoteBottomBar } from './NoteBottomBar';
import { getTranscript } from '@/services/mediaService';
import { useAppStore } from '@/store/useAppStore';

type PendingDeletion =
  | { kind: 'note'; id: string; name: string }
  | { kind: 'folder'; id: string; name: string; noteCount: number }
  | null;

const NoteTreeItem: React.FC<{
  note: NoteDTO;
  active: boolean;
  onSelect: () => void;
  onDelete: () => void;
}> = ({ note, active, onSelect, onDelete }) => (
  <div className={`group/note flex items-center rounded-md ${active ? 'bg-primary/10' : 'hover:bg-surface-container-high/60'}`}>
    <button
      type="button"
      onClick={onSelect}
      aria-current={active ? 'page' : undefined}
      className={`min-w-0 flex-1 min-h-9 flex items-center gap-2 rounded-md pl-8 pr-2 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 ${
        active ? 'text-primary font-semibold' : 'text-on-surface-variant hover:text-on-surface'
      }`}
    >
      <span className="material-symbols-outlined text-[15px] shrink-0" aria-hidden="true">description</span>
      <span className="truncate">{note.title || 'Untitled Note'}</span>
      {note.media_id && (
        <span className="ml-auto shrink-0 group-hover/note:hidden group-focus-within/note:hidden" title="Audio attached">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 block" aria-hidden="true" />
          <span className="sr-only">Audio attached</span>
        </span>
      )}
    </button>
    <button
      type="button"
      onClick={onDelete}
      aria-label={`Delete ${note.title || 'Untitled Note'}`}
      title="Delete note"
      className={`${active ? 'flex' : 'hidden group-hover/note:flex group-focus-within/note:flex'} w-9 h-9 shrink-0 items-center justify-center rounded text-on-surface-variant hover:bg-error/10 hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error/60`}
    >
      <span className="material-symbols-outlined text-[16px]" aria-hidden="true">delete</span>
    </button>
  </div>
);

export const NotesWorkspace: React.FC = () => {
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);

  const {
    folders,
    notes,
    activeNote,
    artifact,
    loading,
    generating,
    saving,
    error,
    toastMessage,
    createNote,
    selectNote,
    updateNote,
    deleteNote,
    createFolder,
    renameFolder,
    deleteFolder,
    attachAudio,
    transcribeAudioForNote,
    generateNotes,
  } = useNotes();

  const {
    isRecording,
    recordingDuration,
    audioLevel,
    isUploading,
    sourceMode,
    error: audioError,
    warning: audioWarning,
    setSourceMode,
    startRecording,
    stopRecording,
  } = useAudioRecorder();

  const [activeFolderId, setActiveFolderId] = useState<string | null>(null);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [unorganizedExpanded, setUnorganizedExpanded] = useState(true);
  const [addingFolder, setAddingFolder] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFolderId, setEditingFolderId] = useState<string | null>(null);
  const [editingFolderName, setEditingFolderName] = useState('');
  const [viewMode, setViewMode] = useState<NoteViewMode>('editor');
  const [noteTitle, setNoteTitle] = useState('Untitled Note');
  const [manualContent, setManualContent] = useState('');
  const [promptValue, setPromptValue] = useState('');
  const [transcriptSegments, setTranscriptSegments] = useState<TranscriptSegmentDTO[]>([]);
  const [loadingTranscript, setLoadingTranscript] = useState(false);
  const [pendingDeletion, setPendingDeletion] = useState<PendingDeletion>(null);
  const [deleting, setDeleting] = useState(false);
  const deleteDialogRef = useRef<HTMLDivElement>(null);
  const deleteTriggerRef = useRef<HTMLElement | null>(null);

  const closeDeletionDialog = () => {
    if (deleting) return;
    setPendingDeletion(null);
    window.setTimeout(() => deleteTriggerRef.current?.focus(), 0);
  };

  const unorganizedNotes = useMemo(
    () => notes.filter((note) => !note.folder_id),
    [notes]
  );

  useEffect(() => {
    setExpandedFolders((current) => {
      const next = new Set(current);
      folders.forEach((folder) => next.add(folder.id));
      return next;
    });
  }, [folders]);

  useEffect(() => {
    if (!pendingDeletion) return;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !deleting) {
        setPendingDeletion(null);
        window.setTimeout(() => deleteTriggerRef.current?.focus(), 0);
        return;
      }
      if (event.key !== 'Tab') return;
      const buttons = Array.from(
        deleteDialogRef.current?.querySelectorAll<HTMLButtonElement>('button:not([disabled])') || []
      );
      if (buttons.length === 0) return;
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [deleting, pendingDeletion]);

  useEffect(() => {
    if (activeNote) {
      setNoteTitle(activeNote.title || 'Untitled Note');
      setManualContent(activeNote.content || '');
      setActiveFolderId(activeNote.folder_id);
    } else {
      setNoteTitle('Untitled Note');
      setManualContent('');
    }
  }, [activeNote?.id, activeNote?.title, activeNote?.content, activeNote?.folder_id]);

  useEffect(() => {
    if (!activeNote) return;
    const content = activeNote.content || '';
    const title = noteTitle.trim() || 'Untitled Note';
    if (title === activeNote.title && manualContent === content) return;
    const timer = window.setTimeout(() => {
      updateNote({ title, content: manualContent }, activeNote.id);
    }, 650);
    return () => window.clearTimeout(timer);
  }, [activeNote, manualContent, noteTitle, updateNote]);

  useEffect(() => {
    let cancelled = false;
    async function loadTranscript() {
      if (!activeNote) {
        setTranscriptSegments([]);
        return;
      }
      setLoadingTranscript(true);
      try {
        if (activeNote.id) {
          const res = await getNoteTranscript(activeNote.id);
          if (!cancelled && res?.segments?.length) {
            setTranscriptSegments(res.segments);
            return;
          }
        }
        if (activeNote.media_id) {
          const transcript = await getTranscript(activeNote.media_id, activeWorkspaceId || undefined);
          if (!cancelled) setTranscriptSegments(transcript?.segments || []);
        } else {
          if (!cancelled) setTranscriptSegments([]);
        }
      } catch {
        if (!cancelled) setTranscriptSegments([]);
      } finally {
        if (!cancelled) setLoadingTranscript(false);
      }
    }
    loadTranscript();
    return () => { cancelled = true; };
  }, [activeNote?.id, activeNote?.media_id, activeWorkspaceId]);

  const handleNewNote = async () => {
    await createNote(activeFolderId);
    setViewMode('editor');
  };

  const handleSelectNote = async (note: NoteDTO) => {
    setActiveFolderId(note.folder_id);
    await selectNote(note.id);
  };

  const handleCreateFolder = async (event: FormEvent) => {
    event.preventDefault();
    const name = newFolderName.trim();
    if (!name) return;
    const folder = await createFolder(name);
    if (folder) {
      setActiveFolderId(folder.id);
      setExpandedFolders((current) => new Set(current).add(folder.id));
      setNewFolderName('');
      setAddingFolder(false);
    }
  };

  const handleMobileCreateFolder = async () => {
    const name = window.prompt('Folder name')?.trim();
    if (!name) return;
    const folder = await createFolder(name);
    if (folder) setActiveFolderId(folder.id);
  };

  const handleRenameFolder = async (folderId: string) => {
    const name = editingFolderName.trim();
    if (!name) return;
    if (await renameFolder(folderId, name)) setEditingFolderId(null);
  };

  const requestFolderDeletion = (folderId: string, folderName: string, noteCount: number) => {
    deleteTriggerRef.current = document.activeElement as HTMLElement | null;
    setPendingDeletion({ kind: 'folder', id: folderId, name: folderName, noteCount });
  };

  const requestNoteDeletion = (note: NoteDTO) => {
    deleteTriggerRef.current = document.activeElement as HTMLElement | null;
    setPendingDeletion({ kind: 'note', id: note.id, name: note.title || 'Untitled Note' });
  };

  const confirmDeletion = async () => {
    if (!pendingDeletion || deleting) return;
    setDeleting(true);
    try {
      const deleted = pendingDeletion.kind === 'folder'
        ? await deleteFolder(pendingDeletion.id)
        : await deleteNote(pendingDeletion.id);
      if (deleted) {
        if (pendingDeletion.kind === 'folder') setActiveFolderId(null);
        setPendingDeletion(null);
      }
    } finally {
      setDeleting(false);
    }
  };

  const handleToggleRecording = async () => {
    if (!isRecording) {
      let target = activeNote;
      if (!target) target = await createNote(activeFolderId);
      if (!target) return;
      if (await startRecording()) setViewMode('transcript');
      return;
    }

    const blob = await stopRecording();
    if (!blob || !activeNote) return;
    setLoadingTranscript(true);
    setViewMode('transcript');
    try {
      const res = await transcribeAudioForNote(activeNote.id, blob);
      if (res?.segments) {
        setTranscriptSegments(res.segments);
      }
    } finally {
      setLoadingTranscript(false);
    }
  };

  const handleGenerateNotes = async () => {
    let target = activeNote;
    if (!target) target = await createNote(activeFolderId);
    if (!target) return;
    const generated = await generateNotes(promptValue.trim() || undefined, target.id);
    if (generated) setViewMode('editor');
  };

  const toggleFolder = (folderId: string) => {
    setActiveFolderId(folderId);
    setExpandedFolders((current) => {
      const next = new Set(current);
      if (next.has(folderId)) next.delete(folderId);
      else next.add(folderId);
      return next;
    });
  };

  return (
    <div className="flex h-full w-full overflow-hidden bg-background">
      <aside className="hidden md:flex w-64 border-r border-outline-variant/30 bg-surface-container-lowest/70 flex-col shrink-0 select-none">
        <div className="p-3 border-b border-outline-variant/20 space-y-2">
          <button
            type="button"
            onClick={handleNewNote}
            className="w-full min-h-11 flex items-center gap-2 px-3 rounded-lg bg-surface-container-high/80 hover:bg-surface-container-highest text-on-surface text-xs font-semibold transition-colors border border-outline-variant/30 shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70"
          >
            <span className="material-symbols-outlined text-[17px] text-primary" aria-hidden="true">edit_square</span>
            <span>New note</span>
            <span className="ml-auto text-[10px] text-on-surface-variant">in selected folder</span>
          </button>
          <div className="flex items-center justify-between px-1 pt-2">
            <span className="text-[11px] font-mono uppercase tracking-wider text-on-surface-variant">Folders</span>
            <button
              type="button"
              onClick={() => setAddingFolder(true)}
              aria-label="Create folder"
              title="Create folder"
              className="min-w-10 min-h-10 rounded-md text-on-surface-variant hover:text-primary hover:bg-primary/10 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70"
            >
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">create_new_folder</span>
            </button>
          </div>
          {addingFolder && (
            <form onSubmit={handleCreateFolder} className="flex gap-1" role="form" aria-label="Create folder">
              <label htmlFor="new-note-folder" className="sr-only">Folder name</label>
              <input
                id="new-note-folder"
                autoFocus
                value={newFolderName}
                onChange={(event) => setNewFolderName(event.target.value)}
                onBlur={() => { if (!newFolderName.trim()) setAddingFolder(false); }}
                placeholder="Folder name"
                className="min-w-0 flex-1 h-9 rounded-md border border-outline-variant/50 bg-surface-container-high px-2 text-xs text-on-surface outline-none focus:ring-2 focus:ring-primary/60"
              />
              <button type="submit" aria-label="Save folder" className="w-9 h-9 rounded-md bg-primary/10 text-primary hover:bg-primary/20">
                <span className="material-symbols-outlined text-[17px]" aria-hidden="true">check</span>
              </button>
            </form>
          )}
        </div>

        <nav className="flex-1 overflow-y-auto custom-scrollbar p-2" aria-label="Note folders">
          <div className="space-y-1">
            <button
              type="button"
              onClick={() => { setActiveFolderId(null); setUnorganizedExpanded((value) => !value); }}
              aria-expanded={unorganizedExpanded}
              className={`w-full min-h-10 flex items-center gap-2 rounded-md px-2 text-xs font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 ${
                activeFolderId === null ? 'bg-primary/10 text-primary' : 'text-on-surface-variant hover:bg-surface-container-high/60'
              }`}
            >
              <span className="material-symbols-outlined text-[16px]" aria-hidden="true">
                {unorganizedExpanded ? 'expand_more' : 'chevron_right'}
              </span>
              <span className="material-symbols-outlined text-[16px]" aria-hidden="true">folder_off</span>
              <span className="truncate">Unorganized Notes</span>
              <span className="ml-auto font-mono text-[10px]">{unorganizedNotes.length}</span>
            </button>
            {unorganizedExpanded && unorganizedNotes.map((note) => (
              <NoteTreeItem
                key={note.id}
                note={note}
                active={activeNote?.id === note.id}
                onSelect={() => handleSelectNote(note)}
                onDelete={() => requestNoteDeletion(note)}
              />
            ))}

            {folders.map((folder) => {
              const expanded = expandedFolders.has(folder.id);
              const folderNotes = notes.filter((note) => note.folder_id === folder.id);
              return (
                <div key={folder.id} className="group/folder">
                  <div className={`flex items-center rounded-md ${activeFolderId === folder.id ? 'bg-primary/10' : 'hover:bg-surface-container-high/60'}`}>
                    {editingFolderId === folder.id ? (
                      <form
                        className="flex-1 flex gap-1 p-1"
                        onSubmit={(event) => { event.preventDefault(); handleRenameFolder(folder.id); }}
                      >
                        <label htmlFor={`folder-${folder.id}`} className="sr-only">Rename folder</label>
                        <input
                          id={`folder-${folder.id}`}
                          autoFocus
                          value={editingFolderName}
                          onChange={(event) => setEditingFolderName(event.target.value)}
                          className="min-w-0 flex-1 h-8 rounded border border-outline-variant/50 bg-surface px-2 text-xs outline-none focus:ring-2 focus:ring-primary/60"
                        />
                        <button type="submit" aria-label="Save folder name" className="w-8 h-8 text-primary">
                          <span className="material-symbols-outlined text-[16px]" aria-hidden="true">check</span>
                        </button>
                      </form>
                    ) : (
                      <>
                        <button
                          type="button"
                          onClick={() => toggleFolder(folder.id)}
                          aria-expanded={expanded}
                          className={`min-w-0 flex-1 min-h-10 flex items-center gap-2 px-2 text-xs font-medium text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 rounded-md ${activeFolderId === folder.id ? 'text-primary' : 'text-on-surface-variant'}`}
                        >
                          <span className="material-symbols-outlined text-[16px]" aria-hidden="true">{expanded ? 'expand_more' : 'chevron_right'}</span>
                          <span className="material-symbols-outlined text-[16px]" aria-hidden="true">folder</span>
                          <span className="truncate">{folder.name}</span>
                          <span className="ml-auto font-mono text-[10px] group-hover/folder:hidden">{folder.note_count}</span>
                        </button>
                        <div className="hidden group-hover/folder:flex group-focus-within/folder:flex items-center pr-1">
                          <button
                            type="button"
                            onClick={() => { setEditingFolderId(folder.id); setEditingFolderName(folder.name); }}
                            aria-label={`Rename ${folder.name}`}
                            title="Rename folder"
                            className="w-9 h-9 rounded text-on-surface-variant hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70"
                          >
                            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">edit</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => requestFolderDeletion(folder.id, folder.name, folder.note_count)}
                            aria-label={`Delete ${folder.name}`}
                            title="Delete folder"
                            className="w-9 h-9 rounded text-on-surface-variant hover:text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error/60"
                          >
                            <span className="material-symbols-outlined text-[16px]" aria-hidden="true">delete</span>
                          </button>
                        </div>
                      </>
                    )}
                  </div>
                  {expanded && folderNotes.map((note) => (
                    <NoteTreeItem
                      key={note.id}
                      note={note}
                      active={activeNote?.id === note.id}
                      onSelect={() => handleSelectNote(note)}
                      onDelete={() => requestNoteDeletion(note)}
                    />
                  ))}
                </div>
              );
            })}
          </div>
        </nav>
      </aside>

      <main className="flex-1 flex flex-col h-full min-w-0 overflow-hidden relative">
        <div className="w-full shrink-0 border-b border-outline-variant/30 bg-background/50 backdrop-blur-xs">
          <div className="md:hidden flex items-center gap-2 px-4 pt-3">
            <label htmlFor="mobile-note-select" className="sr-only">Selected note</label>
            <select
              id="mobile-note-select"
              value={activeNote?.id || ''}
              onChange={(event) => {
                const note = notes.find((item) => item.id === event.target.value);
                if (note) void handleSelectNote(note);
              }}
              className="min-w-0 flex-1 h-10 rounded-md border border-outline-variant/40 bg-surface-container-high px-2 text-xs text-on-surface outline-none focus:ring-2 focus:ring-primary/60"
            >
              <option value="" disabled>Select a note</option>
              {notes.map((note) => <option key={note.id} value={note.id}>{note.title}</option>)}
            </select>
            <button
              type="button"
              onClick={() => activeNote && requestNoteDeletion(activeNote)}
              disabled={!activeNote}
              aria-label="Delete selected note"
              title="Delete selected note"
              className="w-11 h-11 rounded-md text-on-surface-variant hover:bg-error/10 hover:text-error disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error/60"
            >
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">delete</span>
            </button>
            <button type="button" onClick={handleNewNote} aria-label="Create note" title="Create note" className="w-11 h-11 rounded-md bg-primary/10 text-primary hover:bg-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70">
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">note_add</span>
            </button>
            <button type="button" onClick={handleMobileCreateFolder} aria-label="Create folder" title="Create folder" className="w-11 h-11 rounded-md bg-surface-container-high text-on-surface-variant hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70">
              <span className="material-symbols-outlined text-[18px]" aria-hidden="true">create_new_folder</span>
            </button>
          </div>
          <div className="max-w-4xl mx-auto w-full px-6 md:px-12 py-4">
            <NoteTopToolbar
              title={noteTitle}
              onTitleChange={setNoteTitle}
              viewMode={viewMode}
              onViewModeChange={setViewMode}
              hasTranscript={transcriptSegments.length > 0}
              saving={saving}
              disabled={!activeNote}
            />
          </div>
        </div>

        <div className="flex-1 overflow-y-auto custom-scrollbar pb-32">
          <div className="max-w-4xl mx-auto w-full px-6 md:px-12 py-6 space-y-6">
            {(error || audioError) && (
              <div role="alert" className="px-4 py-3 bg-error/10 border border-error/30 rounded-lg text-error text-xs flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] shrink-0">error</span>
                <span>{error || audioError}</span>
              </div>
            )}
            {audioWarning && (
              <div role="status" aria-live="polite" className="px-4 py-2.5 bg-amber-500/10 border border-amber-500/30 rounded-lg text-amber-300 font-mono text-xs flex items-center gap-2">
                <span className="material-symbols-outlined text-[16px] shrink-0 text-amber-400">warning</span>
                <span>{audioWarning}</span>
              </div>
            )}
            {toastMessage && (
              <div role="status" aria-live="polite" className="px-4 py-2 bg-emerald-500/10 border border-emerald-500/30 rounded-lg text-emerald-400 font-mono text-xs font-semibold flex items-center justify-between">
                <span>{toastMessage}</span>
                <span className="text-[10px] text-emerald-400/60 uppercase tracking-wider">Synced</span>
              </div>
            )}

            {(generating || artifact?.status === 'generating') && (
              <div className="p-4 bg-surface-container-high/60 border border-primary/20 rounded-xl space-y-2" role="status" aria-live="polite">
                <div className="flex items-center justify-between text-xs font-mono">
                  <span className="text-primary font-semibold flex items-center gap-2">
                    <span className="inline-block w-2 h-2 rounded-full bg-primary animate-ping motion-reduce:animate-none" aria-hidden="true" />
                    {artifact?.message || 'Synthesizing study notes...'}
                  </span>
                  <span className="text-on-surface-variant font-bold">{artifact?.progress || 20}%</span>
                </div>
                <div className="w-full bg-surface-container-highest rounded-full h-1.5 overflow-hidden">
                  <div className="bg-primary h-full transition-all duration-300 ease-out rounded-full" style={{ width: `${Math.max(10, artifact?.progress || 20)}%` }} />
                </div>
              </div>
            )}

            {loading ? (
              <div className="py-24 text-center text-on-surface-variant text-sm">Loading notes…</div>
            ) : !activeNote ? (
              <div className="py-24 px-6 text-center border border-dashed border-outline-variant rounded-2xl bg-surface-container-low/40 max-w-lg mx-auto">
                <span className="material-symbols-outlined text-4xl text-primary" aria-hidden="true">note_add</span>
                <h2 className="mt-3 text-lg font-semibold text-on-surface">Create your first note</h2>
                <p className="mt-2 text-sm text-on-surface-variant">Choose a folder in the sidebar, then create a note for writing, recording, and AI synthesis.</p>
                <button type="button" onClick={handleNewNote} className="mt-5 min-h-11 px-5 rounded-lg bg-primary text-on-primary text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70 focus-visible:ring-offset-2">
                  New note
                </button>
              </div>
            ) : viewMode === 'transcript' ? (
              <TranscriptView
                segments={transcriptSegments}
                loading={loadingTranscript}
                onStartRecording={handleToggleRecording}
              />
            ) : (
              <div className="space-y-6">
                <ManualNotesEditor content={manualContent} onChange={setManualContent} />
                {(activeNote.summary || activeNote.action_items.length > 0 || activeNote.sections.length > 0) && (
                  <div className="pt-6 border-t border-outline-variant/30 space-y-6">
                    <NoteSummaryHeader note={activeNote} />
                    <div className="space-y-4">
                      <h3 className="text-xs font-mono uppercase tracking-wider text-on-surface-variant font-semibold">
                        Detailed Sections ({activeNote.sections.length})
                      </h3>
                      {activeNote.sections.map((section, index) => (
                        <NoteSectionCard key={section.id || index} section={section} index={index} />
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="absolute bottom-4 left-0 right-0 z-20 flex justify-center pointer-events-none px-4">
          <div className="max-w-4xl w-full pointer-events-auto px-4 md:px-8">
            <NoteBottomBar
              isRecording={isRecording}
              recordingDuration={recordingDuration}
              audioLevel={audioLevel}
              isUploading={isUploading}
              sourceMode={sourceMode}
              onSourceModeChange={setSourceMode}
              onToggleRecording={handleToggleRecording}
              onGenerateNotes={handleGenerateNotes}
              generating={generating}
              promptValue={promptValue}
              onPromptChange={setPromptValue}
            />
          </div>
        </div>
      </main>

      {pendingDeletion && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) closeDeletionDialog();
          }}
        >
          <div
            ref={deleteDialogRef}
            role="alertdialog"
            aria-modal="true"
            aria-labelledby="delete-dialog-title"
            aria-describedby="delete-dialog-description"
            className="w-full max-w-md rounded-2xl border border-error/30 bg-surface-container-high p-6 shadow-2xl"
          >
            <div className="flex items-start gap-4">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-error/10 text-error">
                <span className="material-symbols-outlined text-[24px]" aria-hidden="true">warning</span>
              </div>
              <div className="min-w-0">
                <h2 id="delete-dialog-title" className="text-lg font-bold text-on-surface">
                  Delete {pendingDeletion.kind}?
                </h2>
                <p id="delete-dialog-description" className="mt-2 text-sm leading-relaxed text-on-surface-variant">
                  {pendingDeletion.kind === 'folder' ? (
                    <>
                      This will permanently delete <strong className="text-on-surface">“{pendingDeletion.name}”</strong>
                      {pendingDeletion.noteCount === 0 ? (
                        <>. The folder is currently empty.</>
                      ) : (
                        <>
                          {' '}and {pendingDeletion.noteCount === 1 ? 'the note' : `all ${pendingDeletion.noteCount} notes`} inside it,
                          including their manual content and AI-generated sections.
                        </>
                      )}
                    </>
                  ) : (
                    <>
                      This will permanently delete <strong className="text-on-surface">“{pendingDeletion.name}”</strong>,
                      including its manual content and AI-generated sections.
                    </>
                  )}
                </p>
                <p className="mt-3 text-sm font-semibold text-error">This action cannot be undone.</p>
              </div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button
                type="button"
                autoFocus
                disabled={deleting}
                onClick={closeDeletionDialog}
                className="min-h-11 rounded-lg border border-outline-variant/50 px-4 text-sm font-semibold text-on-surface hover:bg-surface-container-highest disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70"
              >
                Cancel
              </button>
              <button
                type="button"
                disabled={deleting}
                onClick={confirmDeletion}
                className="min-h-11 min-w-28 rounded-lg bg-error px-4 text-sm font-bold text-on-error hover:brightness-110 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-error focus-visible:ring-offset-2 focus-visible:ring-offset-surface-container-high"
              >
                {deleting ? 'Deleting…' : `Delete ${pendingDeletion.kind}`}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
