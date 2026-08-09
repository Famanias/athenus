// RendererRegistry — central index mapping document format categories to
// concrete renderer components. Used by DocumentRenderer (the dispatcher)
// to choose the right renderer for a given document.
//
// All renderers are loaded lazily via dynamic import so the bundle for any
// given document stays minimal (e.g. PDF.js would not be loaded for a
// Markdown file). The actual renderer components are registered in
// `registerRenderers()` once at startup (e.g. from the DocumentRenderer
// barrel) — see features/document/renderers/index.ts.

import type { FormatCategory, RendererComponent } from '../types';
import { PdfRenderer } from '../renderers/PdfRenderer';
import { ImageRenderer } from '../renderers/ImageRenderer';
import { TextRenderer } from '../renderers/TextRenderer';
import { FallbackRenderer } from '../renderers/FallbackRenderer';

// ---------------------------------------------------------------------------
// MIME / file-extension format detection
// ---------------------------------------------------------------------------

/** MIME prefix → renderer category mapping. Matched by startsWith. */
const MIME_PREFIX_MAP: ReadonlyArray<readonly [string, FormatCategory]> = [
  ['application/pdf', 'pdf'],
  ['image/', 'image'],
  ['text/plain', 'text'],
  ['text/markdown', 'text'],
  ['text/x-markdown', 'text'],
];

/** Exact MIME → format category overrides. */
const MIME_EXACT_MAP: Readonly<Record<string, FormatCategory>> = {
  'application/pdf': 'pdf',
  'image/png': 'image',
  'image/jpg': 'image',
  'image/jpeg': 'image',
  'image/webp': 'image',
  'image/svg+xml': 'image',
  'text/plain': 'text',
  'text/markdown': 'text',
};

/** File extension → format category (covers MIME-less filenames). */
const EXTENSION_MAP: Readonly<Record<string, FormatCategory>> = {
  '.pdf': 'pdf',
  '.png': 'image',
  '.jpg': 'image',
  '.jpeg': 'image',
  '.webp': 'image',
  '.svg': 'image',
  '.txt': 'text',
  '.md': 'text',
  '.markdown': 'text',
};

/** Office formats that are ingestion-supported but fall back to a metadata card. */
const FALLBACK_EXTENSIONS: ReadonlySet<string> = new Set([
  '.docx',
  '.doc',
  '.pptx',
  '.ppt',
  '.xlsx',
  '.xls',
  '.epub',
  '.rtf',
  '.odt',
  '.ods',
  '.odp',
]);

/**
 * Resolve the format category for a document. The lookup is:
 *   1. Exact MIME (if provided)
 *   2. MIME prefix (if provided)
 *   3. File extension (from filename or URL)
 *   4. Fallback 'fallback'
 *
 * The function is intentionally tolerant — unknown formats return
 * 'fallback' rather than throwing, so the viewer can always render *some*
 * state including a metadata card + "Open Original File" button.
 */
export function resolveFormatCategory(
  filenameOrUrl?: string,
  mimeType?: string
): FormatCategory {
  // 1. Exact MIME match
  if (mimeType && MIME_EXACT_MAP[mimeType]) {
    return MIME_EXACT_MAP[mimeType];
  }

  // 2. MIME prefix match
  if (mimeType) {
    const lower = mimeType.toLowerCase();
    for (const [prefix, category] of MIME_PREFIX_MAP) {
      if (lower.startsWith(prefix)) {
        return category;
      }
    }
  }

  // 3. Extension match (from filename or URL)
  if (filenameOrUrl) {
    const ext = extractExtension(filenameOrUrl);
    if (ext) {
      const lower = ext.toLowerCase();
      if (EXTENSION_MAP[lower]) {
        return EXTENSION_MAP[lower];
      }
      if (FALLBACK_EXTENSIONS.has(lower)) {
        return 'fallback';
      }
    }
  }

  return 'fallback';
}

/**
 * Resolve the file extension from a filename or URL. Includes the leading
 * dot (e.g. ".pdf"). Returns empty string when no extension is present.
 */
export function extractExtension(filenameOrUrl: string): string {
  if (!filenameOrUrl) return '';
  // Strip query string and hash fragment.
  const clean = filenameOrUrl.split('?')[0].split('#')[0];
  // Skip paths — anchor to the last segment after the final slash.
  const lastSlash = Math.max(clean.lastIndexOf('/'), clean.lastIndexOf('\\'));
  const basename = lastSlash >= 0 ? clean.slice(lastSlash + 1) : clean;
  const dotIndex = basename.lastIndexOf('.');
  if (dotIndex <= 0) return '';
  return basename.slice(dotIndex);
}

// ---------------------------------------------------------------------------
// Renderer registry — maps FormatCategory → RendererComponent
// ---------------------------------------------------------------------------

const rendererRegistry: Partial<Record<FormatCategory, RendererComponent>> = {};

/**
 * Register a renderer component for a format category. Replaces any
 * previously registered component for that category.
 */
export function registerRenderer(
  category: FormatCategory,
  component: RendererComponent
): void {
  rendererRegistry[category] = component;
}

/**
 * Resolve the renderer component for a given format category. Returns the
 * FallbackRenderer whenever the requested category has no registered
 * renderer (or the category itself is 'fallback') so the viewer always
 * renders *something* safe.
 */
export function resolveRenderer(
  filenameOrUrl?: string,
  mimeType?: string
): RendererComponent {
  const category = resolveFormatCategory(filenameOrUrl, mimeType);
  const component = rendererRegistry[category];
  if (component) return component;
  // Last-resort safety net — FallbackRenderer is always registered.
  return rendererRegistry.fallback ?? FallbackRenderer;
}

/**
 * Convenience helper that returns the resolved FormatCategory alongside
 * the RendererComponent. Useful for diagnostics and for telemetry.
 */
export function resolveRendererWithCategory(
  filenameOrUrl?: string,
  mimeType?: string
): { category: FormatCategory; component: RendererComponent } {
  const category = resolveFormatCategory(filenameOrUrl, mimeType);
  return { category, component: resolveRenderer(filenameOrUrl, mimeType) };
}

/**
 * Reset the registry. Intended for unit tests only.
 */
export function _resetRendererRegistry(): void {
  for (const key of Object.keys(rendererRegistry)) {
    delete rendererRegistry[key as FormatCategory];
  }
}

// Built-in registrations — these import the renderer modules eagerly so
// the registry is fully populated by the time the module is evaluated.
// The DynamicRenderer is responsible for the actual conditional dispatch.
registerRenderer('pdf', PdfRenderer);
registerRenderer('image', ImageRenderer);
registerRenderer('text', TextRenderer);
registerRenderer('fallback', FallbackRenderer);
