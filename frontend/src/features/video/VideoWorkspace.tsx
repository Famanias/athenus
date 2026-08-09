'use client';

import React, { useState, useEffect, useRef } from 'react';
import { PersistentMediaPlayer } from './PersistentMediaPlayer';
import { DocumentViewer } from '@/components/DocumentViewer';
import { useVideo } from './useVideo';
import { EmbeddedChatWidget } from './EmbeddedChatWidget';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import { useLibrary } from '@/features/library/useLibrary';

export const VideoWorkspace: React.FC = () => {
  const {
    currentTime,
    segments,
    activeSegmentIndex,
    mediaSrc,
    videoRef,
    seekToSeconds,
    togglePlayPause,
    togglePictureInPicture,
    isPlaying,
    setIsPlaying,
    isPipActive,
    loading,
    playbackSpeed,
    changePlaybackSpeed,
    handleLoadedMetadata,
    handleTimeUpdate,
  } = useVideo();

  const { activeMediaId, activeDocumentId, activeSourceType, setActiveView } = useAppStore();

  // Workspace asset inventory — drives the empty state when no videos remain.
  const { assets: workspaceAssets, loading: assetsLoading } = useLibrary();
  const hasNoVideos = !assetsLoading && workspaceAssets.length === 0;

  // Active right panel tab ('transcript' | 'chat')
  const [activeRightTab, setActiveRightTab] = useState<'transcript' | 'chat'>('transcript');
  const [selectedTranscriptText, setSelectedTranscriptText] = useState<string>('');

  // Layout states (width & collapse)
  const [transcriptWidth, setTranscriptWidth] = useState<number>(380);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);

  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [searchFilter, setSearchFilter] = useState<string>('');
  const [userScrolled, setUserScrolled] = useState<boolean>(false);
  const [copySuccess, setCopySuccess] = useState<boolean>(false);

  // Gate hydration-dependent UI (localStorage-driven state) behind a mounted flag
  // so the server render matches the first client render.
  const [mounted, setMounted] = useState<boolean>(false);
  useEffect(() => {
    setMounted(true);
  }, []);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const scrollContainerRef = useRef<HTMLDivElement | null>(null);
  const segmentRefs = useRef<{ [key: number]: HTMLDivElement | null }>({});

  // Load persisted layout state on mount (client-side only)
  useEffect(() => {
    const savedWidth = localStorage.getItem('athenus_transcript_width');
    if (savedWidth) setTranscriptWidth(parseInt(savedWidth, 10));
    if (localStorage.getItem('athenus_transcript_collapsed') === 'true') setIsCollapsed(true);
  }, []);

  // Persist transcript width & collapse state
  useEffect(() => {
    localStorage.setItem('athenus_transcript_width', transcriptWidth.toString());
  }, [transcriptWidth]);

  useEffect(() => {
    localStorage.setItem('athenus_transcript_collapsed', isCollapsed.toString());
  }, [isCollapsed]);

  // Handle panel resizing via mouse drag
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isDragging || !containerRef.current) return;
      const containerRect = containerRef.current.getBoundingClientRect();
      const newWidth = containerRect.right - e.clientX;
      if (newWidth >= 260 && newWidth <= 650) {
        setTranscriptWidth(newWidth);
      }
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging]);

  // Auto-scroll transcript panel to active segment unless user scrolled manually
  useEffect(() => {
    if (activeRightTab === 'transcript' && !userScrolled && activeSegmentIndex >= 0 && segmentRefs.current[activeSegmentIndex]) {
      segmentRefs.current[activeSegmentIndex]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [activeSegmentIndex, userScrolled, activeRightTab]);

  // Detect manual user scrolling inside transcript container
  const handleTranscriptScroll = () => {
    if (!scrollContainerRef.current) return;
    setUserScrolled(true);
  };

  const handleResumeAutoScroll = () => {
    setUserScrolled(false);
    if (activeSegmentIndex >= 0 && segmentRefs.current[activeSegmentIndex]) {
      segmentRefs.current[activeSegmentIndex]?.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  };

  // Keyboard controls listener
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const targetTag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (targetTag === 'input' || targetTag === 'textarea' || targetTag === 'select') {
        return;
      }

      if (!videoRef.current) return;

      if (e.code === 'Space') {
        e.preventDefault();
        togglePlayPause();
      } else if (e.code === 'ArrowLeft') {
        e.preventDefault();
        videoRef.current.currentTime = Math.max(0, videoRef.current.currentTime - 5);
      } else if (e.code === 'ArrowRight') {
        e.preventDefault();
        videoRef.current.currentTime = Math.min(videoRef.current.duration || 0, videoRef.current.currentTime + 5);
      } else if (e.code === 'KeyM') {
        e.preventDefault();
        videoRef.current.muted = !videoRef.current.muted;
      } else if (e.code === 'KeyF') {
        e.preventDefault();
        if (document.fullscreenElement) {
          document.exitFullscreen().catch(() => { });
        } else {
          videoRef.current.requestFullscreen().catch(() => { });
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [togglePlayPause, videoRef]);

  // Copy full transcript text
  const handleCopyTranscript = () => {
    if (segments.length === 0) return;
    const fullText = segments
      .map((s) => `[${s.timestamp}] ${s.speaker}: ${s.text}`)
      .join('\n');
    navigator.clipboard.writeText(fullText);
    setCopySuccess(true);
    setTimeout(() => setCopySuccess(false), 2000);
  };

  const handleAskAboutSegment = (segmentText: string, startSecs: number) => {
    seekToSeconds(startSecs);
    setSelectedTranscriptText(segmentText);
    setActiveRightTab('chat');
  };

  // Current video playback seconds
  const currentVideoSeconds = videoRef.current?.currentTime || 0;

  // Empty state when no media asset is selected or none exists in the workspace.
  // `mounted` ensures server & first client render agree before reading
  // hydration-dependent state like activeMediaId.
  if (mounted && !loading && !activeMediaId && !activeDocumentId && segments.length === 0) {
    return (
      <div className="flex-1 p-12 flex flex-col items-center justify-center text-center space-y-4 bg-surface-container-lowest">
        <span className="text-5xl">{activeSourceType === 'pdf' ? '📄' : '🎬'}</span>
        <h3 className="font-type-light text-xl font-bold text-on-surface">
          {activeSourceType === 'pdf' ? 'No Document Selected' : 'No Video Selected'}
        </h3>
        <p className="text-xs text-on-surface-variant max-w-md leading-relaxed">
          {activeSourceType === 'pdf'
            ? 'Please upload a PDF or document in Pipelines or select an existing document asset from the Workspace Library.'
            : 'Please upload a lecture video in Pipelines or select an existing asset from the Workspace Library.'}
        </p>
        <div className="flex gap-3 pt-2">
          <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
            {activeSourceType === 'pdf' ? 'Upload Document' : 'Upload Video'}
          </Button>
          <Button variant="secondary" icon="grid_view" onClick={() => setActiveView('view-dashboard')}>
            Browse Library
          </Button>
        </div>
      </div>
    );
  }

  const filteredSegments = segments.filter((s) =>
    s.text.toLowerCase().includes(searchFilter.toLowerCase()) ||
    s.timestamp.includes(searchFilter)
  );

  return (
    <div ref={containerRef} className="flex-1 flex overflow-hidden w-full h-full relative">
      {/* Primary Player Area (Video Player or Document Viewer) */}
      <div className="flex-1 bg-black flex flex-col border-r border-outline-variant min-w-0">
        <div className="flex-1 bg-surface-container-lowest flex flex-col items-stretch justify-stretch p-0 relative overflow-hidden">
          {activeSourceType === 'pdf' ? (
            <div className="w-full h-full">
              <DocumentViewer />
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                src={mediaSrc || undefined}
                controls
                onPlay={() => setIsPlaying(true)}
                onPause={() => setIsPlaying(false)}
                onLoadedMetadata={handleLoadedMetadata}
                onTimeUpdate={handleTimeUpdate}
                className="w-full h-full object-contain rounded border border-outline-variant shadow-lg"
              />
            </>
          )}
        </div>

        {/* Control Bar */}
        <div className="p-3 bg-surface-container-low border-t border-outline-variant flex flex-wrap justify-between items-center text-xs gap-3 shrink-0">
          <div className="flex items-center gap-3">
            {activeSourceType === 'pdf' ? (
              <h3 className="font-bold text-on-surface text-xs truncate max-w-xs">
                {activeDocumentId ? `Document: ${activeDocumentId}` : 'Indexed Document'}
              </h3>
            ) : workspaceAssets.length > 0 ? (
              <select
                value={activeMediaId || ''}
                onChange={(e) => useAppStore.setState({ activeMediaId: e.target.value || null })}
                className="bg-surface-container border border-outline-variant rounded px-2.5 py-1 text-xs font-mono text-on-surface focus:border-secondary outline-none max-w-xs"
              >
                <option value="" disabled>-- Select Workspace Video --</option>
                {workspaceAssets.map((asset) => (
                  <option key={asset.id} value={asset.id}>
                    🎥 {asset.title || asset.id}
                  </option>
                ))}
              </select>
            ) : (
              <h3 className="font-bold text-on-surface text-xs truncate max-w-xs">
                {activeMediaId ? `Media Asset: ${activeMediaId}` : 'Indexed Lecture Video'}
              </h3>
            )}
            {activeSourceType !== 'pdf' && (
              <span className="font-mono text-secondary text-[11px]">
                Time: {currentTime}
              </span>
            )}
          </div>

          {/* Right Panel Tab Switcher & Tools */}
          <div className="flex items-center gap-3">
            <div className="flex bg-surface-container border border-outline-variant rounded p-0.5 font-mono text-[11px]">
              <button
                onClick={() => {
                  setActiveRightTab('transcript');
                  if (isCollapsed) setIsCollapsed(false);
                }}
                className={`px-2.5 py-1 rounded transition-colors ${activeRightTab === 'transcript' && !isCollapsed
                  ? 'bg-secondary text-on-secondary font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
                  }`}
              >
                📝 Transcript
              </button>
              <button
                onClick={() => {
                  setActiveRightTab('chat');
                  if (isCollapsed) setIsCollapsed(false);
                }}
                className={`px-2.5 py-1 rounded transition-colors ${activeRightTab === 'chat' && !isCollapsed
                  ? 'bg-secondary text-on-secondary font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
                  }`}
              >
                💬 AI Assistant
              </button>
            </div>

            {/* Panel Collapse Toggle */}
            <button
              onClick={() => setIsCollapsed(!isCollapsed)}
              title={isCollapsed ? 'Expand Side Panel' : 'Collapse Side Panel'}
              className="p-1.5 rounded bg-surface-container border border-outline-variant text-on-surface-variant hover:text-on-surface text-xs font-mono"
            >
              {isCollapsed ? '◀ Panel' : '▶ Hide'}
            </button>
          </div>
        </div>
      </div>

      {/* Draggable Resize Handle — hidden in document mode (viewer has its own controls) */}
      {!isCollapsed && activeSourceType !== 'pdf' && (
        <div
          onMouseDown={() => setIsDragging(true)}
          className={`w-1.5 bg-outline-variant/30 hover:bg-secondary cursor-col-resize transition-colors z-10 shrink-0 ${isDragging ? 'bg-secondary' : ''
            }`}
        />
      )}

      {/* Side Panel (Transcript Sync or Embedded AI Chat Widget) — hidden in document mode */}
      {!isCollapsed && activeSourceType !== 'pdf' && (
        <div
          style={{ width: `${transcriptWidth}px` }}
          className="flex flex-col bg-surface-container-lowest shrink-0 min-w-[260px] max-w-[650px] h-full overflow-hidden"
        >
          {activeRightTab === 'chat' ? (
            <EmbeddedChatWidget
              currentTimestampSeconds={currentVideoSeconds}
              selectedTranscriptText={selectedTranscriptText}
              onClearSelectedText={() => setSelectedTranscriptText('')}
            />
          ) : (
            <div className="flex flex-col h-full overflow-hidden">
              {/* Transcript Panel Header & Search Filter */}
              <div className="p-3 border-b border-outline-variant bg-surface-container-low space-y-2 shrink-0">
                <div className="flex justify-between items-center">
                  <span className="font-mono text-xs font-bold text-secondary uppercase tracking-wider flex items-center gap-1.5">
                    <span>📝</span> Transcript Sync
                  </span>
                  <button
                    onClick={handleCopyTranscript}
                    className="text-[10px] text-on-surface-variant hover:text-secondary font-mono flex items-center gap-1"
                  >
                    {copySuccess ? '✓ Copied' : '📋 Copy Text'}
                  </button>
                </div>

                {/* Filter Input */}
                <input
                  type="text"
                  placeholder="Search transcript text or 01:15..."
                  value={searchFilter}
                  onChange={(e) => setSearchFilter(e.target.value)}
                  className="w-full bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface focus:border-secondary focus:outline-none font-mono"
                />
              </div>

              {/* Transcript List Scroll Area */}
              <div
                ref={scrollContainerRef}
                onScroll={handleTranscriptScroll}
                className="flex-1 overflow-y-auto p-4 space-y-3 custom-scrollbar text-xs leading-relaxed relative"
              >
                {loading && (
                  <div className="p-8 text-center text-xs text-on-surface-variant font-mono">
                    Loading transcript...
                  </div>
                )}

                {!loading && segments.length === 0 && (
                  <div className="p-6 border border-dashed border-outline-variant rounded bg-surface-container-low text-center space-y-2">
                    <span className="text-xl block">📄</span>
                    <p className="text-xs text-on-surface-variant">No transcript segments available for this asset.</p>
                  </div>
                )}

                {!loading && filteredSegments.map((seg) => {
                  const originalIndex = segments.findIndex((s) => s.id === seg.id);
                  const isActive = originalIndex === activeSegmentIndex;

                  return (
                    <div
                      key={seg.id}
                      ref={(el) => {
                        if (originalIndex >= 0) segmentRefs.current[originalIndex] = el;
                      }}
                      onClick={() => seekToSeconds(seg.start_seconds)}
                      className={`p-3 rounded border transition-all cursor-pointer ${isActive
                        ? 'bg-secondary/15 border-l-4 border-secondary border-secondary/40 text-on-surface shadow-md scale-[1.01]'
                        : 'bg-surface-container-low/60 border-outline-variant/30 hover:bg-surface-container hover:border-secondary/40 text-on-surface-variant'
                        }`}
                    >
                      <div className="flex justify-between items-center mb-1">
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            seekToSeconds(seg.start_seconds);
                          }}
                          className={`font-mono text-[11px] font-bold hover:underline ${isActive ? 'text-secondary' : 'text-on-surface-variant'}`}
                        >
                          ⏱ {seg.timestamp}
                        </button>
                        <div className="flex items-center gap-2">
                          <span className="text-[10px] font-mono text-on-surface-variant/60">
                            {seg.speaker}
                          </span>
                          {/* <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleAskAboutSegment(seg.text, seg.start_seconds);
                            }}
                            title="Ask AI about this segment"
                            className="px-1.5 py-0.5 rounded bg-surface-container hover:bg-secondary/20 hover:text-secondary text-[10px] font-mono text-on-surface-variant transition-colors"
                          >
                            Ask AI
                          </button> */}
                        </div>
                      </div>
                      <p className="text-xs leading-relaxed select-text">{seg.text}</p>
                    </div>
                  );
                })}
              </div>

              {/* Floating Resume Auto-Scroll Button */}
              {userScrolled && (
                <div className="p-2 bg-surface-container-low border-t border-outline-variant flex justify-center shrink-0">
                  <button
                    onClick={handleResumeAutoScroll}
                    className="px-3 py-1 bg-secondary text-on-secondary text-xs font-bold rounded-full shadow-lg hover:brightness-110 flex items-center gap-1"
                  >
                    ↓ Resume Auto-Scroll
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
};
