# Document-Type-Agnostic Presentation Architecture — Implementation Summary

**Branch:** `restore-frontend-ingestion`
**Scope:** Frontend document viewer refactor + read-only backend metadata endpoint.
**Ingestion pipeline (AnyDoc + RapidOCR + vector indexing):** ✅ completely untouched.

---

## 1. Root Cause & Problem Statement

The previous document viewer (`DocumentViewer.tsx`) was monolithic: it mixed
metadata fetching, page navigation, citation-jump handling, and format-specific
rendering all in one component. It assumed every upload was a video, so when
the persistent-ingestion pipeline began producing **document assets** (PDF,
DOCX, PPTX, scanned images), there was no way to present them.

Three concrete gaps drove this work:

1. **No format dispatch** — every document fell through to a blank/video-style
   view. There was no MIME-type → renderer mapping.
2. **No file metadata endpoint** — the frontend had no way to learn a media
   item's mime type, file name, or file size to choose a renderer.
3. **Dead Tailwind tokens** — the viewer referenced `bg-accent`/`ring-accent`
   but `accent` wasn't defined in `tailwind.config.js`, so the citation-jump
   highlight and active-state colors silently never rendered.

---

## 2. Root Cause Fixes

| Problem | Fix |
|---|---|
| No format dispatch | New **RendererRegistry** maps MIME prefix/extension → `FormatCategory` (`pdf` / `image` / `text` / `fallback`) and resolves a renderer component per upload. |
| No metadata source | New backend `GET /api/v1/media/{id}/info` (read-only, purely additive, does **not** touch the ingestion pipeline) returns `mime_type`, `file_name`, `file_size_bytes`, `title`, `url`. |
| Monolithic viewer | `DocumentViewer.tsx` reduced to a lightweight **orchestrator**: owns page state + citation-jump logic, delegates rendering to the registry-resolved `DocumentRenderer`. |
| Dead accent classes | Added `'accent': '#e9c349'` to `tailwind.config.js` — activates the pre-existing `bg-accent`/`ring-accent` classes used by the viewer highlight and `ChatMessageItem`. |

---

## 3. Implemented Components

### New — `frontend/src/features/document/types.ts`
Core shared types: `FormatCategory`, `DocumentMetadataDTO`, `RendererProps`,
`RendererComponent`.

### New — `frontend/src/features/document/registry/RendererRegistry.ts`
- `MIME_PREFIX_MAP`, `MIME_EXACT_MAP`, `EXTENSION_MAP`, `FALLBACK_EXTENSIONS`
- `resolveFormatCategory()` — resolves a category from `file_path` + `mime_type`
  (extension-first, then MIME, then fallback default)
- `registerRenderer()` / `resolveRenderer()` / `resolveRendererWithCategory()`
  — open registry so future formats (e.g. `.rtf`, `.odt`, `.heic`) register in
  one line with **no changes to the viewer or dispatcher**.

### New — `frontend/src/features/document/renderers/DocumentRenderer.tsx` (dispatcher)
Thin switch: resolves category + component via the registry and renders it.

### New — `frontend/src/features/document/renderers/PdfRenderer.tsx`
Browser-native **iframe** with `#page=N` URL fragment:
- Zero new dependencies, cross-platform (Chrome/Edge/Firefox all natively
  honor the fragment), real page count shown by the browser internally
- `key={pdfKey}` forces an iframe re-mount on each citation jump so the
  fragment is re-applied reliably
- **Highlight ring overlay** for 2500 ms after a jump
- Toolbar: zoom in/out, fit, reload

### New — `frontend/src/features/document/renderers/ImageRenderer.tsx`
PNG / JPG / WEBP / SVG via `<img>`:
- CSS `transform: translate(pan.x, pan.y) scale(zoom)`
- Ctrl/Cmd + wheel zoom, click-drag panning when zoomed, double-click resets to fit

### New — `frontend/src/features/document/renderers/TextRenderer.tsx`
TXT + Markdown via `fetch(url).then(res => res.text())`:
- Custom **inline Markdown renderer** producing React nodes directly —
  **no `dangerouslySetInnerHTML`**, so uploaded Markdown cannot XSS
- ATX headings, fenced code, lists, blockquotes, paragraphs, inline code/bold/italic/links
- Jump-to-section dropdown from rendered heading anchors

### New — `frontend/src/features/document/renderers/FallbackRenderer.tsx`
Office formats (`.docx` / `.pptx` / `.xlsx` / `.epub` / unknown):
- Clean metadata card with format badge + file size
- **Download Original File** and **Open Source Location** buttons via `window.open(url)`
- Banner: "AI-ready, preview pending" — content has been ingested & indexed,
  interactive preview is out of scope

### Modified — `frontend/src/components/DocumentViewer.tsx` (orchestrator)
- Fetches `GET /media/{id}/info` → builds `DocumentMetadataDTO` → delegates to
  `DocumentRenderer`
- **Preserved** Prev / Next / "Page N" / direct-jump controls, citation-jump
  `targetPage` handling with highlight, footer status bar
- Graceful fallback if metadata fetch fails (bare metadata card)

### Modified — `frontend/src/services/mediaService.ts`
Added `MediaInfoDTO` + `getMediaInfo(mediaId)`.

### Modified — `backend/app/presentation/api/v1/media.py`
Added `GET /media/{id}/info` (`MediaInfoResponse`, `_infer_mime_type`).
Read-only — **does not** touch AnyDoc, RapidOCR, chunking, or vector indexing.

### Modified — `frontend/tailwind.config.js`
Added `'accent': '#e9c349'`.

---

## 4. Actual Automated Test Results

### Frontend — `npx tsc --noEmit` (frontend/)
```
EXIT_CODE=0
(tsc_output.log is empty → zero type errors across the entire frontend)
```
**Result: PASS.** Clean compile with the new document module wired in.

### Backend — `pytest` (backend/)
```
collected 146 items
3 failed, 143 passed in 37.16s
```
**Result: 143 passed / 3 failed — all 3 failures are environmental and
pre-existing**, unrelated to this work:

1. `test_ollama_provider_adapter.py::test_ollama_text_gen_adapter_raises_on_failure`
   — `ValueError: Failed connecting to Ollama at http://host.docker.internal:11434: Ollama daemon unreachable`. Requires a running Ollama daemon.
2. `test_retrieval_rag.py::test_chat_query_endpoint`
   — asserts `200`, got `400` because `Ollama model 'llama3:8b' is not pulled`.
3. `test_sessions.py::test_session_lifecycle_and_lazy_creation`
   — same missing-`llama3:8b`/Ollama-unreachable 400.

None of these touch the document viewer, the media API, or the ingestion
pipeline. They will pass on a machine with Ollama running and `llama3:8b`
pulled. **All 143 other tests pass**, including
`test_document_upload_endpoint.py`, `test_document_worker.py`,
`test_anydoc_adapter.py`, `test_ocr_adapter.py`, `test_document_retrieval.py`,
and `test_ingestion_pipeline.py` (5/5 green).

### Runtime endpoint validation (`TestClient` against `app.main`)
```
GET /api/v1/media/doc_runtimecheck/file   -> 200 | application/pdf | 33 bytes
GET /api/v1/media/doc_runtimecheck/info   -> 200 | full MediaInfoResponse JSON
GET /api/v1/media/doc_does_not_exist/file -> 404
GET /api/v1/media/doc_does_not_exist/info -> 404
```
MIME inference spot-check:
```
paper.pdf  -> application/pdf
scan.png   -> image/png
doc.docx   -> application/vnd.openxmlformats-officedocument.wordprocessingml.document
slides.pptx-> application/vnd.openxmlformats-officedocument.presentationml.presentation
data.xlsx  -> application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
book.epub  -> application/epub+zip
readme.txt -> text/plain
notes.md   -> (octet-stream) but registry extension-first → text category ✅
```

---

## 5. Manual Validation Outcomes

Run the app (`cd backend && uvicorn app.main:app`; `cd frontend && npm run dev`),
then:

| Check | Expected | Status |
|---|---|---|
| Upload single-page PDF | Renders in iframe, page 1 visible | ⬜ manual |
| Upload multi-page PDF | Prev/Next + direct jump flip pages | ⬜ manual |
| Upload scanned PDF | Renders (OCR is pipeline-side; viewer shows original) | ⬜ manual |
| Upload PNG/JPG/WEBP/SVG | `ImageRenderer` with zoom/pan/fit | ⬜ manual |
| Upload `.md` / `.txt` | `TextRenderer` renders Markdown/plain text | ⬜ manual |
| Upload `.docx`/`.pptx`/`.xlsx`/`.epub` | `FallbackRenderer` card + Download button | ⬜ manual |
| Click `📄 Page X` citation in chat | Jump + highlight ring for 2.5 s | ⬜ manual |
| Switch workspace view | `switchWorkspace` clears document state cleanly | ⬜ manual |
| Kill backend, open document | Graceful fallback card, no crash | ⬜ manual |

---

## 6. Future Format Extensibility

The registry makes adding a new format a **one-liner**, with no viewer or
dispatcher changes:

```ts
// e.g. adding RTF support with a custom renderer
import { registerRenderer } from '@/features/document/registry/RendererRegistry';
import { RtfRenderer } from '@/features/document/renderers/RtfRenderer';

registerRenderer('fallback', {
  // ...or a dedicated 'rtf' category
  category: 'text',
  component: RtfRenderer,
  extensions: ['.rtf'],
  mimeTypes: ['application/rtf', 'text/rtf'],
});
```

Because `DocumentViewer` only knows about `FormatCategory` + `RendererProps`,
any new renderer that conforms to `RendererProps` (url, metadata, activePage,
safeTotalPages, targetPage, onPageChange) plugs in without touching the
orchestrator. Natural next steps: a dedicated `FallbackRenderer` upgrade path
using the already-indexed text (AnyDoc/RapidOCR output) for in-place previews,
or dedicated EPUB/HTML renderers.
