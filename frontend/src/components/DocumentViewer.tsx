'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { Button } from '@/components/ui/Button';
import { getMediaInfo, getMediaUrl, type MediaInfoDTO } from '@/services/mediaService';
import { DocumentRenderer } from '@/features/document/renderers/DocumentRenderer';
import type { DocumentMetadataDTO } from '@/features/document/types';

// DocumentViewer — lightweight orchestrator for document-type-agnostic
// presentation. Owns viewer state (active page, target page jump, page
// navigation controls) and delegates the actual rendering to the
// format-specific renderer resolved by the RendererRegistry via
// DocumentRenderer.
//
// Behavior preserved from the previous implementation:
//   - Page navigation: Previous Page, Next Page, "Page N of M", direct jump
//   - Auto-scrolls/re-pages to the active target page when `targetPage`
//     changes (triggered by clicking a `📄 Page X` citation badge in chat)
//   - Highlights the target page briefly after navigation
//
// New behavior:
//   - Fetches file metadata via GET /media/{id}/info (mime type, file size,
//     filename) to drive renderer dispatch
//   - Resolves the appropriate renderer from the RendererRegistry
//   - Renders the actual file binary (PDF / image / text / fallback card):
//       • PDFs are rendered in a browser-native iframe (`#page=N` fragment)
//       • Images are rendered via <img> with zoom/pan controls
//       • Text/Markdown is fetched and rendered with an inline Markdown
//         renderer (no innerHTML)
//       • Office formats (.docx/.pptx/.xlsx/.epub) fall back to a clean
//         metadata card with a "Download Original File" button

const PLACEHOLDER_TITLE = 'Document Reader';
const HIGHLIGHT_DURATION_MS = 2500;

function buildMetadata(info: MediaInfoDTO, mediaId: string): DocumentMetadataDTO {
  return {
    id: info.media_id || mediaId,
    title: info.title || info.file_name || 'Untitled Document',
    file_path: info.file_path || '',
    media_type: info.media_type || 'document',
    file_size_bytes: info.file_size_bytes || 0,
    mime_type: info.mime_type || '',
    url: getMediaUrl(info.media_id || mediaId),
    file_format: info.file_name,
  };
}

export const DocumentViewer: React.FC = () => {
  const {
    activeDocumentId,
    currentPage,
    targetPage,
    setCurrentPage,
    setTargetPage,
  } = useAppStore();

  const [pageInput, setPageInput] = useState<string>('');
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const [metadata, setMetadata] = useState<DocumentMetadataDTO | null>(null);
  const [loadingInfo, setLoadingInfo] = useState<boolean>(false);
  const [infoError, setInfoError] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // The orchestrator does not know the document's actual page count from
  // the backend metadata. The browser-native PDF viewer displays the real
  // page count internally; the orchestrator only needs an upper bound for
  // citation-jump validation. We use 1 as the safe default — renderers
  // handle page navigation internally regardless of this value.
  const safeTotalPages = 1;

  const activePage = useMemo<number>(() => {
    if (typeof currentPage === 'number' && currentPage >= 1) {
      return currentPage;
    }
    return 1;
  }, [currentPage]);

  // Fetch file metadata when the active document changes.
  const fetchMetadata = useCallback(async (mediaId: string) => {
    setLoadingInfo(true);
    setInfoError(null);
    try {
      const info = await getMediaInfo(mediaId);
      setMetadata(buildMetadata(info, mediaId));
    } catch (err: unknown) {
      // Soft fallback — keep the viewer usable with bare metadata so the
      // FallbackRenderer can still render its metadata card.
      setInfoError(
        err instanceof Error ? err.message : 'Failed to load document metadata.'
      );
      setMetadata({
        id: mediaId,
        title: PLACEHOLDER_TITLE,
        file_path: '',
        media_type: 'document',
        file_size_bytes: 0,
        mime_type: '',
        url: getMediaUrl(mediaId),
      });
    } finally {
      setLoadingInfo(false);
    }
  }, []);

  useEffect(() => {
    if (activeDocumentId) {
      fetchMetadata(activeDocumentId);
    } else {
      setMetadata(null);
      setInfoError(null);
    }
  }, [activeDocumentId, fetchMetadata]);

  // React to target page changes triggered by citation clicks.
  useEffect(() => {
    if (
      targetPage !== null &&
      targetPage >= 1 &&
      targetPage !== activePage
    ) {
      setCurrentPage(targetPage);
      setHighlightPage(targetPage);
      if (highlightTimeoutRef.current) {
        clearTimeout(highlightTimeoutRef.current);
      }
      highlightTimeoutRef.current = setTimeout(() => {
        setHighlightPage(null);
      }, HIGHLIGHT_DURATION_MS);
      setTargetPage(null);
    }
    return () => {
      if (highlightTimeoutRef.current) {
        clearTimeout(highlightTimeoutRef.current);
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targetPage]);

  const goToPage = (page: number) => {
    if (page < 1) return;
    setCurrentPage(page);
    setHighlightPage(page);
    if (highlightTimeoutRef.current) {
      clearTimeout(highlightTimeoutRef.current);
    }
    highlightTimeoutRef.current = setTimeout(() => {
      setHighlightPage(null);
    }, HIGHLIGHT_DURATION_MS);
  };

  const handlePrev = () => goToPage(activePage - 1);
  const handleNext = () => goToPage(activePage + 1);

  const handleJump = (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = parseInt(pageInput, 10);
    if (!isNaN(parsed)) {
      goToPage(parsed);
      setPageInput('');
    }
  };

  // Active render content — handles loading, error, and ready states.
  let renderContent: React.ReactNode;
  if (loadingInfo && !metadata) {
    renderContent = (
      <div className="flex-1 flex items-center justify-center">
        <span className="text-xs text-on-surface-variant font-mono animate-pulse">
          Loading document metadata…
        </span>
      </div>
    );
  } else if (metadata) {
    renderContent = (
      <DocumentRenderer
        metadata={metadata}
        activePage={activePage}
        safeTotalPages={safeTotalPages}
        targetPage={targetPage}
        onPageChange={goToPage}
      />
    );
  } else {
    renderContent = (
      <div className="flex-1 flex items-center justify-center p-12">
        <div className="max-w-md text-center space-y-3">
          <span className="text-5xl block">📄</span>
          <h4 className="font-bold text-sm text-on-surface">
            No document selected
          </h4>
          <p className="text-xs text-on-surface-variant">
            Upload a document in the Pipelines tab or select an existing
            document asset from the Library to view it here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-surface-container-lowest overflow-hidden h-full">
      {/* Header / Toolbar */}
      <div className="p-3 bg-surface-container-low border-b border-outline-variant flex flex-wrap justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <span className="text-2xl">📄</span>
          <div className="flex flex-col min-w-0">
            <h3 className="font-type-light text-sm font-bold text-on-surface truncate">
              {metadata?.title && metadata.title !== PLACEHOLDER_TITLE
                ? metadata.title
                : PLACEHOLDER_TITLE}
            </h3>
            <span className="text-[11px] font-mono text-on-surface-variant truncate">
              {activeDocumentId
                ? `Document ID: ${activeDocumentId}`
                : 'No document selected'}
              {metadata?.mime_type && ` • ${metadata.mime_type}`}
            </span>
          </div>
        </div>

        {/* Page Navigation Controls */}
        <div className="flex items-center gap-2 flex-wrap">
          <Button
            variant="secondary"
            size="sm"
            disabled={activePage <= 1}
            onClick={handlePrev}
          >
            ← Prev
          </Button>
          <span className="font-mono text-xs text-on-surface px-2">
            Page <span className="text-secondary font-bold">{activePage}</span>
          </span>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleNext}
          >
            Next →
          </Button>

          {/* Direct Jump Input */}
          <form onSubmit={handleJump} className="flex items-center gap-1 ml-2">
            <input
              type="number"
              min={1}
              value={pageInput}
              onChange={(e) => setPageInput(e.target.value)}
              placeholder="Jump…"
              className="w-20 bg-surface-container border border-outline-variant rounded p-1 text-xs text-on-surface focus:border-secondary focus:outline-none font-mono"
            />
            <Button variant="primary" size="sm" type="submit">
              Go
            </Button>
          </form>
        </div>
      </div>

      {/* Document Renderer (format-agnostic) */}
      <div className="flex-1 overflow-hidden">{renderContent}</div>

      {/* Footer status bar */}
      <div className="p-2 bg-surface-container-low border-t border-outline-variant text-[10px] font-mono text-on-surface-variant/60 flex justify-between items-center shrink-0 gap-3">
        <span>📄 Document Reader</span>
        {infoError && (
          <span className="text-rose-400 truncate max-w-xs" title={infoError}>
            ⚠ metadata unavailable — showing fallback
          </span>
        )}
        <span>
          {highlightPage === activePage && highlightPage !== null
            ? `📍 Jumped to Page ${activePage}`
            : `Active page: ${activePage}`}
        </span>
      </div>
    </div>
  );
};
