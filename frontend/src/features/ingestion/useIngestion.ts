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

// Document-aware stage templates (used for PDF/DOCX/PPTX/etc ingestion flows)
const DOCUMENT_STAGES: PipelineStage[] = [
  { id: 'stg_doc_1', name: 'Receiving Document Upload', status: 'pending', progress: 0 },
  { id: 'stg_doc_2', name: 'Parsing Document Structure (AnyDoc)', status: 'pending', progress: 0 },
  { id: 'stg_doc_3', name: 'Extracting Text from Scanned Pages (RapidOCR)', status: 'pending', progress: 0 },
  { id: 'stg_doc_4', name: 'Indexing Vector Embeddings', status: 'pending', progress: 0 },
];

// Maps backend stage ids to the frontend pipeline stage index.
const STAGE_INDEX_BY_NAME: Record<string, number> = {
  audio_extraction: 0,
  document_parsing: 0,
  transcription: 1,
  ocr_processing: 1,
  chunking: 2,
  vector_indexing: 3,
};

// Dynamic friendly stage name overrides (used by dynamic stage rendering)
const STAGE_FRIENDLY_NAMES: Record<string, string> = {
  document_parsing: 'Parsing Document Structure (AnyDoc)',
  ocr_processing: 'Extracting Text from Scanned Pages (RapidOCR)',
};

// Heuristic: is the active job a document/PDF ingestion flow?
function isDocumentJob(job: { job_type?: string; stage?: string; media_id?: string; title?: string } | null | undefined): boolean {
  if (!job) return false;
  const hint = `${job.job_type || ''} ${job.stage || ''} ${job.media_id || ''} ${job.title || ''}`.toLowerCase();
  return (
    hint.includes('document') ||
    hint.includes('pdf') ||
    hint.includes('docx') ||
    (job.media_id ? job.media_id.startsWith('doc_') : false) ||
    job.stage === 'document_parsing' ||
    job.stage === 'ocr_processing'
  );
}

export function useIngestion() {
  const {
    activeWorkspaceId,
    activeMediaId,
    setActiveMediaId,
    setActiveDocumentId,
    activeSourceType,
    setActiveSourceType,
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

  // Choose the right base stage template based on whether this is a video or document job
  const baseStages = isDocumentJob(currentJob) ? DOCUMENT_STAGES : INITIAL_STAGES;
  const stageIdPrefix = isDocumentJob(currentJob) ? 'stg_doc_' : 'stg_';
  const stageCount = baseStages.length;

  // Map job state to visual stages array
  const stages: PipelineStage[] = (() => {
    if (!currentJob) return baseStages;

    const { stage, progress, status } = currentJob;

    if (status === 'completed' || stage === 'completed' || stage === 'ready') {
      return baseStages.map((s, idx) => ({
        ...s,
        id: `${stageIdPrefix}${idx + 1}`,
        name: STAGE_FRIENDLY_NAMES[s.name.toLowerCase().includes('parsing')
          ? 'document_parsing'
          : s.name.toLowerCase().includes('ocr')
          ? 'ocr_processing'
          : ''] || s.name,
        status: 'completed',
        progress: 100,
      }));
    }

    if (status === 'failed' || stage === 'failed') {
      const activeStageIdx = STAGE_INDEX_BY_NAME[stage] ?? 0;
      return baseStages.map((s, idx) => {
        if (idx < activeStageIdx) return { ...s, status: 'completed', progress: 100 };
        if (idx === activeStageIdx) return { ...s, status: 'failed', progress: 0 };
        return { ...s, status: 'pending', progress: 0 };
      });
    }

    if (stage === 'queued') {
      return baseStages.map((s, idx) => ({
        ...s,
        id: `${stageIdPrefix}${idx + 1}`,
        status: idx === 0 ? 'processing' : 'pending',
        progress: idx === 0 ? progress || 15 : 0,
      }));
    }

    // Dynamic stage progression
    if (stage === 'audio_extraction' || stage === 'uploaded' || stage === 'document_parsing') {
      return baseStages.map((s, idx) => ({
        ...s,
        id: `${stageIdPrefix}${idx + 1}`,
        status: idx === 0 ? 'processing' : 'pending',
        progress: idx === 0 ? progress || 50 : 0,
      }));
    } else if (stage === 'transcription' || stage === 'ocr_processing') {
      return baseStages.map((s, idx) => {
        const isCompleted = idx < 1;
        const isProcessing = idx === 1;
        return {
          ...s,
          id: `${stageIdPrefix}${idx + 1}`,
          status: isCompleted ? 'completed' : isProcessing ? 'processing' : 'pending',
          progress: isCompleted ? 100 : isProcessing ? progress || 60 : 0,
        };
      });
    } else if (stage === 'chunking' || stage === 'vector_indexing') {
      return baseStages.map((s, idx) => {
        const isCompleted = idx < 2;
        const isProcessing = idx === 2;
        return {
          ...s,
          id: `${stageIdPrefix}${idx + 1}`,
          status: isCompleted ? 'completed' : isProcessing ? 'processing' : 'pending',
          progress: isCompleted ? 100 : isProcessing ? progress || 75 : 0,
        };
      });
    } else if (stage === 'graph_extraction' || stage === 'collect_context' || stage === 'llm_generation' || stage === 'validation') {
      return baseStages.map((s, idx) => {
        const isCompleted = idx < stageCount - 1;
        const isProcessing = idx === stageCount - 1;
        return {
          ...s,
          id: `${stageIdPrefix}${idx + 1}`,
          status: isCompleted ? 'completed' : isProcessing ? 'processing' : 'pending',
          progress: isCompleted ? 100 : isProcessing ? progress || 85 : 0,
        };
      });
    }

    return baseStages;
  })();

  const isUploading = currentJob ? currentJob.status === 'processing' || currentJob.status === 'pending' || currentJob.status === 'queued' : false;
  const errorMessage = localError || currentJob?.error || null;

  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    setLocalError(null);

    // Detect modality from file type — PDF/office documents switch the
    // workspace source context to 'pdf', everything else stays 'video'.
    const isDocumentFile =
      /\.(pdf|docx?|pptx?|xlsx?|epub|md|txt)$/i.test(file.name) ||
      file.type === 'application/pdf';
    if (isDocumentFile) {
      setActiveSourceType('pdf');
    }

    try {
      const data = await uploadMedia(file, activeWorkspaceId || 'default');
      const jobId = `ingestion_${data.media_id}`;

      if (isDocumentFile) {
        setActiveDocumentId(data.media_id);
        setActiveSourceType('pdf');
      } else {
        setActiveMediaId(data.media_id);
        setActiveSourceType('video');
      }
      setActiveJobId(jobId);
      setInspectedJobId(jobId);

      // Register job in store
      upsertJob({
        job_id: jobId,
        media_id: data.media_id,
        workspace_id: activeWorkspaceId || 'default',
        title: file.name,
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
    activeSourceType,
  };
}
