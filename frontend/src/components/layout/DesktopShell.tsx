'use client';

import React, { useEffect } from 'react';
import { Sidebar } from '@/components/navigation/Sidebar';
import { TopToolbar } from '@/components/navigation/TopToolbar';
import { MainPanel } from '@/components/layout/MainPanel';
import { useAppStore, rehydrateStoredState } from '@/store/useAppStore';

// Feature Components (Phases B through F)
import { LibraryGrid } from '@/features/library/LibraryGrid';
import { VideoWorkspace } from '@/features/video/VideoWorkspace';
import { TranscriptReader } from '@/features/transcript/TranscriptReader';
import { ChatWorkspace } from '@/features/chat/ChatWorkspace';
import { FlashcardGrid } from '@/features/flashcards/FlashcardGrid';
import { QuizStudio } from '@/features/quiz/QuizStudio';
import { KnowledgeGraphCanvas } from '@/features/graph/KnowledgeGraphCanvas';
import { UnifiedLearningPipeline } from '@/features/ingestion/UnifiedLearningPipeline';
import { AnalyticsDashboard } from '@/features/analytics/AnalyticsDashboard';
import { SystemSettings } from '@/features/settings/SystemSettings';
import { NotesWorkspace } from '@/features/notes/NotesWorkspace';
import { BackgroundTaskRuntime } from '@/features/pipeline/BackgroundTaskRuntime';

import { PersistentMediaPlayer } from '@/features/video/PersistentMediaPlayer';

export const DesktopShell: React.FC = () => {
  const { activeView } = useAppStore();

  useEffect(() => {
    rehydrateStoredState();
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-background text-on-background">
      {/* Decoupled Background Task Engine Runtime */}
      <BackgroundTaskRuntime />

      {/* Persistent Single Authoritative Video Player */}
      <PersistentMediaPlayer />

      {/* Categorized Navigation Sidebar */}
      <Sidebar />

      {/* Workspace Area */}
      <main className="ml-sidebar-width flex-1 min-w-0 flex flex-col h-full bg-background">
        {/* Top App Bar */}
        <TopToolbar />

        {/* Dynamic View Canvas */}
        <MainPanel>
          {/* Persistent Video Workspace Container (guarantees single authoritative video player DOM node) */}
          <div className={`flex-1 flex flex-col h-full w-full ${activeView === 'view-video' ? '' : 'hidden'}`}>
            <VideoWorkspace />
          </div>

          {activeView === 'view-dashboard' && <LibraryGrid />}
          {activeView === 'view-chat' && <ChatWorkspace />}
          {activeView === 'view-notes' && <NotesWorkspace />}
          {activeView === 'view-flashcards' && <FlashcardGrid />}
          {activeView === 'view-quiz' && <QuizStudio />}
          {activeView === 'view-graph' && <KnowledgeGraphCanvas />}
          {activeView === 'view-ingestion' && <UnifiedLearningPipeline />}
          {activeView === 'view-analytics' && <AnalyticsDashboard />}
          {activeView === 'view-settings' && <SystemSettings />}

          {/* Default fallback for unimplemented views */}
          {!['view-dashboard', 'view-video', 'view-chat', 'view-notes', 'view-flashcards', 'view-quiz', 'view-graph', 'view-ingestion', 'view-analytics', 'view-settings'].includes(activeView) && (
            <div className="flex-1 p-12 flex flex-col items-center justify-center text-center space-y-4 bg-surface-container-low border border-dashed border-outline-variant m-8 rounded-lg">
              <span className="text-5xl">🚧</span>
              <h3 className="font-type-light text-xl font-bold text-on-surface">
                Feature Under Construction
              </h3>
              <p className="text-xs text-on-surface-variant max-w-md">
                This Athenus capability is currently under active construction. Stay tuned for future release updates!
              </p>
            </div>
          )}
        </MainPanel>
      </main>
    </div>
  );
};
