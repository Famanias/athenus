// FallbackRenderer — used when a file format is accepted by Athenus
// ingestion (e.g. .docx, .pptx, .xlsx, .epub) but native visual browser
// preview is not implemented.
//
// Displays a clean metadata card (title, format, size, media id) plus a
// "Download Original File" / "Open Source Location" action. It explicitly
// informs the user that the document is fully indexed and usable by the
// Athenus AI agent even though visual preview is unavailable.

'use client';

import React, { useMemo } from 'react';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { extractExtension } from '../registry/RendererRegistry';
import type { RendererProps } from '../types';

/** Friendly labels for known fallback formats. */
const FORMAT_LABELS: Readonly<Record<string, string>> = {
  '.docx': 'Word Document',
  '.doc': 'Word Document',
  '.pptx': 'PowerPoint Presentation',
  '.ppt': 'PowerPoint Presentation',
  '.xlsx': 'Excel Spreadsheet',
  '.xls': 'Excel Spreadsheet',
  '.epub': 'EPUB eBook',
  '.rtf': 'Rich Text Format',
  '.odt': 'OpenDocument Text',
  '.ods': 'OpenDocument Spreadsheet',
  '.odp': 'OpenDocument Presentation',
};

const FALLBACK_EMOJIS: Readonly<Record<string, string>> = {
  '.docx': '📄',
  '.doc': '📄',
  '.pptx': '📊',
  '.ppt': '📊',
  '.xlsx': '📈',
  '.xls': '📈',
  '.epub': '📖',
  '.rtf': '📄',
};

export const FallbackRenderer: React.FC<RendererProps> = ({ url, metadata }) => {
  const extension = useMemo(
    () => (metadata.file_path || metadata.title || url ? extractExtension(metadata.file_path || metadata.title || url) : ''),
    [metadata.file_path, metadata.title, url]
  );
  const ext = extension.toLowerCase();

  const formatLabel = FORMAT_LABELS[ext] ?? (ext ? ext.slice(1).toUpperCase() : 'Unknown Format');
  const emoji = FALLBACK_EMOJIS[ext] ?? '🗂️';

  const fileSize = useMemo(() => {
    const bytes = metadata.file_size_bytes;
    if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${bytes} bytes`;
  }, [metadata.file_size_bytes]);

  const handleOpenOriginal = () => {
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  return (
    <div className="flex-1 overflow-y-auto custom-scrollbar p-6 bg-surface-container-lowest">
      <div className="max-w-xl mx-auto flex flex-col items-center text-center pt-10">
        <span className="text-6xl block mb-4">{emoji}</span>

        <Badge variant="secondary" className="mb-3">
          {formatLabel}
        </Badge>

        <h3 className="font-type-light text-lg font-bold text-on-surface mb-2">
          {metadata.title || 'Untitled Document'}
        </h3>

        <Card className="w-full mt-4 text-left">
          <div className="space-y-3 text-xs">
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant font-mono">Format</span>
              <span className="text-on-surface font-mono">{formatLabel}{ext ? ` (${ext})` : ''}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant font-mono">Size</span>
              <span className="text-on-surface font-mono">{fileSize}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant font-mono">Media ID</span>
              <span className="text-on-surface font-mono">{metadata.id}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-on-surface-variant font-mono">Ingestion Status</span>
              <Badge variant="active">Indexed</Badge>
            </div>
          </div>
        </Card>

        <div className="w-full mt-4 p-4 rounded border border-accent/30 bg-accent/10 text-left">
          <p className="text-xs leading-relaxed text-on-surface">
            <span className="font-bold text-accent">ℹ️ AI-ready, preview pending.</span>{' '}
            This document format is fully indexed and usable by the Athenus AI
            agent for RAG search, flashcards, and quizzes — but visual browser
            preview is not currently supported for this file type. Use the
            buttons below to open or download the original source file.
          </p>
        </div>

        <div className="mt-6 flex flex-wrap justify-center gap-3">
          <Button variant="primary" icon="download" onClick={handleOpenOriginal}>
            Download Original File
          </Button>
          <Button variant="secondary" icon="open_in_new" onClick={handleOpenOriginal}>
            Open Source Location
          </Button>
        </div>

        <p className="mt-6 text-[10px] font-mono text-on-surface-variant/50">
          Ask the AI assistant about this document in the chat panel.
        </p>
      </div>
    </div>
  );
};
