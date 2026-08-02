'use client';

import React from 'react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { TopToolbar } from '@/components/navigation/TopToolbar';
import { StatusBar } from '@/components/layout/StatusBar';
import { MainPanel } from '@/components/layout/MainPanel';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import { useAppStore } from '@/store/useAppStore';

// Feature Components (Phases B & C)
import { LibraryGrid } from '@/features/library/LibraryGrid';
import { VideoWorkspace } from '@/features/video/VideoWorkspace';
import { TranscriptReader } from '@/features/transcript/TranscriptReader';
import { ChatWorkspace } from '@/features/chat/ChatWorkspace';

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
          {activeView === 'view-chat' && <ChatWorkspace />}

          {/* Fallback canvas for future phases */}
          {!['view-dashboard', 'view-video', 'view-transcript', 'view-chat'].includes(activeView) && (
            <div className="flex-1 p-12 flex flex-col items-center justify-center text-center space-y-3">
              <span className="text-5xl">⚡</span>
              <h3 className="font-carvist text-lg font-bold text-on-surface">
                Athena View Canvas: {activeView}
              </h3>
              <p className="text-xs text-on-surface-variant max-w-md">
                Phase C complete. Feature modules will populate this panel in Phases D through F.
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
