import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { uploadMedia, createMediaProcessingStream } from '@/services/mediaService';
import { apiClient } from '@/services/apiClient';

export interface PipelineStage {
  id: string;
  name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
}

const INITIAL_STAGES: PipelineStage[] = [
  { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'pending', progress: 0 },
  { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'pending', progress: 0 },
  { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'pending', progress: 0 },
  { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
];

// Maps backend stage ids to the frontend pipeline stage index.
const STAGE_INDEX_BY_NAME: Record<string, number> = {
  audio_extraction: 0,
  transcription: 1,
  chunking: 2,
  vector_indexing: 3,
};

export function useIngestion() {
  const {
    activeWorkspaceId,
    activeMediaId,
    setActiveMediaId,
    setActiveView,
    jobs,
    activeJobId,
    setActiveJobId,
    inspectedJobId,
    setInspectedJobId,
    upsertJob,
  } = useAppStore();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // Poll workspace media jobs from backend
  useEffect(() => {
    let timer: NodeJS.Timeout;
    const fetchJobs = async () => {
      if (!activeWorkspaceId) return;
      try {
        const backendJobs = await apiClient<Array<any>>(
          `/api/v1/media/workspace/${encodeURIComponent(activeWorkspaceId)}/jobs`
        );
        if (Array.isArray(backendJobs)) {
          backendJobs.forEach((j) => {
            upsertJob({
              job_id: j.job_id,
              media_id: j.media_id,
              workspace_id: j.workspace_id,
              job_type: 'ingestion',
              stage: j.stage || 'queued',
              progress: j.progress || 0,
              status: j.status || 'pending',
              message: j.message || '',
              error: j.error_message || undefined,
              startedAt: j.created_at || new Date().toISOString(),
              updatedAt: j.updated_at || new Date().toISOString(),
            });
          });
        }
      } catch (_e) {}
    };

    fetchJobs();
    timer = setInterval(fetchJobs, 4000);
    return () => clearInterval(timer);
  }, [activeWorkspaceId, upsertJob]);

  // List of all workspace jobs for UI queue panel
  const workspaceJobs = Object.values(jobs)
    .filter((j) => j.workspace_id === (activeWorkspaceId || 'default'))
    .sort((a, b) => new Date(b.startedAt).getTime() - new Date(a.startedAt).getTime());

  // Find active job for current workspace / media item
  const activeProcessingJob =
    workspaceJobs.find((j) => j.status === 'processing' || j.status === 'pending') ||
    (activeJobId ? jobs[activeJobId] : undefined);

  // Job selected for inspection in the detailed stage stepper
  const currentJob =
    (inspectedJobId && jobs[inspectedJobId]) ||
    activeProcessingJob ||
    (activeMediaId ? jobs[`ingestion_${activeMediaId}`] : undefined) ||
    workspaceJobs[0];

  // Map job state to visual stages array
  const stages: PipelineStage[] = (() => {
    if (!currentJob) return INITIAL_STAGES;

    const { stage, progress, status } = currentJob;

    if (status === 'completed' || stage === 'completed' || stage === 'ready') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'completed', progress: 100 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'completed', progress: 100 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'completed', progress: 100 },
      ];
    }

    if (status === 'failed' || stage === 'failed') {
      const activeStageIdx = STAGE_INDEX_BY_NAME[stage] ?? 0;
      return INITIAL_STAGES.map((s, idx) => {
        if (idx < activeStageIdx) return { ...s, status: 'completed', progress: 100 };
        if (idx === activeStageIdx) return { ...s, status: 'failed', progress: 0 };
        return { ...s, status: 'pending', progress: 0 };
      });
    }

    if (stage === 'queued') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'processing', progress: 15 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'pending', progress: 0 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'pending', progress: 0 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
      ];
    }

    // Dynamic stage progression
    if (stage === 'audio_extraction' || stage === 'uploaded') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'processing', progress: progress || 50 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'pending', progress: 0 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'pending', progress: 0 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
      ];
    } else if (stage === 'transcription') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'processing', progress: progress || 60 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'pending', progress: 0 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
      ];
    } else if (stage === 'chunking' || stage === 'vector_indexing') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'completed', progress: 100 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'processing', progress: progress || 75 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
      ];
    } else if (stage === 'graph_extraction' || stage === 'collect_context' || stage === 'llm_generation' || stage === 'validation') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'completed', progress: 100 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'completed', progress: 100 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'processing', progress: progress || 85 },
      ];
    }

    return INITIAL_STAGES;
  })();

  const isUploading = currentJob ? currentJob.status === 'processing' || currentJob.status === 'pending' || currentJob.status === 'queued' : false;
  const errorMessage = localError || currentJob?.error || null;

  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    setLocalError(null);

    try {
      const data = await uploadMedia(file, activeWorkspaceId || 'default');
      const jobId = `ingestion_${data.media_id}`;

      setActiveMediaId(data.media_id);
      setActiveJobId(jobId);
      setInspectedJobId(jobId);

      // Register job in store
      upsertJob({
        job_id: jobId,
        media_id: data.media_id,
        workspace_id: activeWorkspaceId || 'default',
        job_type: 'ingestion',
        stage: 'queued',
        progress: 5,
        status: 'queued',
        message: 'File uploaded. Enqueued in persistent ingestion queue.',
        startedAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      });
    } catch (err: any) {
      setLocalError(err.message || 'Upload failed. Backend engine unreachable.');
    }
  };

  return {
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
  };
}
