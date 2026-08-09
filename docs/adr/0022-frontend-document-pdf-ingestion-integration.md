# ADR 0022: Frontend Generalized Document & PDF Ingestion Integration

- **Status**: Approved (Implemented — Phases 1–4)
- **Date**: 2026-08-09
- **Deciders**: Athenus Architecture Team

## Context & Problem Statement

[ADR 0021](file:///e:/repos/athenus/docs/adr/0021-generalized-document-pdf-ingestion-architecture.md)
specified the **backend** capability for generalized document/PDF ingestion (AnyDoc + RapidOCR,
`location_json` unified provenance, page-aware retrieval). The frontend was still video-centric: the
workspace rendered an HTML5 video player, chat queries were anchored to `media_id` +
`current_timestamp`, and citations rendered exclusively as `⏱ MM:SS` seek badges.

The frontend needed to consume the new backend document capabilities — page-aware chat queries,
document citations, a document reading view, and document ingestion stage monitoring — **without
breaking any legacy video workflow** (upload, player seeking, timestamp citation clicks, PiP
detachment prevention, transcript syncing).

## Decision Drivers

1. **Zero Video Regression Guarantee**: All legacy video paths must remain byte-for-byte
   operational. Document behavior is strictly *additive*.
2. **Unified Modality Model**: A single typed discriminator (`sourceType: 'video' | 'pdf'`) should
   thread end-to-end — DTO → store → query payload → citation rendering → workspace layout — to
   avoid permanent dual-branching in the frontend.
3. **Backward-Compatible Contracts**: New document fields (`source_type`, `page_number`,
   `section_title`, `document_id`, `current_page`) must be optional so older backends and the
   legacy video payload are unaffected.
4. **One-Shot Navigation**: Page jumps from chat citations must be deterministic and must not
   re-trigger on stale state (e.g. re-mounts, unrelated re-renders).

## Decided Architectural Choices

### 1. Modality Discriminator (`activeSourceType`) as the Single Source of Truth

* **Decision**: The Zustand `UISlice` owns `activeSourceType: 'video' | 'pdf'` (default `'video'`),
  alongside `activeDocumentId`, `currentPage`, and a transient `targetPage`. Every setter keeps the
  flat field and the persisted `WorkspaceContext` object in sync (`setActiveDocumentId` →
  `context.documentId`, `setActiveSourceType` → `context.sourceType`, `setCurrentPage` →
  `context.currentPage`). `setTargetPage` is a pure transient navigation trigger and never syncs
  context.
* **Rationale**: One discriminator avoids per-component "is this a document?" heuristics scattered
  across the app. Components read `activeSourceType` and branch once.

### 2. Dual-Modality Workspace (`view-video` Route Reuse)

* **Decision**: `VideoWorkspace.tsx` remains the sole workspace component and dynamically renders
  either the `<video>` player (`PersistentMediaPlayer`) or the new `DocumentViewer` based on
  `activeSourceType === 'pdf'`. The route id `'view-video'` is intentionally **reused** for both
  modalities.
* **Document mode**: empty state (`📄 No Document Selected`), control bar shows `Document: <id>`
  instead of the video asset dropdown, time readout hidden, right-side transcript/chat panel and
  resize handle hidden (the viewer is self-contained).
* **Video mode**: entirely untouched — player, seek, PiP, transcript sync, keyboard shortcuts.
* **Rationale**: Preserves ADR 0005's zero-DOM-reparenting model (one persistent workspace node,
  CSS-hidden, never unmounted) rather than introducing a second route/component that would
  destabilize PiP. The route-name overload is accepted technical debt (see Consequences).

### 3. Generalized Citation Rendering (`📄 Page X` badges)

* **Decision**: `ChatMessageItem.tsx` branches per citation: a citation is a document citation when
  `sourceType === 'pdf' || typeof pageNumber === 'number'`. Document citations render as
  `📄 Page X (Section)` badges (accent styling) that call `handleDocumentCitationClick` →
  `setActiveDocumentId` + `setTargetPage(page)` + `setActiveSourceType('pdf')` + `setActiveView('view-video')`.
  Video citations keep the legacy `⏱ MM:SS` badge → `handleVideoCitationClick` → seek.
* **Rationale**: The `typeof pageNumber === 'number'` secondary signal provides backward
  compatibility with backends that omit `source_type`. `mediaId` doubles as the document id for
  document citations (document assets carry `doc_xxx` ids), avoiding a new field on `Citation`.

### 4. Page-Aware Chat Query Forwarding

* **Decision**: `useChat.ts` `sendMessage` computes `isDocumentContext = activeSourceType === 'pdf'`.
  Only in document mode does it transmit `documentIdToSend`, `sourceTypeToSend` (`'pdf'`), and
  `currentPageToSend`. For video, all three are `undefined` and omitted from the wire payload,
  preserving the legacy `media_id` + `current_timestamp` contract exactly.
* **Rationale**: Guarantees zero regression at the API layer — the backend sees identical video
  requests before and after this change.

### 5. Transient `targetPage` Navigation Trigger

* **Decision**: Citation clicks set a one-shot `targetPage` store field. `DocumentViewer`
  subscribes: on change it validates `1 ≤ page ≤ totalPages`, navigates via `setCurrentPage`
  (syncing `context.currentPage`), applies a 2.5 s accent highlight ring, then clears `targetPage`
  to `null`.
* **Rationale**: A persistent "jump target" would re-navigate on every unrelated re-render or
  mount. Clearing after consumption makes the trigger idempotent and deterministic.

### 6. Document-Aware Ingestion Stage Monitoring

* **Decision**: `useIngestion.ts` adds a `DOCUMENT_STAGES` template (Receiving Upload → Parsing
  Document Structure (AnyDoc) → Extracting Text from Scanned Pages (RapidOCR) → Indexing Vector
  Embeddings). `isDocumentJob()` (scans `job_type + stage + title` for `document|pdf|docx`, or a
  `document_parsing`/`ocr_processing` stage) selects the template. `handleFileUpload` detects
  document files by extension and flips `setActiveSourceType('pdf')` before upload. The legacy
  `INITIAL_STAGES` (Hermes/Apollo/Athenus/Owl) is preserved for video.
* **Rationale**: Mirrors the backend `INGESTION_STAGES` registry so the stepper reflects real
  backend stage transitions for both modalities.

## Deferred Scope Declarations

1. **Library Grid Document Routing**: `LibraryGrid` displays `📄`/`🎬` icons via a stopgap
   heuristic (`duration === '00:00'`, id contains `doc`/`pdf`, thumbnail emoji) because the backend
   asset DTO lacks a `source_type` field, and `handleSelectAsset` currently forces `'video'`.
   Routing document assets from the library into `DocumentViewer` is **deferred** until the backend
   exposes per-asset `source_type`.
2. **Document Content Fetching**: `DocumentViewer` is presentational — it renders `pageSections`
   when supplied and a graceful placeholder otherwise. A backend page-content contract
   (`GET /documents/{id}/pages`) is **deferred**.
3. **`activeDocumentId` Persistence**: Unlike `activeMediaId`, the active document is not persisted
   to `localStorage`. Restoring the last-open document across restarts is **deferred**.
4. **Dedicated Document Route**: The overloaded `view-video` route may be split into a
   `view-document` route when route-aware tooling requires it. **Deferred**.

## Consequences

* **Positive**:
  * 100% video regression safety — every legacy path is byte-for-byte preserved and verified
    (`npx tsc --noEmit` clean; `npm run build` passes).
  * Document citations deep-link into the reader at the exact page with visual highlight feedback.
  * Page-aware chat queries transmit active document context only when relevant.
  * A single `activeSourceType` discriminator keeps frontend branching uniform and testable.
* **Negative / Risks**:
  * The `view-video` route id is semantically overloaded for both modalities.
  * The `LibraryGrid` document heuristic is fragile and currently cannot route documents from the
    library into the reader — requires a backend `source_type` field on the asset DTO to resolve.
  * `DocumentViewer` cannot yet display real page content until the backend page-content contract
    lands.
