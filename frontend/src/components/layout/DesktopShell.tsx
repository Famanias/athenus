'use client';

import React from 'react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { TopToolbar } from '@/components/navigation/TopToolbar';
import { StatusBar } from '@/components/layout/StatusBar';
import { MainPanel } from '@/components/layout/MainPanel';
import { CommandPalette } from '@/components/navigation/CommandPalette';
import { useAppStore } from '@/store/useAppStore';

// Feature Components (Phases B through F)
import { LibraryGrid } from '@/features/library/LibraryGrid';
import { VideoWorkspace } from '@/features/video/VideoWorkspace';
import { TranscriptReader } from '@/features/transcript/TranscriptReader';
import { ChatWorkspace } from '@/features/chat/ChatWorkspace';
import { FlashcardGrid } from '@/features/flashcards/FlashcardGrid';
import { QuizStudio } from '@/features/quiz/QuizStudio';
import { KnowledgeGraphCanvas } from '@/features/graph/KnowledgeGraphCanvas';
import { UploadDropzone } from '@/features/ingestion/UploadDropzone';
import { SystemSettings } from '@/features/settings/SystemSettings';

export const DesktopShell: React.FC = () => {
  const { activeView } = useAppStore();

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Categorized Navigation Sidebar */}
      <Sidebar />

      {/* Workspace Area */}
      <main className="ml-sidebar-width flex-1 min-w-0 flex flex-col h-full bg-background">
        {/* Top App Bar */}
        <TopToolbar />

        {/* Dynamic View Canvas */}
        <MainPanel>
          {activeView === 'view-dashboard' && <LibraryGrid />}
          {activeView === 'view-video' && <VideoWorkspace />}
          {activeView === 'view-transcript' && <TranscriptReader />}
          {activeView === 'view-chat' && <ChatWorkspace />}
          {activeView === 'view-flashcards' && <FlashcardGrid />}
          {activeView === 'view-quiz' && <QuizStudio />}
          {activeView === 'view-graph' && <KnowledgeGraphCanvas />}
          {activeView === 'view-ingestion' && <UploadDropzone />}
          {activeView === 'view-settings' && <SystemSettings />}

          {/* Default fallback for unimplemented views */}
          {!['view-dashboard', 'view-video', 'view-transcript', 'view-chat', 'view-flashcards', 'view-quiz', 'view-graph', 'view-ingestion', 'view-settings'].includes(activeView) && (
            <div className="flex-1 p-12 flex flex-col items-center justify-center text-center space-y-4 bg-surface-container-low border border-dashed border-outline-variant m-8 rounded-lg">
              <span className="text-5xl">🚧</span>
              <h3 className="font-carvist text-xl font-bold text-on-surface">
                Feature Under Construction
              </h3>
              <p className="text-xs text-on-surface-variant max-w-md">
                This Athenus capability is currently under active construction. Stay tuned for future release updates!
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
