// PdfRenderer — renders original PDF binary via browser-native iframe embedding.
//
// This is the most reliable cross-platform approach: Chrome, Edge, Firefox,
// and Safari all natively render PDFs in an <iframe>, with zero extra
// dependencies. The native viewer guarantees visual fidelity — including
// scanned PDFs (rendered as exact page images), tables, diagrams, and
// unusual page dimensions.
//
// Page Navigation
//   - Browser-native PDF viewers (Chrome/Edge, Firefox) honor the `#page=N`
//     URL fragment, so we embed `url#page=N` in the iframe src.
//   - Updating the fragment re-navigates the embedded viewer to that page.
//
// Citation Jumping (📄 Page X)
//   - The orchestrator passes `targetPage` via props when a citation badge
//     is clicked.
//   - We bump `pdfKey` (forcing a clean iframe re-mount with the new
//     `#page=N` fragment) and show a temporary accent highlight ring so the
//     user sees the jump landed.
//
// Zoom
//   - The embedded viewer has its own zoom; we additionally support CSS
//     transform-based zoom on the iframe wrapper (fit / zoom in / zoom out).

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
  const [pdfKey, setPdfKey] = useState<number>(0);
  const [showHighlight, setShowHighlight] = useState<boolean>(false);
  const [zoom, setZoom] = useState<number>(1);
  const highlightTimeout = useRef<NodeJS.Timeout | null>(null);

  // Cleanup highlight timer on unmount.
  useEffect(() => {
    return () => {
      if (highlightTimeout.current) clearTimeout(highlightTimeout.current);
    };
  }, []);

  // Citation jumps (📄 Page X): re-mount the iframe with the #page=N fragment
  // so the embedded viewer lands on the target page, then flash a highlight
  // ring so the user sees the jump landed.
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

  // Manual navigation (Prev/Next/jump input in the orchestrator): the
  // activePage prop changes; update the #page=N fragment on the same iframe.
  // Browser PDF viewers navigate to the page on fragment change.
  const pdfSrc = useMemo(() => {
    const base = url.split('#')[0];
    const page = Math.min(Math.max(1, activePage), Math.max(1, safeTotalPages));
    return `${base}#page=${page}`;
  }, [url, activePage, safeTotalPages]);

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
    <div className="flex-1 flex flex-col overflow-hidden bg-surface-container-lowest">
      {/* PDF Viewer — browser-native iframe */}
      <div className="flex-1 relative overflow-hidden">
        {/* Accent highlight ring — shown on citation jump landing */}
        {showHighlight && (
          <div className="absolute inset-0 z-10 pointer-events-none border-4 border-secondary/60 ring-4 ring-secondary/30 bg-secondary/5 animate-pulse rounded" />
        )}

        {/* Native PDF viewer. `key={pdfKey}` forces a clean re-mount for
            citation jumps so the #page=N fragment is re-evaluated. Zoom is
            applied via CSS transform on the wrapper. */}
        <div
          className="w-full h-full transition-transform duration-150 origin-center"
          style={{ transform: `scale(${zoom})` }}
        >
          <iframe
            key={pdfKey}
            title={`PDF Viewer — ${metadata.title}`}
            src={pdfSrc}
            className="w-full h-full border-none"
            style={{ background: '#1a1a2e' }}
          />
        </div>
      </div>

      {/* PDF toolbar */}
      <div className="px-3 py-2 bg-surface-container-low border-t border-outline-variant text-[10px] font-mono text-on-surface-variant/60 flex flex-wrap justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-secondary shrink-0">📄 PDF</span>
          <span className="hidden md:inline truncate max-w-xs">{metadata.title}</span>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-secondary font-semibold">
            Page {activePage} of {safeTotalPages}
          </span>
          <span className="text-on-surface-variant/50">•</span>
          <span>{fileSize}</span>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={handleZoomFit} title="Fit to screen">
            Fit
          </Button>
          <Button variant="ghost" size="sm" onClick={handleZoomOut} title="Zoom out">
            −
          </Button>
          <span className="text-on-surface-variant px-1 w-10 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <Button variant="ghost" size="sm" onClick={handleZoomIn} title="Zoom in">
            +
          </Button>
        </div>
      </div>
    </div>
  );
};
