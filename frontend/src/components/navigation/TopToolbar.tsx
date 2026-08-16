import React from 'react';
import { useAppStore } from '@/store/useAppStore';
import { WorkspaceModal } from '../workspace/WorkspaceModal';

export const TopToolbar: React.FC = () => {
  const { jobs, setActiveView } = useAppStore();

  const activeJobs = Object.values(jobs).filter(
    (j) => j.status === 'processing' || j.status === 'pending'
  );
  const singleJob = activeJobs.length === 1 ? activeJobs[0] : null;

  return (
    <>
      {activeJobs.length > 0 && (
        <header className="shrink-0 flex justify-between items-center w-full px-6 py-2 z-50 bg-background border-b border-outline-variant">
          {/* Active Background Task Progress Badge */}
          <button
            type="button"
            onClick={() => setActiveView('view-ingestion')}
            className="flex items-center gap-2 bg-secondary/15 hover:bg-secondary/25 border border-secondary/40 text-secondary px-3 py-1.5 rounded text-xs font-mono font-bold transition-all shadow-sm shrink-0"
            title="Click to view live background task pipeline"
          >
            <span className="material-symbols-outlined text-sm animate-pulse">sync</span>
            <span>
              {singleJob
                ? `⚡ ${singleJob.stage.replace('_', ' ')} (${singleJob.progress}%)`
                : `⚡ ${activeJobs.length} Background Tasks Running`}
            </span>
          </button>
        </header>
      )}

      {/* Global Workspace Modal */}
      <WorkspaceModal />
    </>
  );
};
