import { useState } from 'react';
import { useAppStore } from '@/store/useAppStore';

export interface PipelineStage {
  id: string;
  name: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  progress: number;
}

const INITIAL_STAGES: PipelineStage[] = [
  { id: 'stg_1', name: '1. FFmpeg Audio Extraction (16kHz Mono WAV)', status: 'completed', progress: 100 },
  { id: 'stg_2', name: '2. Faster-Whisper Speech Recognition', status: 'processing', progress: 85 },
  { id: 'stg_3', name: '3. Semantic Chunker (~250 Word Windows)', status: 'pending', progress: 0 },
  { id: 'stg_4', name: '4. BGE Embedding & Qdrant Vector Upsert', status: 'pending', progress: 0 },
];

export function useIngestion() {
  const { activeWorkspaceId, setActiveView, setActiveMediaId } = useAppStore();
  const [stages, setStages] = useState<PipelineStage[]>(INITIAL_STAGES);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const handleFileUpload = async (file: File) => {
    setSelectedFile(file);
    setIsUploading(true);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('workspace_id', activeWorkspaceId);

    try {
      const res = await fetch('http://localhost:8000/api/v1/media/upload', {
        method: 'POST',
        body: formData,
      });

      if (res.ok) {
        const data = await res.json();
        setActiveMediaId(data.media_id || 'med_uploaded_01');
      }
    } catch (_err) {
      // Local fallback simulation
    } finally {
      setTimeout(() => {
        setStages((prev) =>
          prev.map((s) => ({ ...s, status: 'completed', progress: 100 }))
        );
        setIsUploading(false);
      }, 1500);
    }
  };

  return {
    stages,
    isUploading,
    selectedFile,
    handleFileUpload,
    setActiveView,
  };
}
