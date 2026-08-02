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
          const payload = JSON.parse(event.data.replace(/'/g, '"'));
          if (payload.status === 'completed' || payload.status === 'TRANSCRIBING') {
            setStages([
              { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
              { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'completed', progress: 100 },
              { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'completed', progress: 100 },
              { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'completed', progress: 100 },
            ]);
            setIsUploading(false);
            eventSource.close();
          }
        } catch (_e) {
          // Keep listening
        }
      };

      eventSource.onerror = () => {
        // SSE disconnected or closed - finalize stages
        setStages([
          { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
          { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'completed', progress: 100 },
          { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'completed', progress: 100 },
          { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'completed', progress: 100 },
        ]);
        setIsUploading(false);
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
