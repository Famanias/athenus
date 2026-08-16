'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { Button } from '@/components/ui/Button';
import { getDocumentPages, getMediaInfo, getMediaUrl, type MediaInfoDTO } from '@/services/mediaService';
import { DocumentRenderer } from '@/features/document/renderers/DocumentRenderer';
import type { DocumentMetadataDTO } from '@/features/document/types';

// DocumentViewer — lightweight orchestrator for document-type-agnostic
// presentation. Owns viewer state (active page, target page jump, page
// navigation controls) and delegates the actual rendering to the
// format-specific renderer resolved by the RendererRegistry via
// DocumentRenderer.

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
  const [totalPages, setTotalPages] = useState<number>(1);
  const [loadingInfo, setLoadingInfo] = useState<boolean>(false);
  const [infoError, setInfoError] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const safeTotalPages = useMemo(() => Math.max(1, totalPages), [totalPages]);

  const activePage = useMemo<number>(() => {
    if (typeof currentPage === 'number' && currentPage >= 1 && currentPage <= safeTotalPages) {
      return currentPage;
    }
    return 1;
  }, [currentPage, safeTotalPages]);

  // Fetch file metadata and dynamic page count when the active document changes.
  const fetchMetadata = useCallback(async (mediaId: string) => {
    setLoadingInfo(true);
    setInfoError(null);
    try {
      const [infoRes, pagesRes] = await Promise.allSettled([
        getMediaInfo(mediaId),
        getDocumentPages(mediaId),
      ]);

      if (infoRes.status === 'fulfilled') {
        setMetadata(buildMetadata(infoRes.value, mediaId));
      } else {
        setMetadata({
          id: mediaId,
          title: PLACEHOLDER_TITLE,
          file_path: '',
          media_type: 'document',
          file_size_bytes: 0,
          mime_type: '',
          url: getMediaUrl(mediaId),
        });
      }

      if (pagesRes.status === 'fulfilled' && pagesRes.value.total_pages > 0) {
        setTotalPages(pagesRes.value.total_pages);
      } else {
        setTotalPages(1);
      }
    } catch (err: unknown) {
      setInfoError(
        err instanceof Error ? err.message : 'Failed to load document metadata.'
      );
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
      setTotalPages(1);
    }
  }, [activeDocumentId, fetchMetadata]);

  // React to target page changes triggered by citation clicks.
  useEffect(() => {
    if (
      targetPage !== null &&
      targetPage >= 1 &&
      targetPage <= safeTotalPages &&
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
  }, [targetPage, safeTotalPages]);

  const goToPage = (page: number) => {
    if (page < 1 || page > safeTotalPages) return;
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
            Upload a document in the Uploads tab or select an existing
            document asset from the Library to view it here.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col bg-surface-container-lowest overflow-hidden h-full">
      {/* Header / Document Title Bar */}
      <div className="px-3 py-2 bg-surface-container-low border-b border-outline-variant flex justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-lg">📄</span>
          <h3 className="font-type-light text-xs font-bold text-on-surface truncate">
            {metadata?.title && metadata.title !== PLACEHOLDER_TITLE
              ? metadata.title
              : PLACEHOLDER_TITLE}
          </h3>
        </div>
        {activeDocumentId && (
          <span className="text-[10px] font-mono text-on-surface-variant truncate">
            ID: {activeDocumentId}
          </span>
        )}
      </div>

      {/* Document Renderer (format-agnostic) */}
      <div className="flex-1 overflow-hidden">{renderContent}</div>
    </div>
  );
};
