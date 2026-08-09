'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { Button } from '@/components/ui/Button';

// DocumentViewer — clean, responsive reader for PDF/Markdown document content.
//
// Features:
// - Page navigation: Previous Page, Next Page, "Page N of M", direct jump input
// - Auto-scrolls to the active target page when `targetPage` state changes
//   (triggered by clicking a `📄 Page X` citation badge in chat)
// - Highlights the target section briefly after navigation
// - Reads document metadata from `useAppStore` (activeDocumentId, currentPage, targetPage)

interface PageSection {
  id: string;
  pageNumber: number;
  title?: string;
  body: string;
}

interface DocumentViewerProps {
  // Total number of pages in the loaded document. Falls back to a sensible
  // default so the viewer still renders for documents with no extracted metadata.
  totalPages?: number;
  // Optional page-by-page content (rendered as Markdown-style blocks).
  // When omitted, the viewer still shows page navigation & placeholders.
  pageSections?: PageSection[];
}

const DEFAULT_TOTAL_PAGES = 1;
const PLACEHOLDER_TITLE = 'Document Reader';

export const DocumentViewer: React.FC<DocumentViewerProps> = ({
  totalPages = DEFAULT_TOTAL_PAGES,
  pageSections,
}) => {
  const {
    activeDocumentId,
    currentPage,
    targetPage,
    setCurrentPage,
    setTargetPage,
  } = useAppStore();

  const [pageInput, setPageInput] = useState<string>('');
  const [highlightPage, setHighlightPage] = useState<number | null>(null);
  const highlightTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const safeTotalPages = useMemo(
    () => (totalPages && totalPages > 0 ? totalPages : DEFAULT_TOTAL_PAGES),
    [totalPages]
  );

  const activePage = useMemo<number>(() => {
    if (typeof currentPage === 'number' && currentPage >= 1 && currentPage <= safeTotalPages) {
      return currentPage;
    }
    return 1;
  }, [currentPage, safeTotalPages]);

  // React to target page changes triggered by citation clicks.
  useEffect(() => {
    if (
      targetPage !== null &&
      targetPage >= 1 &&
      targetPage <= safeTotalPages &&
      targetPage !== activePage
    ) {
      setCurrentPage(targetPage);
      // Highlight the target page briefly so the user sees the jump landed.
      setHighlightPage(targetPage);
      if (highlightTimeoutRef.current) {
        clearTimeout(highlightTimeoutRef.current);
      }
      highlightTimeoutRef.current = setTimeout(() => {
        setHighlightPage(null);
      }, 2500);
      // Clear the target page so a stale value doesn't re-trigger.
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
    }, 2500);
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

  const currentSection =
    pageSections?.find((p) => p.pageNumber === activePage) ?? null;

  return (
    <div className="flex-1 flex flex-col bg-surface-container-lowest overflow-hidden h-full">
      {/* Header / Toolbar */}
      <div className="p-3 bg-surface-container-low border-b border-outline-variant flex flex-wrap justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-2xl">📄</span>
          <div className="flex flex-col">
            <h3 className="font-type-light text-sm font-bold text-on-surface">
              {PLACEHOLDER_TITLE}
            </h3>
            <span className="text-[11px] font-mono text-on-surface-variant">
              {activeDocumentId
                ? `Document ID: ${activeDocumentId}`
                : 'No document selected'}
            </span>
          </div>
        </div>

        {/* Page Navigation Controls */}
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={activePage <= 1}
            onClick={handlePrev}
          >
            ← Prev
          </Button>
          <span className="font-mono text-xs text-on-surface px-2">
            Page <span className="text-secondary font-bold">{activePage}</span> of{' '}
            <span className="text-on-surface font-bold">{safeTotalPages}</span>
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={activePage >= safeTotalPages}
            onClick={handleNext}
          >
            Next →
          </Button>

          {/* Direct Jump Input */}
          <form onSubmit={handleJump} className="flex items-center gap-1 ml-2">
            <input
              type="number"
              min={1}
              max={safeTotalPages}
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

      {/* Document Page Content Area */}
      <div className="flex-1 overflow-y-auto custom-scrollbar p-6">
        {currentSection ? (
          <div
            className={`max-w-3xl mx-auto p-6 bg-surface-container border rounded-md shadow-sm transition-all ${
              highlightPage === activePage
                ? 'border-accent ring-2 ring-accent/40 bg-accent/10'
                : 'border-outline-variant'
            }`}
          >
            {currentSection.title && (
              <h2 className="text-lg font-bold text-on-surface mb-3 border-b border-outline-variant/40 pb-2">
                {currentSection.title}
              </h2>
            )}
            <p className="text-sm leading-relaxed text-on-surface whitespace-pre-wrap">
              {currentSection.body}
            </p>
            <div className="mt-6 pt-3 border-t border-outline-variant/40 text-[10px] font-mono text-on-surface-variant/60 flex justify-between">
              <span>Page {activePage} of {safeTotalPages}</span>
              <span>Document ID: {activeDocumentId ?? 'N/A'}</span>
            </div>
          </div>
        ) : (
          <div
            className={`max-w-3xl mx-auto p-12 border border-dashed rounded-md text-center space-y-3 transition-all ${
              highlightPage === activePage
                ? 'border-accent bg-accent/10 ring-2 ring-accent/40'
                : 'border-outline-variant bg-surface-container-low'
            }`}
          >
            <span className="text-5xl block">📄</span>
            <h4 className="font-bold text-sm text-on-surface">
              Viewing Page {activePage} of {safeTotalPages}
            </h4>
            <p className="text-xs text-on-surface-variant max-w-sm mx-auto">
              Document content for this page is not yet loaded. Navigate to other
              pages, or click a <code className="font-mono">📄 Page X</code>{' '}
              citation badge in chat to jump directly to a cited page.
            </p>
          </div>
        )}
      </div>

      {/* Footer status bar */}
      <div className="p-2 bg-surface-container-low border-t border-outline-variant text-[10px] font-mono text-on-surface-variant/60 flex justify-between items-center shrink-0">
        <span>📄 Document Reader</span>
        <span>
          {activePage === safeTotalPages
            ? 'End of document'
            : `${safeTotalPages - activePage} page(s) remaining`}
        </span>
      </div>
    </div>
  );
};
