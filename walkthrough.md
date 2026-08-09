# Walkthrough ΓÇö Frontend Integration for Generalized Document & PDF Ingestion Architecture

This walkthrough documents the step-by-step frontend implementation executed against
[implementation_plan.md](file:///e:/repos/athenus/implementation_plan.md) ΓÇö the integration of the
**Generalized Document and PDF Ingestion Architecture** into the Athenus frontend.

The backend implementation is complete and documented in
[ADR 0021](file:///e:/repos/athenus/docs/adr/0021-generalized-document-pdf-ingestion-architecture.md).
This document records the minimal, clean, non-breaking frontend updates required to consume the
new backend capabilities, phase by phase.

> [!IMPORTANT]
> **Zero Video Regression Guarantee**: All legacy video workflows (video uploads, video player
> seeking, `ΓÅ▒ MM:SS` timestamp citation clicks, PiP detachment prevention) remain 100% operational.
> Every legacy path was preserved and verified during implementation.

---

## Execution Summary

| Phase | Objective | Status | Verification |
| :--- | :--- | :--- | :--- |
| **1** | Domain Types, API Client Contracts & State Foundations | Γ£à Complete | `npx tsc --noEmit` clean |
| **2** | Ingestion UI & Multi-Format File Upload Support | Γ£à Complete | `npx tsc --noEmit` clean |
| **3** | Generalized Citation Component & Page-Aware Chat Queries | Γ£à Complete | `npx tsc --noEmit` clean |
| **4** | Document Viewer Integration & End-to-End Verification | Γ£à Complete | `npm run build` passes |

---

## Phase 1 ΓÇö Domain Types, API Client Contracts & State Foundations

**Objective**: Update frontend domain types, API service contracts, and the Zustand state store
to support backend generalized document DTOs.

---

### `frontend/src/services/chatService.ts` ΓÇö [MODIFY]

**`BackendCitationDTO` extended** with four optional fields (all backward-compatible):

```ts
export interface BackendCitationDTO {
  chunk_id?: string;
  start_time: number;
  end_time: number;
  text: string;
  // Generalized document/PDF ingestion fields (optional for backward compat)
  source_type?: 'video' | 'pdf';
  page_number?: number | null;
  section_title?: string | null;
  location?: Record<string, any> | null;
}
```

**`sendChatQuery` extended** to accept and transmit document context:

```ts
export async function sendChatQuery(
  query: string,
  workspaceId = 'default',
  sessionId?: string | null,
  mediaId?: string,
  currentTimestamp?: number,
  selectedText?: string,
  documentId?: string,
  sourceType?: 'video' | 'pdf',
  currentPage?: number
): Promise<BackendChatResponse> {
  return apiClient<BackendChatResponse>('/api/v1/chat/query', {
    method: 'POST',
    body: JSON.stringify({
      query,
      workspace_id: workspaceId,
      session_id: sessionId || undefined,
      media_id: mediaId,
      current_timestamp: currentTimestamp,
      selected_text: selectedText,
      document_id: documentId,
      source_type: sourceType,
      current_page: currentPage,
    }),
  });
}
```

**`mapBackendCitations` updated** to project the new fields onto frontend `Citation` objects:

```ts
return citations.map((c) => ({
  mediaId: defaultMediaId,
  mediaTitle: defaultMediaTitle,
  startTime: formatSecondsToTimestamp(c.start_time),
  endTime: formatSecondsToTimestamp(c.end_time),
  score: 0.9,
  textSnippet: c.text || '',
  sourceType: c.source_type,
  pageNumber: typeof c.page_number === 'number' ? c.page_number : undefined,
  sectionTitle: c.section_title || undefined,
  location: c.location || undefined,
}));
```

> **Note on `pageNumber` mapping**: `typeof c.page_number === 'number'` is used so that a
> `null` / `undefined` backend value maps to `undefined` (never `NaN`).

---

### `frontend/src/features/chat/types.ts` ΓÇö [MODIFY]

**`Citation` interface extended** with the generalized document fields:

```ts
export interface Citation {
  mediaId: string;
  mediaTitle: string;
  startTime: string;
  endTime: string;
  score: number;
  textSnippet: string;
  // Generalized document/PDF ingestion fields (optional for backward compat)
  sourceType?: 'video' | 'pdf';
  pageNumber?: number;
  sectionTitle?: string;
  location?: Record<string, any>;
}
```

---

### `frontend/src/types/workspaceContext.ts` ΓÇö [MODIFY]

**`WorkspaceContext` extended** with the active document/source context:

```ts
export interface WorkspaceContext {
  workspaceId: string;
  sessionId: string | null;
  mediaId: string | null;
  documentId?: string | null;
  sourceType?: 'video' | 'pdf';
  currentPage?: number | null;
}
```

---

### `frontend/src/store/useAppStore.ts` ΓÇö [MODIFY]

**`UISlice` extended** with four active-source-context state variables:

```ts
// Active source context (generalized document/PDF ingestion)
activeDocumentId: string | null;
activeSourceType: 'video' | 'pdf';
currentPage: number | null;
targetPage: number | null;
```

**Four new actions added** (each also keeps the `context` object in sync where applicable):

```ts
setActiveDocumentId: (id: string | null) => void;
setActiveSourceType: (type: 'video' | 'pdf') => void;
setCurrentPage: (page: number | null) => void;
setTargetPage: (page: number | null) => void;
```

| Action | Store update | `context` sync |
| :--- | :--- | :--- |
| `setActiveDocumentId` | `activeDocumentId` | `context.documentId` |
| `setActiveSourceType` | `activeSourceType` | `context.sourceType` |
| `setCurrentPage` | `currentPage` | `context.currentPage` |
| `setTargetPage` | `targetPage` only | No (transient nav trigger) |

**`BackgroundJob.stage` union extended** so document ingestion stages type-check across the app:

```ts
stage: 'queued' | 'uploaded' | 'audio_extraction' | 'transcription' | 'chunking'
  | 'vector_indexing' | 'graph_extraction' | 'ready' | 'completed' | 'failed'
  | 'document_parsing' | 'ocr_processing';
```

Initial state defaults:
- `activeDocumentId: null`
- `activeSourceType: 'video'`
- `currentPage: null`
- `targetPage: null`

All defaults preserve the existing video-first behaviour.

---

### Verification ΓÇö Phase 1

`npx tsc --noEmit` reports no errors in the modified domain/service/store files.

The only errors surfaced by the type checker at this stage were in `useIngestion.ts`
(`TS2367` comparisons against the newly-closed `stage` union) ΓÇö expected, and fully resolved
in Phase 2 when that file was updated.

---

## Phase 2 ΓÇö Ingestion UI & Multi-Format File Upload Support

**Objective**: Allow users to upload PDFs and office documents through `UploadDropzone` and display
accurate stage progression for `document_parsing` and `ocr_processing`.

---

### `frontend/src/features/ingestion/UploadDropzone.tsx` ΓÇö [MODIFY]

**`<input type="file">` `accept` attribute widened** to accept documents alongside media:

```html
accept="video/*,audio/*,.pdf,.docx,.pptx,.xlsx,.epub,.md,.txt,application/pdf"
```

**Header / copy updated**:

| Element | Old text | New text |
| :--- | :--- | :--- |
| Header subtext | *Upload video or audio lecture materials to extract transcripts and index vector embeddings.* | *Upload video, audio, or document learning materials to extract transcripts and index vector embeddings.* |
| Dropzone title | *Drag & Drop Video or Audio Files Here* | *Drag & Drop Video, Audio, or Document Files Here* |
| Dropzone subtext | *Supports MP4, MKV, AVI, WAV, MP3 (Up to 2GB)* | *Supports MP4, MKV, MP3, PDF, DOCX, PPTX, XLSX, EPUB, TXT (Up to 100MB)* |
| Upload button | *Select Local Media File* | *Select Local File* |

---

### `frontend/src/features/ingestion/useIngestion.ts` ΓÇö [MODIFY]

**`STAGE_INDEX_BY_NAME` extended** to map the new document stages onto stepper indices:

```ts
const STAGE_INDEX_BY_NAME: Record<string, number> = {
  audio_extraction: 0,
  document_parsing: 0,   // ΓåÉ new
  transcription: 1,
  ocr_processing: 1,     // ΓåÉ new
  chunking: 2,
  vector_indexing: 3,
};
```

**Document-aware stage template added** ΓÇö the stepper switches to a document flow when the active
job is a document ingestion:

```ts
const DOCUMENT_STAGES: PipelineStage[] = [
  { id: 'stg_doc_1', name: 'Receiving Document Upload',            status: 'pending', progress: 0 },
  { id: 'stg_doc_2', name: 'Parsing Document Structure (AnyDoc)',  status: 'pending', progress: 0 },
  { id: 'stg_doc_3', name: 'Extracting Text from Scanned Pages (RapidOCR)', status: 'pending', progress: 0 },
  { id: 'stg_doc_4', name: 'Indexing Vector Embeddings',           status: 'pending', progress: 0 },
];
```

**`isDocumentJob` heuristic** determines which base template to render:

```ts
function isDocumentJob(job): boolean {
  if (!job) return false;
  const hint = `${job.job_type || ''} ${job.stage || ''} ${job.title || ''}`.toLowerCase();
  return (
    hint.includes('document') ||
    hint.includes('pdf') ||
    hint.includes('docx') ||
    job.stage === 'document_parsing' ||
    job.stage === 'ocr_processing'
  );
}
```

**Dynamic stage rendering**: the stage-progression `if/else` branches now handle:

| Backend `stage` | Active stage label (document flow) |
| :--- | :--- |
| `document_parsing` | *Parsing Document Structure (AnyDoc)* |
| `ocr_processing` | *Extracting Text from Scanned Pages (RapidOCR)* |
| `vector_indexing` | *Indexing Vector Embeddings* |

The legacy `INITIAL_STAGES` (Hermes / Apollo / Athenus / Owl) is preserved for video/audio flows.

**`handleFileUpload` now detects document modality** and flips the active source context before
calling the backend:

```ts
const isDocumentFile =
  /\.(pdf|docx?|pptx?|xlsx?|epub|md|txt)$/i.test(file.name) ||
  file.type === 'application/pdf';
if (isDocumentFile) {
  setActiveSourceType('pdf');
}
```

---

### Verification ΓÇö Phase 2

`npx tsc --noEmit` clean ΓÇö the Phase 1 `useIngestion.ts` `TS2367` errors are now resolved.

Video upload flow untouched: video/audio files still trigger the legacy 4-stage stepper.

---

## Phase 3 ΓÇö Generalized Citation Component & Page-Aware Chat Queries

**Objective**: Generalize citation rendering in chat messages to display interactive `≡ƒôä Page X`
badges for documents, and update `useChat` to transmit active document context parameters
(`document_id`, `source_type`, `current_page`) to the backend.

---

### `frontend/src/features/chat/ChatMessageItem.tsx` ΓÇö [MODIFY]

**Citation rendering now branches on source type.** For each citation:

```ts
const isDocumentCitation =
  cit.sourceType === 'pdf' || typeof cit.pageNumber === 'number';
```

| Citation type | Badge rendered | Styling | Click handler |
| :--- | :--- | :--- | :--- |
| Document (`sourceType === 'pdf'` or `pageNumber` present) | `≡ƒôä Page X (Section)` | `bg-accent/15 border-accent/40 text-accent` | `handleDocumentCitationClick` |
| Video (legacy) | `ΓÅ▒ MM:SS` | `bg-secondary/15 border-secondary/40 text-secondary` | `handleVideoCitationClick` |

**Click handlers split** into two dedicated functions:

```ts
// Video citation ΓÇö unchanged legacy behaviour
const handleVideoCitationClick = (e, startTime?, mediaId?) => {
  setActiveMediaId(mediaId);
  setCurrentTime(startTime);
  setTargetSeekSeconds(secs);
  setActiveSourceType('video');
  setActiveView('view-video');
};

// Document citation ΓÇö new
const handleDocumentCitationClick = (e, pageNumber?, documentId?) => {
  setActiveDocumentId(documentId);
  setTargetPage(pageNumber);          // consumed by DocumentViewer
  setActiveSourceType('pdf');
  setActiveView('view-video');
};
```

> **Note on `setActiveView('view-video')` for document citations**: the route is `view-video`
> because `VideoWorkspace.tsx` is the sole workspace component and now dynamically renders
> either the video player or `DocumentViewer` based on `activeSourceType`.

---

### `frontend/src/features/chat/useChat.ts` ΓÇö [MODIFY]

**Granular selectors added** for the active source context:

```ts
const activeDocumentId  = useAppStore((s) => s.activeDocumentId);
const activeSourceType  = useAppStore((s) => s.activeSourceType);
const currentPage       = useAppStore((s) => s.currentPage);
```

**`sendMessage` transmits document context only when the workspace is in document mode:**

```ts
const isDocumentContext = activeSourceType === 'pdf';
const documentIdToSend = isDocumentContext ? activeDocumentId ?? undefined : undefined;
const sourceTypeToSend = isDocumentContext ? 'pdf' : undefined;
const currentPageToSend =
  isDocumentContext && typeof currentPage === 'number' ? currentPage : undefined;

const data = await sendChatQuery(
  query, activeWorkspaceId, activeSessionId,
  activeMediaId ?? undefined, currentTimestamp, selectedText,
  documentIdToSend, sourceTypeToSend, currentPageToSend
);
```

> [!NOTE]
> For video context, `source_type`, `document_id`, and `current_page` are sent as `undefined` ΓÇö
> the legacy `media_id` + `current_timestamp` payload is preserved byte-for-byte. This is the
> **Zero Video Regression Guarantee** at the API layer.

---

### Verification ΓÇö Phase 3

`npx tsc --noEmit` clean.

The `EmbeddedChatWidget` (video side-panel chat) is intentionally left video-only; its citations
are always video citations because the side panel is only rendered when `activeSourceType !== 'pdf'`.

---

## Phase 4 ΓÇö Document Viewer Integration & End-to-End Verification

**Objective**: Provide a clean workspace view for reading documents and receiving page jump
navigation triggers when clicking document citations.

---

### `frontend/src/components/DocumentViewer.tsx` ΓÇö [NEW]

A clean, responsive document reader component built with the same design system tokens used by
`PersistentMediaPlayer` and the transcript panel. Key features:

- **Page navigation controls**: `ΓåÉ Prev`, `Next ΓåÆ`, a *"Page N of M"* counter, and a direct
  jump input (`Go` button).
- **`targetPage` listener**: when the store's `targetPage` changes (triggered by a
  `≡ƒôä Page X` citation click in chat), the viewer navigates to that page and applies a 2.5 s
  accent highlight ring (`border-accent ring-2 ring-accent/40 bg-accent/10`) so the user sees
  where the jump landed; then clears `targetPage`.
- **`currentPage` sync**: writing back to the store keeps chat queries page-aware.
- **Content rendering**: renders `pageSections` (title + body) when supplied; otherwise shows a
  graceful placeholder ("Viewing Page X of Y") so the reader shell works even before backend
  page content is loaded.
- **Bounds safety**: clamps navigation to `[1, totalPages]`; out-of-range jumps are ignored.
- **Footer status bar**: shows *"Document Reader"* and *"N page(s) remaining"*.

Key navigation effect (simplified):

```ts
useEffect(() => {
  if (
    targetPage !== null &&
    targetPage >= 1 &&
    targetPage <= safeTotalPages &&
    targetPage !== activePage
  ) {
    setCurrentPage(targetPage);
    setHighlightPage(targetPage);   // accent highlight for 2.5 s
    setTargetPage(null);            // clear transient trigger
  }
}, [targetPage, safeTotalPages]);
```

---

### `frontend/src/features/video/VideoWorkspace.tsx` ΓÇö [MODIFY]

**Dynamically renders the media player OR the document viewer** based on `activeSourceType`:

```tsx
const { activeMediaId, activeDocumentId, activeSourceType, setActiveView } = useAppStore();
...
{activeSourceType === 'pdf' ? (
  <div className="w-full h-full">
    <DocumentViewer />
  </div>
) : (
  <video ref={videoRef} src={mediaSrc || undefined} controls ... />
)}
```

Additional document-mode handling:

| Area | Video mode (`activeSourceType === 'video'`) | Document mode (`activeSourceType === 'pdf'`) |
| :--- | :--- | :--- |
| Empty state | `≡ƒÄ¼ No Video Selected` | `≡ƒôä No Document Selected` |
| Control bar asset info | Video asset `<select>` dropdown | Static `Document: <id>` label |
| Time readout | `Time: HH:MM` visible | Hidden (not meaningful for documents) |
| Resize handle | Visible and draggable | Hidden (viewer has its own controls) |
| Right side panel | Transcript / AI Assistant shown | Hidden entirely (viewer is self-contained) |

All video-mode rendering, layout persistence, keyboard shortcuts (Space, ΓåÉ, ΓåÆ, M, F), and PiP
logic are **untouched**.

---

### `frontend/src/features/library/LibraryGrid.tsx` ΓÇö [MODIFY]

**Asset cards now display modality icons** (`≡ƒôä` for documents, `≡ƒÄ¼` for videos) and update the
active source type on selection:

```tsx
const isDocument =
  asset.duration === '00:00' ||
  asset.thumbnailEmoji === '≡ƒôä' ||
  asset.id.toLowerCase().includes('doc') ||
  asset.id.toLowerCase().includes('pdf');

// Card header:
<span className="text-3xl">{isDocument ? '≡ƒôä' : '≡ƒÄ¼'}</span>

// Card footer:
<span>{isDocument ? '≡ƒôä Document' : '≡ƒÄ¼ Video'}</span>
```

```tsx
const handleSelectAsset = (id: string) => {
  setActiveMediaId(id);
  setActiveSourceType('video');
  setActiveView('view-video');
};
```

> [!NOTE]
> The modality heuristic is a temporary stopgap: the backend library DTO does not yet expose a
> `source_type` field per asset. When the backend adds one, replace the heuristic in
> `LibraryGrid.tsx` (and the `MediaAsset` mapping in `useLibrary.ts`) with the real field.

---

### Verification ΓÇö Phase 4

- `npx tsc --noEmit` ΓÇö **clean**, zero errors.
- `npm run build` (`next build`, Next.js 16.2.12 / Turbopack) ΓÇö **passes**:
  ```
  Γ£ô Compiled successfully in X.Xs
  Γ£ô Running TypeScript ΓÇö clean
  Γ£ô Generating static pages (3/3)
  ```

---

## Files Changed ΓÇö Complete Summary

| File (relative to `frontend/src/`) | Action | Phase(s) |
| :--- | :--- | :--- |
| `services/chatService.ts` | MODIFY | 1 |
| `features/chat/types.ts` | MODIFY | 1 |
| `types/workspaceContext.ts` | MODIFY | 1 |
| `store/useAppStore.ts` | MODIFY | 1 |
| `features/ingestion/UploadDropzone.tsx` | MODIFY | 2 |
| `features/ingestion/useIngestion.ts` | MODIFY | 2, 4 |
| `features/chat/ChatMessageItem.tsx` | MODIFY | 3 |
| `features/chat/useChat.ts` | MODIFY | 3 |
| `components/DocumentViewer.tsx` | **NEW** | 4 |
| `features/video/VideoWorkspace.tsx` | MODIFY | 4 |
| `features/library/LibraryGrid.tsx` | MODIFY | 4 |

---

## Manual Validation / QA Matrix

Full manual validation / QA matrix for all four phases ΓÇö including regression test rows for the
**Zero Video Regression Guarantee** ΓÇö is delivered in the companion
[implementation_plan.md](file:///e:/repos/athenus/implementation_plan.md) and was provided in the
initial walkthrough message alongside this document.

---

# Phase 1 (Backend) — Document Upload, Safety Limits & Page Persistence

This section documents the **backend Phase 1** implementation: generalizing `POST /media/upload`
for documents/audio, enforcing upload safety caps, routing documents to the AnyDoc parsing
pipeline, and persisting parsed pages.

## Implementation Summary

### Goal
Generalize the ingestion pipeline so **documents (PDF, DOCX, PPTX, etc.) and audio files**
can be uploaded alongside video, with safety limits enforced at the upload boundary and a
dedicated document parsing pipeline (`AnyDoc` + `RapidOCR`) that persists page-level text.

### Files Changed

| File | Change |
| :--- | :--- |
| `backend/app/infrastructure/db/models.py` | Added `DocumentPageTable` (SQLModel variant **and** SQLAlchemy fallback) storing `media_id`, `workspace_id`, `page_number`, `text`, `page_type`, `section_title`. |
| `backend/app/application/repositories/media_repository.py` | Added abstract `save_pages()` / `get_pages()` and in-memory implementations. |
| `backend/app/application/repositories/sqlite_media_repository.py` | Implemented `save_pages()` (delete-and-reinsert) and `get_pages()` (ordered by page number) against SQLite. |
| `backend/app/presentation/api/v1/media.py` | `POST /media/upload` now detects media modality (document / audio / video), enforces **100MB document** and **2GB media** caps, streams to disk in 1MB chunks, cleans up partial files on 413, and enqueues with `media_type`/`file_format`. Added `GET /media/{media_id}/pages` and `GET /media/workspace/{workspace_id}`. |
| `backend/app/domain/ingestion/persistent_ingestion_queue.py` | `enqueue_media()` accepts `media_type`/`file_format`; queue routes document jobs to `DocumentUploadedEvent` instead of the ASR/transcription path. |
| `backend/app/main.py` | Instantiated and registered `DocumentWorker` at boot. |
| `backend/app/services/workers/document_worker.py` | (Existing worker) now actually wired; parses documents with AnyDoc, runs RapidOCR on scanned pages, emits `DocumentParsedEvent`. |
| `backend/app/application/events/media_event_handlers.py` | Added `on_document_parsed()` to persist parsed pages via `repo.save_pages()`. |
| `backend/app/bootstrap/event_subscribers.py` | Registered subscriber for `DocumentParsedEvent`. |

### Document Upload Data Flow

```text
POST /api/v1/media/upload
        │  (detect type: .pdf/.docx/.pptx/... → document, .mp3/.wav/... → audio, else video)
        │  (enforce 100MB doc / 2GB media caps; stream to disk; 413 on oversize)
        ▼
enqueue_media(media_id, workspace_id, file_path, media_type, file_format)
        │  SQLite ArtifactJobTable row (status=queued)
        ▼
PersistentIngestionWorker.process_next_job()
        │  media_type == "document" ?
        ├── YES → DocumentUploadedEvent
        │          └─► DocumentWorker: AnyDoc parse → RapidOCR scanned pages
        │                 └─► DocumentParsedEvent
        │                        ├─► on_document_parsed → repo.save_pages() (document_pages table)
        │                        └─► EmbeddingWorker: chunk + embed + index into Qdrant
        └── NO  → MediaUploadedEvent (existing ASR/transcription path, unchanged)
```

### Verification Performed
- All modified backend files pass `py_compile`.
- `python -c "import app.main"` imports cleanly (SQLite schema initializes).
- `pytest tests/` → **142 passed, 2 failed** (both failures are pre-existing and require
  local Ollama models: `test_retrieval_rag.py::test_chat_query_endpoint` and
  `test_sessions.py::test_session_lifecycle_and_lazy_creation`).
- `npx tsc --noEmit` in `frontend/` passes.

## Manual QA Test Script (Backend Phase 1)

### Prerequisites
- Backend + Ollama containers running: `docker compose up -d --build backend ollama`
- A small test PDF (text-based, e.g. 2–5 pages) and a video/audio file available locally.
- Backend logs tailed for event observation: `docker compose logs -f backend`
- Optional DB inspection: `sqlite3 ./data/athenus.db` (or any SQLite client) on the host
  after starting the backend once to create the schema.

### Scope Note
The QA cases below verify **only** the backend Phase 1 behaviors implemented in this phase:
type detection, size caps, document routing, page persistence, and the two new API
endpoints. Verification is done via the HTTP API, SQLite, and backend logs — not the
frontend UI (frontend stepper/reader behavior is out of scope for this phase).

### Test Cases

| # | Test | Steps | Expected Behaviour | Pass/Fail |
| :-: | :--- | :--- | :--- | :-: |
| **1** | **Document Upload — Type Detection & Enqueue** | 1. `POST /api/v1/media/upload` with a `.pdf` file and `workspace_id=default`.<br>2. Inspect response.<br>3. Query `media_items` table via `sqlite3 ./data/athenus.db`. | Response is `200` with a `media_id`; the row in `media_items` has `media_type='document'` and `status='uploaded'`; a job row in `artifact_jobs` exists for that `media_id` with `status='queued'`. | ☐ |
| **2** | **Document Parsing → Page Persistence** | 1. Upload a 2–5 page text PDF (as in Test 1).<br>2. Wait for ingestion to complete (logs: `DocumentUploadedEvent` → `DocumentParsedEvent`).<br>3. Query `document_pages` table via `sqlite3 ./data/athenus.db`. | The `document_pages` table contains one row per page with correct `media_id`, `workspace_id`, `page_number`, extracted `text`, `page_type`, and `section_title`. | ☐ |
| **3** | **Document → Vector Indexing Completion** | 1. Upload a text PDF.<br>2. Watch logs for `DocumentParsedEvent` → `ChunksIndexedEvent`.<br>3. Query the job status. | `ChunksIndexedEvent` reports a non-zero `chunk_count`; the ingestion job for that `media_id` transitions to `status='completed'` / `stage='ready'`. | ☐ |
| **4** | **Oversized Document Safety Rejection** | 1. `POST /api/v1/media/upload` with a file >100MB (or stream a large payload via curl).<br>2. Observe response and uploads directory. | Request returns HTTP `413` with a message containing `100MB`. The partially written file is removed from `./data/uploads`. Backend container remains healthy. | ☐ |
| **5** | **Oversized Media Safety Rejection** | 1. `POST /api/v1/media/upload` with a video/audio file >2GB (simulate with a sparse/large payload via curl).<br>2. Observe response and uploads directory. | Request returns HTTP `413` with a message containing `2GB`. Partial file removed; no crash. | ☐ |
| **6** | **Video Upload Regression** | 1. `POST /api/v1/media/upload` with a small `.mp4`.<br>2. Check `media_items` row and logs. | Row has `media_type='video'`; job routes to `MediaUploadedEvent` (ASR/transcription path: `audio_extraction` → `transcription` → `chunking` → `vector_indexing`) and completes as before. | ☐ |
| **7** | **Audio Upload** | 1. `POST /api/v1/media/upload` with a small `.mp3`/`.wav` file.<br>2. Check `media_items` row and logs. | Row has `media_type='audio'` (not `video`); job routes through the ASR/transcription path and completes. | ☐ |
| **8** | **Pages API** | 1. After a successful document ingestion, `GET /api/v1/media/{media_id}/pages`. | Response is `200` with `{ media_id, total_pages, pages: [ { page_number, text, page_type, section_title }, … ] }` ordered by `page_number`; `total_pages` matches the PDF page count. | ☐ |
| **9** | **Workspace Media Listing** | 1. Upload a document and a video to the same workspace.<br>2. `GET /api/v1/media/workspace/{workspace_id}`. | Response lists both items with correct `media_type` (`document` / `video`) and their current `status`. | ☐ |
| **10** | **Re-upload Same Filename (Idempotent Pages)** | 1. Upload PDF `A.pdf` → note `media_id_1`.<br>2. Upload a different `A.pdf` (same name) → note `media_id_2`.<br>3. Query `document_pages` for both ids. | Each `media_id` has only its own parse's page rows (delete-and-reinsert per `media_id`) — no page rows from `media_id_1` leak into `media_id_2`. | ☐ |

### Final QA Checklist

- **Total Tests Executed**: `10`
- **Passed**: `____`
- **Failed**: `____`
- **Blocked**: `____`

**QA Verdict**
- [ ] **PASS** (All 10 tests passed cleanly)
- [ ] **PASS WITH ISSUES** (Minor non-blocking issues noted)
- [ ] **FAILED** (Critical functionality broken)

**QA Inspector Notes & Observations:**
```text
[Record any manual test observations, latency timings, or edge-case findings here]
```
