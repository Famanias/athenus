'use client';

import React, { useRef } from 'react';
import { useIngestion, PipelineStage } from './useIngestion';
import { useAnalytics } from '@/features/analytics/useAnalytics';
import { Button } from '@/components/ui/Button';

function StageRow({ stage }: { stage: PipelineStage }) {
  return (
    <div className="flex justify-between items-center p-2.5 rounded bg-surface-container">
      <span className="text-on-surface font-mono text-xs">{stage.name}</span>
      {stage.status === 'completed' && (
        <span className="text-emerald-400 font-mono font-semibold text-xs">✓ Completed</span>
      )}
      {stage.status === 'processing' && (
        <span className="text-secondary font-mono font-semibold text-xs">
          ⚙ In Progress ({stage.progress}%)
        </span>
      )}
      {stage.status === 'failed' && (
        <span className="text-rose-400 font-mono font-semibold text-xs">✕ Failed</span>
      )}
      {stage.status === 'pending' && (
        <span className="text-on-surface-variant/50 font-mono text-xs">N/A</span>
      )}
    </div>
  );
}

interface PipelineLink {
  id: string;
  view: string;
  label: string;
  icon: string;
  description: string;
}

const PIPELINE_LINKS: PipelineLink[] = [
  { id: 'pl_graph', view: 'view-graph', label: 'Knowledge Graph', icon: 'hub', description: 'Explore extracted concepts & relations' },
  { id: 'pl_flashcards', view: 'view-flashcards', label: 'Flashcards', icon: 'layers', description: 'SM-2 spaced repetition practice' },
  { id: 'pl_quiz', view: 'view-quiz', label: 'Quiz Studio', icon: 'quiz', description: 'Concept-balanced comprehension checks' },
  { id: 'pl_analytics', view: 'view-analytics', label: 'Analytics', icon: 'analytics', description: 'Mastery tracking & revision plan' },
];

export const UnifiedLearningPipeline: React.FC = () => {
  const {
    stages,
    isUploading,
    selectedFile,
    errorMessage,
    handleFileUpload,
    setActiveView,
    workspaceJobs,
    currentJob,
    inspectedJobId,
    setInspectedJobId,
  } = useIngestion();
  const { workspace } = useAnalytics();
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const onFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFileUpload(e.target.files[0]);
    }
  };

  return (
    <div className="flex-1 p-8 overflow-y-auto custom-scrollbar max-w-4xl mx-auto space-y-6 w-full">
      {/* Error Notice */}
      {errorMessage && (
        <div className="p-3 bg-rose-950/60 border border-rose-500/40 rounded text-rose-300 text-xs flex justify-between items-center">
          <span>⚠️ {errorMessage}</span>
        </div>
      )}

      {/* Header */}
      <div className="pb-4 border-b border-outline-variant">
        <h2 className="font-type-light text-2xl font-bold text-on-surface">
          Unified Learning Pipeline
        </h2>
        <p className="text-xs text-on-surface-variant mt-1">
          Ingest lecture media, auto-extract the knowledge graph, then generate
          flashcards, quizzes, and analytics — all grounded and on-demand.
        </p>
      </div>

      {/* Drag and Drop Zone */}
      <div
        onClick={() => fileInputRef.current?.click()}
        className="p-10 border-2 border-dashed border-outline-variant rounded-lg bg-surface-container-low text-center space-y-4 hover:border-secondary transition-all cursor-pointer"
      >
        <input
          type="file"
          ref={fileInputRef}
          onChange={onFileChange}
          accept="video/*,audio/*"
          className="hidden"
        />
        <span className="text-5xl block">📤</span>
        <div>
          <h4 className="font-bold text-sm text-on-surface">
            Drag & Drop Video or Audio Files Here
          </h4>
          <p className="text-xs text-on-surface-variant mt-1">
            Supports MP4, MKV, AVI, WAV, MP3 (Up to 2GB)
          </p>
        </div>
        <Button variant="primary" size="md">
          {selectedFile ? `Selected: ${selectedFile.name}` : 'Select Local Media File'}
        </Button>
      </div>

      {/* Multi-Video Ingestion Queue Panel */}
      {workspaceJobs && workspaceJobs.length > 0 && (
        <div className="p-4 bg-surface-container-low border border-outline-variant rounded-lg space-y-3">
          <div className="flex justify-between items-center">
            <h4 className="font-bold text-xs uppercase tracking-wider text-on-surface-variant font-mono">
              Workspace Video Ingestion Queue ({workspaceJobs.length} Total)
            </h4>
            <span className="text-[10px] text-on-surface-variant/60 font-mono">
              Click video to inspect stage stepper
            </span>
          </div>
          <div className="space-y-2 max-h-48 overflow-y-auto custom-scrollbar">
            {workspaceJobs.map((j, idx) => {
              const isSelected = currentJob?.job_id === j.job_id;
              return (
                <div
                  key={j.job_id}
                  onClick={() => setInspectedJobId(j.job_id)}
                  className={`p-2.5 rounded border text-xs font-mono flex justify-between items-center cursor-pointer transition-all ${
                    isSelected
                      ? 'border-secondary bg-secondary/10 text-on-surface font-semibold shadow-sm'
                      : 'border-outline-variant/60 bg-surface-container hover:bg-surface-container-high text-on-surface-variant'
                  }`}
                >
                  <div className="flex items-center gap-2 truncate pr-2">
                    <span className="material-symbols-outlined text-sm text-secondary shrink-0">
                      {j.status === 'completed' ? 'check_circle' : j.status === 'processing' ? 'sync' : 'hourglass_top'}
                    </span>
                    <span className="truncate">{j.title}</span>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span
                      className={`text-[10px] px-1.5 py-0.5 rounded font-bold uppercase ${
                        j.status === 'completed'
                          ? 'bg-emerald-950/60 border border-emerald-500/40 text-emerald-300'
                          : j.status === 'processing'
                          ? 'bg-amber-950/60 border border-amber-500/40 text-amber-300 animate-pulse'
                          : 'bg-surface-container-high border border-outline-variant text-on-surface-variant'
                      }`}
                    >
                      {j.status === 'queued' ? `Queued (#${idx} in Line)` : j.status}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Pipeline Status Monitor */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex justify-between items-center">
          <h4 className="font-bold text-sm text-on-surface">
            Inspected Pipeline: {currentJob ? currentJob.title : selectedFile ? selectedFile.name : 'Sample_Lecture.mp4'}
          </h4>
          {isUploading && (
            <span className="font-mono text-xs text-secondary animate-pulse">
              ⚙ Processing pipeline...
            </span>
          )}
        </div>

        <div className="space-y-3">
          {stages.map((stg) => (
            <StageRow key={stg.id} stage={stg} />
          ))}
        </div>

        {!isUploading && (
          <div className="pt-2 flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setActiveView('view-video')}>
              Open Video Workspace →
            </Button>
          </div>
        )}
      </div>

      {/* Downstream artifact pipeline */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {PIPELINE_LINKS.map((link) => (
          <button
            key={link.id}
            onClick={() => setActiveView(link.view)}
            className="p-4 bg-surface-container-low border border-outline-variant rounded-lg text-left hover:border-secondary hover:bg-surface-container-high transition-all space-y-2"
          >
            <span className="material-symbols-outlined text-secondary text-xl block">
              {link.icon}
            </span>
            <div>
              <p className="text-xs font-bold text-on-surface">{link.label}</p>
              <p className="text-[10px] text-on-surface-variant leading-relaxed">{link.description}</p>
            </div>
          </button>
        ))}
      </div>

      {/* Workspace footprint */}
      {workspace && (
        <div className="p-4 bg-surface-container-low border border-outline-variant rounded-lg flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-secondary text-base">analytics</span>
            <span className="font-mono text-xs text-on-surface-variant">
              Workspace footprint: {workspace.total_media} media · {workspace.total_concepts} concepts
              · {workspace.total_flashcards} flashcards · {workspace.total_quiz_attempts} quiz attempts
            </span>
          </div>
          <Button variant="outline" size="sm" icon="analytics" onClick={() => setActiveView('view-analytics')}>
            Dashboard
          </Button>
        </div>
      )}
    </div>
  );
};
