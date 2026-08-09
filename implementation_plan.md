# Implementation Plan — Refined Document-Type-Agnostic Presentation Architecture

Build an extensible **Document-Type-Agnostic Presentation Architecture** for Athenus so that uploaded source documents (`.pdf`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`, `.txt`, `.md`, etc.) are rendered visually using a modular **Renderer Registry**, completely decoupled from AI ingestion processing (`AnyDoc` + `RapidOCR`).

---

## 1. Architectural Principles & Reuse of Existing Codebase

### 1. Ingestion Support vs. Presentation Support
A document can be **100% usable by the AI agent** for RAG search, flashcards, and quizzes even when native visual browser preview is not implemented. Ingestion capability is distinct from visual presentation.

### 2. Reuse of Existing Codebase Infrastructure
Before creating new abstractions, the implementation will reuse existing Athenus utilities, types, API clients, and UI components:
- **`mediaService.ts`**: Reuses existing `getMediaUrl(mediaId)` endpoint helper.
- **`useAppStore.ts`**: Reuses existing `activeDocumentId`, `currentPage`, `targetPage`, `setCurrentPage`, `setTargetPage` state primitives.
- **`Button.tsx`**: Reuses existing UI design system buttons.
- **Upload Validation Alignment**: Aligns image & document format detection with actual upload filters in `UploadDropzone.tsx` (`.pdf`, `.docx`, `.pptx`, `.xlsx`, `.epub`, `.txt`, `.md`, `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`).

```text
                               Original Source Document File
                                             │
               ┌─────────────────────────────┴─────────────────────────────┐
               ▼                                                           ▼
        Processing Path                                             Presentation Path
      (AI RAG Knowledge)                                          (Human Visual Reader)
               │                                                           │
      AnyDoc + RapidOCR                                           Generic DocumentViewer
               │                                                           │
       Markdown & Pages                                            Renderer Registry
               │                                                           │
        Semantic Chunker                                   ┌───────────────┼───────────────┐
               │                                           ▼               ▼               ▼
 384-d Vector Embedding (bge-small-en-v1.5)            PdfRenderer    ImageRenderer     TextRenderer
               │                                       (PDF Binary)   (PNG/JPG/SVG)    (TXT/MD Source)
    Qdrant & Knowledge Graph                                               │
               │                                                           ▼
       RAG Chat & Citations                                        FallbackRenderer
                                                                  (Office/Metadata +
                                                                   "Open Original File")
```

---

## 2. Component Responsibility & Renderer Registry Design

### Component Breakdown
- **`DocumentViewer.tsx` (Viewer Orchestrator)**: Manages viewer state (`activeDocumentId`, `activePage`, `targetPage`), fetches file metadata/URL via `getMediaUrl()`, and renders top navigation controls (page counter, jump input).
- **`DocumentRenderer.tsx` (Dispatcher)**: Queries the `RendererRegistry` for the appropriate renderer based on MIME type and file extension.
- **`RendererRegistry.ts` (Central Registry)**: Maps format categories (`PDF`, `IMAGE`, `TEXT`, `FALLBACK`) to specific renderer components.

```text
Source Document Metadata
           │
           ▼
    RendererRegistry
           ├── PDF      → PdfRenderer (Verified renderer implementation; flexible engine choice)
           ├── IMAGE    → ImageRenderer (PNG, JPG, JPEG, WEBP, SVG with zoom/fit)
           ├── TEXT     → TextRenderer (Raw TXT & Markdown source viewer)
           └── FALLBACK → FallbackRenderer (Office docs / metadata card + file download)
```

---

## 3. Detailed Renderer Specifications

### 1. `PdfRenderer`
- Renders original PDF binary loaded from backend `getMediaUrl(mediaId)`.
- Flexible implementation choice: uses the most reliable, cross-platform verified rendering approach in Tauri/browser environment (e.g. iframe, object Blob URL, or pdfjs).
- Implements programmatic page navigation and scrolling to target page.
- Handles citation jumps (`📄 Page X`) reliably by updating view offset and applying a temporary highlight ring overlay.
- Handles single-page, multi-page, scanned PDFs, and unusual page dimensions.

### 2. `ImageRenderer`
- Renders image assets consistent with upload support (`.png`, `.jpg`, `.jpeg`, `.webp`, `.svg`).
- Provides fit-to-screen, zoom-in/out, and pan controls.

### 3. `TextRenderer`
- Renders plain text (`.txt`) and Markdown (`.md`) files.
- Provides clean typography, syntax formatting, and section anchor jumping.

### 4. `FallbackRenderer`
- Used when a file format is accepted by Athenus ingestion (e.g. `.docx`, `.pptx`, `.xlsx`, `.epub`), but native visual browser preview is not currently implemented.
- Displays a clean card with file metadata, size, ingestion status, and a **"Download Original File" / "Open Source Location"** button.
- Explicitly informs the user:
  > *"This document format is fully indexed and usable by the Athenus AI agent, but visual browser preview is not currently supported for this file type."*

---

## 4. Proposed File Changes

### Frontend Architecture

#### [NEW] `frontend/src/features/document/types.ts`
- `FormatCategory`: `'pdf' | 'image' | 'text' | 'fallback'`
- `DocumentMetadataDTO`: `id`, `title`, `file_path`, `media_type`, `file_size_bytes`, `mime_type`, `url`
- `RendererProps`: `url`, `metadata`, `activePage`, `safeTotalPages`, `targetPage`, `onPageChange`

#### [NEW] `frontend/src/features/document/registry/RendererRegistry.ts`
- Format detection & registry resolver: `resolveRenderer(filenameOrUrl?: string, mimeType?: string): RendererComponent`

#### [NEW] `frontend/src/features/document/renderers/PdfRenderer.tsx`
- PDF renderer with verified programmatic page jumping & citation highlight ring.

#### [NEW] `frontend/src/features/document/renderers/ImageRenderer.tsx`
- Image renderer for `.png`, `.jpg`, `.jpeg`, `.webp`, `.svg` with zoom & fit controls.

#### [NEW] `frontend/src/features/document/renderers/TextRenderer.tsx`
- Source code / Markdown / plain text renderer.

#### [NEW] `frontend/src/features/document/renderers/FallbackRenderer.tsx`
- Ingestion-supported fallback renderer with metadata card and source file download/open button.

#### [NEW] `frontend/src/features/document/renderers/DocumentRenderer.tsx`
- Dispatcher component that queries `RendererRegistry`.

#### [MODIFY] `frontend/src/components/DocumentViewer.tsx`
- Refactor top-level viewer container to use state orchestration, consume `getMediaUrl()`, and mount `<DocumentRenderer />`.

---

## 5. Verification & Testing Matrix

### Automated Verification
- `npx tsc --noEmit` in `frontend/` (report actual execution result).
- `python -m pytest` in `backend/` (report actual executed test count and pass/fail summary).

### Real-World Manual Test Suite

| Category | Test Case | Description & Expected Result |
| :--- | :--- | :--- |
| **PDF Rendering** | Single-page & Multi-page PDF | Native PDF displayed cleanly; page controls update seamlessly. |
| **PDF Edge Cases** | Large PDF (100+ pages) | Page jumping and scrolling performant without memory leak. |
| **Scanned PDF** | Scanned PDF file | Rendered visually as exact original scanned pages; independent of RapidOCR text extraction. |
| **Visual Fidelity** | PDF with tables & diagrams | Preserves original layout, typography, and embedded figures. |
| **Images** | High-res PNG / JPG / WEBP / SVG | Displayed centered in `ImageRenderer` with zoom controls. |
| **Text / Markdown** | `.md` / `.txt` file | Displayed in `TextRenderer` with formatted syntax. |
| **Office Documents** | `.docx` / `.pptx` file | `FallbackRenderer` displays metadata card + "Download Original File" button. AI chat operates on indexed content. |
| **Citation Jumps** | Citation click (`📄 Page 7`) | Viewer lands on Page 7 with brief accent highlight ring. |
| **Boundary Tests** | Citation to Page 1 / Last Page / Invalid Page | Graceful handling without crash or blank screen. |
| **Error Resiliency** | Missing file / Backend down | Displays clean error state without crashing application shell. |
| **Video Parity** | Toggle to Video Workspace | Video player loads and plays without regression. |

---

## 6. Extensibility Strategy

To add visual support for a new format (e.g. EPUB, CAD) in the future:
1. Create a renderer component in `renderers/` (e.g. `EpubRenderer.tsx`).
2. Register the format mapping in `RendererRegistry.ts`.
3. **Minimize and avoid modifications to core `DocumentViewer.tsx` orchestrator where possible.**
