import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { uploadMedia, createMediaProcessingStream } from '@/services/mediaService';

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
    upsertJob,
  } = useAppStore();

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);

  // Find active job for current workspace / media item
  const currentJob =
    (activeJobId && jobs[activeJobId]) ||
    Object.values(jobs).find(
      (j) => j.workspace_id === (activeWorkspaceId || 'default') && j.status === 'processing'
    ) ||
    (activeMediaId
      ? Object.values(jobs).find((j) => j.media_id === activeMediaId)
      : undefined);

  // Map job state to visual stages array
  const stages: PipelineStage[] = (() => {
    if (!currentJob) return INITIAL_STAGES;

    const { stage, progress, status } = currentJob;

    if (status === 'completed' || stage === 'completed') {
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
    } else if (stage === 'chunking') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'completed', progress: 100 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'processing', progress: progress || 75 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'pending', progress: 0 },
      ];
    } else if (stage === 'vector_indexing' || stage === 'graph_extraction') {
      return [
        { id: 'stg_1', name: 'Hermes is Receiving Your Lecture', status: 'completed', progress: 100 },
        { id: 'stg_2', name: 'Apollo is Listening to Every Word', status: 'completed', progress: 100 },
        { id: 'stg_3', name: 'Athenus is Understanding the Concepts', status: 'completed', progress: 100 },
        { id: 'stg_4', name: 'The Owl of Athenus is Delivering the Answer', status: 'processing', progress: progress || 90 },
      ];
    }

    return INITIAL_STAGES;
  })();

  const isUploading = currentJob ? currentJob.status === 'processing' || currentJob.status === 'pending' : false;
  const errorMessage = localError || currentJob?.error || null;

  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    setLocalError(null);

    try {
      const data = await uploadMedia(file, activeWorkspaceId || 'default');
      const jobId = `job_${data.media_id}`;

      setActiveMediaId(data.media_id);
      setActiveJobId(jobId);

      // Register job in background task runtime
      upsertJob({
        job_id: jobId,
        media_id: data.media_id,
        workspace_id: activeWorkspaceId || 'default',
        job_type: 'ingestion',
        stage: 'uploaded',
        progress: 15,
        status: 'processing',
        message: 'File uploaded. Initiating background ASR pipeline.',
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
  };
}
