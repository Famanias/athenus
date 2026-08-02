'use client';

import React from 'react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { TopToolbar } from '@/components/navigation/TopToolbar';
import { StatusBar } from '@/components/layout/StatusBar';
import { MainPanel } from '@/components/layout/MainPanel';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import { useAppStore } from '@/store/useAppStore';

// Phase B Feature Components
import { LibraryGrid } from '@/features/library/LibraryGrid';
import { VideoWorkspace } from '@/features/video/VideoWorkspace';
import { TranscriptReader } from '@/features/transcript/TranscriptReader';

const ChatViewPlaceholder = () => (
  <div className="flex-1 p-8 overflow-y-auto custom-scrollbar space-y-4">
    <div className="flex items-center gap-3">
      <span className="text-3xl">🦉</span>
      <div>
        <h2 className="font-carvist text-xl font-bold text-on-surface">AI Research Assistant Workspace</h2>
        <p className="text-xs text-on-surface-variant">Phase A & B active. 8-Stage RAG Chat component loading in Phase C.</p>
      </div>
    </div>
    <div className="p-6 bg-surface-container-low border border-outline-variant rounded space-y-2 text-xs">
      <span className="font-mono text-secondary font-semibold">STATUS: PHASE B VERIFIED</span>
      <p className="text-on-surface-variant">LibraryGrid, VideoWorkspace with synced timestamp seeking, and TranscriptReader features active.</p>
    </div>
  </div>
);

export const DesktopShell: React.FC = () => {
  const { activeView } = useAppStore();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Categorized Navigation Sidebar */}
      <Sidebar />

      {/* Workspace Area */}
      <main className="ml-sidebar-width flex-1 flex flex-col h-screen relative bg-background">
        {/* Top App Bar */}
        <TopToolbar />

        {/* Dynamic View Canvas */}
        <MainPanel>
          {activeView === 'view-dashboard' && <LibraryGrid />}
          {activeView === 'view-video' && <VideoWorkspace />}
          {activeView === 'view-transcript' && <TranscriptReader />}
          {activeView === 'view-chat' && <ChatViewPlaceholder />}
          
          {/* Default fallback for future phases */}
          {!['view-dashboard', 'view-video', 'view-transcript', 'view-chat'].includes(activeView) && (
            <div className="flex-1 p-12 flex flex-col items-center justify-center text-center space-y-3">
              <span className="text-5xl">⚡</span>
              <h3 className="font-carvist text-lg font-bold text-on-surface">
                Athena View Canvas: {activeView}
              </h3>
              <p className="text-xs text-on-surface-variant max-w-md">
                Phase B complete. This feature component will populate this panel in Phases C through E.
              </p>
            </div>
          )}
        </MainPanel>

        {/* Bottom Status Bar */}
        <StatusBar />
      </main>

      {/* Global Command Palette Modal */}
      <CommandPalette />
    </div>
  );
};
