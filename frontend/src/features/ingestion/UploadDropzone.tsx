'use client';

import React, { useRef } from 'react';
import { useIngestion } from './useIngestion';
import { Button } from '@/components/ui/Button';

export const UploadDropzone: React.FC = () => {
  const { stages, isUploading, selectedFile, errorMessage, handleFileUpload, setActiveView, activeSourceType } =
    useIngestion();
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
          Media Ingestion & Worker Pipeline
        </h2>
        <p className="text-xs text-on-surface-variant mt-1">
          Upload video, audio, or document learning materials to extract transcripts and index vector embeddings.
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
          accept="video/*,audio/*,.pdf,.docx,.pptx,.xlsx,.epub,.md,.txt,application/pdf"
          className="hidden"
        />
        <span className="text-5xl block">📤</span>
        <div>
          <h4 className="font-bold text-sm text-on-surface">
            Drag & Drop Video, Audio, or Document Files Here
          </h4>
          <p className="text-xs text-on-surface-variant mt-1">
            Supports MP4, MKV, MP3, PDF, DOCX, PPTX, XLSX, EPUB, TXT (Up to 100MB)
          </p>
        </div>
        <Button variant="primary" size="md">
          {selectedFile ? `Selected: ${selectedFile.name}` : 'Select Local File'}
        </Button>
      </div>

      {/* Pipeline Status Monitor */}
      <div className="p-6 bg-surface-container-low border border-outline-variant rounded-lg space-y-4">
        <div className="flex justify-between items-center">
          <h4 className="font-bold text-sm text-on-surface">
            Pipeline Monitor: {selectedFile ? selectedFile.name : 'Sample_Lecture.mp4'}
          </h4>
          {isUploading && (
            <span className="font-mono text-xs text-secondary animate-pulse">
              ⚙ Processing pipeline...
            </span>
          )}
        </div>

        <div className="space-y-3 text-xs">
          {stages.map((stg) => (
            <div key={stg.id} className="flex justify-between items-center p-2 rounded bg-surface-container">
              <span className="text-on-surface font-mono">{stg.name}</span>
              {stg.status === 'completed' && (
                <span className="text-emerald-400 font-mono font-semibold">✓ Completed</span>
              )}
              {stg.status === 'processing' && (
                <span className="text-secondary font-mono font-semibold">⚙ In Progress ({stg.progress}%)</span>
              )}
              {stg.status === 'failed' && (
                <span className="text-rose-400 font-mono font-semibold">✕ Failed</span>
              )}
              {stg.status === 'pending' && (
                <span className="text-on-surface-variant/50 font-mono">N/A</span>
              )}
            </div>
          ))}
        </div>

        {!isUploading && (
          <div className="pt-2 flex justify-end gap-3">
            <Button variant="secondary" onClick={() => setActiveView('view-video')}>
              {activeSourceType === 'pdf' ? 'Open Document Reader →' : 'Open Video Workspace →'}
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};
