'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import type { RendererProps } from '../types';

const HIGHLIGHT_DURATION_MS = 2500;

export const PdfRenderer: React.FC<RendererProps> = ({
  url,
  metadata,
  activePage,
  safeTotalPages,
  targetPage,
  onPageChange,
}) => {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [pdfKey, setPdfKey] = useState<number>(0);
  const [showHighlight, setShowHighlight] = useState<boolean>(false);
  const [zoom, setZoom] = useState<number>(1);
  const highlightTimeout = useRef<NodeJS.Timeout | null>(null);

  // Fetch PDF binary and convert to a local Blob URL for reliable Tauri/browser rendering
  useEffect(() => {
    let isMounted = true;
    let activeBlobUrl: string | null = null;

    async function loadPdfBlob() {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch(url.split('#')[0]);
        if (!response.ok) {
          throw new Error(`Failed to load PDF file (HTTP ${response.status})`);
        }
        const blob = await response.blob();
        if (isMounted) {
          activeBlobUrl = URL.createObjectURL(blob);
          setBlobUrl(activeBlobUrl);
        }
      } catch (err: unknown) {
        if (isMounted) {
          setError(err instanceof Error ? err.message : 'Error loading PDF binary.');
        }
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    if (url) {
      loadPdfBlob();
    }

    return () => {
      isMounted = false;
      if (activeBlobUrl) {
        URL.revokeObjectURL(activeBlobUrl);
      }
      if (highlightTimeout.current) clearTimeout(highlightTimeout.current);
    };
  }, [url]);

  // Citation jumps (📄 Page X): flash highlight ring
  useEffect(() => {
    if (targetPage !== null && targetPage >= 1 && targetPage <= safeTotalPages) {
      setPdfKey((k) => k + 1);
      setShowHighlight(true);
      if (highlightTimeout.current) clearTimeout(highlightTimeout.current);
      highlightTimeout.current = setTimeout(() => {
        setShowHighlight(false);
      }, HIGHLIGHT_DURATION_MS);
    }
  }, [targetPage, safeTotalPages]);

  const pdfSrc = useMemo(() => {
    if (!blobUrl) return '';
    const page = Math.min(Math.max(1, activePage), Math.max(1, safeTotalPages));
    return `${blobUrl}#page=${page}`;
  }, [blobUrl, activePage, safeTotalPages]);

  const fileSize = useMemo(() => {
    const bytes = metadata.file_size_bytes;
    if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${bytes} bytes`;
  }, [metadata.file_size_bytes]);

  const handleZoomIn = () => setZoom((z) => Math.min(2.5, z + 0.15));
  const handleZoomOut = () => setZoom((z) => Math.max(0.5, z - 0.15));
  const handleZoomFit = () => setZoom(1);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-surface-container-lowest h-full w-full">
      {/* PDF Viewer Container */}
      <div className="flex-1 relative overflow-hidden flex items-center justify-center bg-[#1a1a2e]">
        {/* Accent highlight ring — shown on citation jump landing */}
        {showHighlight && (
          <div className="absolute inset-0 z-20 pointer-events-none border-4 border-secondary/60 ring-4 ring-secondary/30 bg-secondary/5 animate-pulse rounded" />
        )}

        {loading && (
          <div className="flex flex-col items-center justify-center p-6 text-on-surface-variant gap-2">
            <span className="animate-spin text-2xl">⚙</span>
            <span className="text-xs font-mono">Loading PDF document binary...</span>
          </div>
        )}

        {error && !loading && (
          <div className="flex flex-col items-center justify-center p-6 text-center text-error gap-2 max-w-md">
            <span className="text-3xl">⚠️</span>
            <h4 className="font-bold text-sm">PDF Display Error</h4>
            <p className="text-xs font-mono text-on-surface-variant">{error}</p>
          </div>
        )}

        {!loading && !error && blobUrl && (
          <div
            className="w-full h-full transition-transform duration-150 origin-center flex items-center justify-center"
            style={{ transform: `scale(${zoom})` }}
          >
            <object
              key={pdfKey}
              data={pdfSrc}
              type="application/pdf"
              className="w-full h-full border-none"
            >
              <embed src={pdfSrc} type="application/pdf" className="w-full h-full border-none" />
              <div className="p-6 text-center text-on-surface-variant text-xs">
                Your browser or window does not support embedded PDF viewing.{' '}
                <a href={blobUrl} target="_blank" rel="noopener noreferrer" className="text-secondary underline">
                  Open PDF file directly
                </a>
              </div>
            </object>
          </div>
        )}
      </div>
    </div>
  );
};
