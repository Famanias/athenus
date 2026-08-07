'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import { useVideo } from '@/features/video/useVideo';

export const TranscriptReader: React.FC = () => {
  const { setCurrentTime, setActiveView, activeMediaId } = useAppStore();
  const { segments, loading } = useVideo();
  const [autoScroll, setAutoScroll] = useState<boolean>(true);

  const handleTimestampClick = (timeStr: string) => {
    setCurrentTime(timeStr);
    setActiveView('view-video');
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Header Toolbar */}
      <div className="flex justify-between items-center pb-4 border-b border-outline-variant">
        <div>
          <h2 className="font-type-light text-2xl font-bold text-on-surface">
            Full Document Transcript Reader
          </h2>
          <p className="text-xs text-on-surface-variant mt-1">
            {activeMediaId ? `Media Asset: ${activeMediaId}` : 'Document Transcript'}
          </p>
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-2 text-xs font-mono text-on-surface-variant cursor-pointer">
            <input
              type="checkbox"
              checked={autoScroll}
              onChange={(e) => setAutoScroll(e.target.checked)}
              className="rounded accent-secondary"
            />
            Auto-Scroll
          </label>
          <Button variant="secondary" size="sm" icon="chat" onClick={() => setActiveView('view-chat')}>
            Ask AI Assistant
          </Button>
        </div>
      </div>

      {/* Paragraph Document Body */}
      {loading && (
        <div className="p-12 text-center text-xs text-on-surface-variant font-mono">
          Loading transcript segments...
        </div>
      )}

      {!loading && segments.length === 0 && (
        <div className="p-12 border border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-3">
          <span className="text-4xl block">📄</span>
          <h4 className="font-bold text-sm text-on-surface">No Document Transcript Found</h4>
          <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
            Upload a video or audio file to transcribe and view full lecture transcripts.
          </p>
          <Button variant="primary" icon="upload_file" onClick={() => setActiveView('view-ingestion')}>
            Upload Lecture
          </Button>
        </div>
      )}

      {!loading && segments.length > 0 && (
        <div className="p-8 bg-surface-container-low border border-outline-variant rounded space-y-6 text-xs leading-relaxed text-on-surface-variant">
          {segments.map((seg) => (
            <div key={seg.id} className="space-y-2">
              <span
                onClick={() => handleTimestampClick(seg.timestamp)}
                className="text-secondary font-mono font-semibold cursor-pointer hover:underline"
              >
                ⏱ {seg.timestamp}
              </span>
              <p className="text-on-surface-variant">{seg.text}</p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
