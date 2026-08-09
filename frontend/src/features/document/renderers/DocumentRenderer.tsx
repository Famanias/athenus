// DocumentRenderer — dispatcher component that resolves the appropriate
// renderer from the RendererRegistry and delegates rendering to it.
//
// The dispatcher is intentionally thin. All renderer-specific behavior
// lives in the renderer components themselves. To add a new format:
//   1. Create a renderer component in renderers/
//   2. Register it in registry/RendererRegistry.ts
//   3. Done — no changes to DocumentViewer or DocumentRenderer required.

'use client';

import React, { useMemo } from 'react';
import { resolveRendererWithCategory } from '../registry/RendererRegistry';
import type { DocumentMetadataDTO, RendererProps } from '../types';

interface DocumentRendererProps {
  metadata: DocumentMetadataDTO;
  activePage: number;
  safeTotalPages: number;
  targetPage: number | null;
  onPageChange: (page: number) => void;
}

export const DocumentRenderer: React.FC<DocumentRendererProps> = ({
  metadata,
  activePage,
  safeTotalPages,
  targetPage,
  onPageChange,
}) => {
  // Resolve renderer once per (metadata.url, metadata.mime_type) change.
  // The renderer is then mounted as long as the document identity is stable.
  const { category, component: RendererComponent } = useMemo(
    () =>
      resolveRendererWithCategory(
        metadata.file_path || metadata.title,
        metadata.mime_type
      ),
    [metadata.file_path, metadata.title, metadata.mime_type]
  );

  const rendererProps: RendererProps = {
    url: metadata.url,
    metadata,
    activePage,
    safeTotalPages,
    targetPage,
    onPageChange,
  };

  return (
    <div
      className="w-full h-full flex flex-col bg-surface-container-lowest"
      data-document-renderer={category}
      data-document-id={metadata.id}
    >
      <RendererComponent {...rendererProps} />
    </div>
  );
};
