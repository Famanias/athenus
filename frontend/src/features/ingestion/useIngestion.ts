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
  { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'pending', progress: 0 },
  { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'pending', progress: 0 },
  { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'pending', progress: 0 },
  { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
];

// Maps backend stage ids to the frontend pipeline stage index.
const STAGE_INDEX_BY_NAME: Record<string, number> = {
  audio_extraction: 0,
  transcription: 1,
  chunking: 2,
  vector_indexing: 3,
};

export function useIngestion() {
  const { activeWorkspaceId, setActiveView, setActiveMediaId } = useAppStore();
  const [stages, setStages] = useState<PipelineStage[]>(INITIAL_STAGES);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    setIsUploading(true);
    setErrorMessage(null);

    // Reset stages
    setStages([
      { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'processing', progress: 50 },
      { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'pending', progress: 0 },
      { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'pending', progress: 0 },
      { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
    ]);

    try {
      const data = await uploadMedia(file, activeWorkspaceId || 'default');
      setActiveMediaId(data.media_id);

      // Subscribe to SSE stream for live status
      const eventSource = createMediaProcessingStream(data.media_id);

      eventSource.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          const { current_stage, overall_progress, status, message, error } = payload;

          if (status === 'failed') {
            setErrorMessage(error || message || 'Ingestion processing failed.');
            setStages((prev) => {
              // Fail the specific stage reported by the backend instead of blaming
              // whichever stage happens to be currently 'processing' (which, at the
              // very start of an upload, is always stage 1).
              const failedIdx =
                typeof current_stage === 'string' && current_stage in STAGE_INDEX_BY_NAME
                  ? STAGE_INDEX_BY_NAME[current_stage]
                  : prev.findIndex((s) => s.status === 'processing');
              const resolvedIdx = failedIdx >= 0 ? failedIdx : 0;
              return prev.map((s, i) =>
                i === resolvedIdx ? { ...s, status: 'failed', progress: 0 } : s
              );
            });
            setIsUploading(false);
            eventSource.close();
            return;
          }

          if (status === 'completed' || current_stage === 'completed') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'completed', progress: 100 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'completed', progress: 100 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'completed', progress: 100 },
            ]);
            setIsUploading(false);
            eventSource.close();
            return;
          }

          // Dynamic stage progression
          if (current_stage === 'audio_extraction') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'processing', progress: overall_progress || 50 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'pending', progress: 0 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'pending', progress: 0 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
            ]);
          } else if (current_stage === 'transcription') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'processing', progress: overall_progress || 60 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'pending', progress: 0 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
            ]);
          } else if (current_stage === 'chunking') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'completed', progress: 100 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'processing', progress: overall_progress || 75 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
            ]);
          } else if (current_stage === 'vector_indexing') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'completed', progress: 100 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'completed', progress: 100 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'processing', progress: overall_progress || 90 },
            ]);
          }
        } catch (_e) {
          // Ignore JSON parse errors for heartbeat frames
        }
      };

      eventSource.onerror = () => {
        // Stop stream without fabricating fake success if upload is still processing
        eventSource.close();
      };
    } catch (err: any) {
      setErrorMessage(err.message || 'Upload failed. Backend engine unreachable.');
      setStages((prev) =>
        prev.map((s) => ({ ...s, status: s.status === 'processing' ? 'failed' : s.status }))
      );
      setIsUploading(false);
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
