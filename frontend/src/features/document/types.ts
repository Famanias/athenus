// Document Renderer — shared types for the document-type-agnostic
// presentation architecture. This module is concerned strictly with human
// visual presentation (PDF, image, text, fallback). It is intentionally
// decoupled from the AnyDoc + RapidOCR ingestion pipeline and the
// 384-d vector embedding / Qdrant indexing path.

import type { ComponentType } from 'react';

/**
 * Coarse-grained renderer categories. The registry maps MIME types and file
 * extensions to one of these categories and each category maps to a single
 * renderer component.
 *
 * Keep this enum small — adding a new category is intentional, adding a new
 * renderer for an existing category is routine.
 */
export type FormatCategory = 'pdf' | 'image' | 'text' | 'fallback';

/**
 * Normalized document metadata passed from the orchestrator to the chosen
 * renderer. The orchestrator is responsible for fetching this from the
 * backend; the renderer should treat it as read-only.
 */
export interface DocumentMetadataDTO {
  /** Backend media/document id (e.g. "doc_abc12345"). */
  id: string;
  /** Human-readable title (typically the original filename). */
  title: string;
  /** Absolute file path on the backend (informational only). */
  file_path: string;
  /** Backend media_type string (e.g. "document", "video", "audio"). */
  media_type: string;
  /** File size in bytes. */
  file_size_bytes: number;
  /** MIME type reported by the upload (e.g. "application/pdf"). */
  mime_type: string;
  /** Download URL produced by mediaService.getMediaUrl(). */
  url: string;
  /** Optional pre-known file format hint (e.g. ".pdf", ".md"). */
  file_format?: string;
}

/**
 * Common contract every concrete renderer must implement. The orchestrator
 * wires stateful caller concerns (active page, target page, total pages,
 * page change callbacks) through these props.
 *
 * Individual renderers may accept additional props of their own.
 */
export interface RendererProps {
  /** Resolved URL the renderer should load (typically via getMediaUrl). */
  url: string;
  /** Document metadata (title, mime, size, etc.). */
  metadata: DocumentMetadataDTO;
  /** 1-indexed active page when applicable. May be null for non-paginated formats. */
  activePage: number;
  /** Total pages for the document when known. Falls back to 1. */
  safeTotalPages: number;
  /** Target page set by external citation jump — null when no jump pending. */
  targetPage: number | null;
  /** Notify the orchestrator that the user navigated to a new page. */
  onPageChange: (page: number) => void;
}

export type RendererComponent = ComponentType<RendererProps>;
