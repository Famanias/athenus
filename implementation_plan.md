# Athenus — Implementation Plan & Status

Living implementation roadmap for the **Generalized Document & PDF Ingestion Architecture**
(backends ADR 0021 + ADR 0022) and the surrounding integration phases.

- Last updated: 2026-08-09
- Status legend: ✅ Completed · 🟡 In progress · ⬜ Pending

---

## 1. Status Overview

| Workstream | Status | Key commits |
| :--- | :--- | :--- |
| Backend Milestones 2–4 (parsing, OCR, worker, chunking, retrieval, citations) | ✅ | `d3a9ff8` → `71f43a9` |
| Frontend Phases 1–4 (domain types, upload UI, citations, document viewer) | ✅ | `59f96ac` |
| Backend Phase 1 (upload routing, safety caps, page persistence, pages API) | ✅ | `d6ef2d7` |
| Backend Phase 2 (validation guardrails wiring) | ✅ | uncommitted |
| Frontend wiring: DocumentViewer → pages API | ✅ | uncommitted |
| QA regression / manual test verification | ⬜ | — |

---

## 2. Completed Work

### 2.1 Backend Milestones 2–4 — Document Ingestion Core (ADR 0021)

The backend pipeline is implemented and committed:

- **M2 P2.1** — `DocumentParsingPort` + **Firecrawl AnyDoc** adapter for text-based PDFs,
  Office docs, spreadsheets (`d3a9ff8`).
- **M2 P2.2** — `OCRPort` + **RapidOCR (ONNX Runtime)** adapter for scanned pages (`ed84814`).
- **M3 P3.1** — `DocumentWorker` + event-bus sync/async handler support (`5ec817a`).
- **M3 P3.2** — Generalized chunker + embedding worker for document page units (`7952e1d`).
- **M4 P4.1** — Document Qdrant filtering + page-context retrieval (`0efc7a0`).
- **M4 P4.2** — Generalized citation parser + `CitationDTO` document serialization (`71f43a9`).

### 2.2 Frontend Phases 1–4 — Frontend Integration (ADR 0022)

Fully implemented and committed in `59f96ac`. The complete file-level breakdown is in
[`walkthrough.md`](walkthrough.md) under "Frontend Integration for Generalized Document & PDF
Ingestion Architecture":

- **Phase 1** — Domain types (`sourceType`, `pageNumber`, `sectionTitle`, `documentId`), API client
  contracts (`chatService.ts` `sendChatQuery(documentId, currentPage)`), store foundations
  (`activeSourceType`/`activeDocumentId`/`currentPage`/`targetPage`).
- **Phase 2** — `UploadDropzone` multi-format file selection + `useIngestion` document detection
  (`DOCUMENT_STAGES` stepper, `isDocumentJob()`).
- **Phase 3** — `ChatMessageItem` generalized citations (`📄 Page X` badges →
  `handleDocumentCitationClick`) + `useChat` page-aware query forwarding.
- **Phase 4** — `DocumentViewer` (new) + `VideoWorkspace` dual-modality switch + `LibraryGrid`
  document icon heuristic.

### 2.3 Backend Phase 1 — Upload Routing, Safety Caps & Page Persistence

Implemented and committed in `d6ef2d7`:

- **Upload type detection** in `media.py`: `doc` / `audio` / `video` derived from extension + MIME.
- **Safety caps**: documents → `413` over 100 MB; video/audio → `413` over 2 GB (streamed writes,
  temp-file cleanup on rejection).
- **Document routing**: `enqueue_media` accepts `media_type`/`file_format`; document jobs → queue
  `doc` branch → `DocumentUploadedEvent` → `DocumentWorker`.
- **`DocumentWorker` registered in `main.py`** — was previously never instantiated at runtime.
- **Page persistence**: `DocumentPageTable` (SQLModel + SQLAlchemy), `save_pages`/`get_pages` on
  `MediaRepository`/`SqliteMediaRepository`/`InMemoryMediaRepository`.
- **`on_document_parsed` handler** persists parsed pages + records `document_parsing` progress.
- **New endpoints**: `GET /media/{id}/pages` (page sections), `GET /media/workspace/{id}` (all
  media types in a workspace).
- **QA verification**: 10 manual backend QA tests documented in
  [`walkthrough.md`](walkthrough.md) "Manual QA Test Script (Backend Phase 1)".

---

## 3. Completed — Backend Phase 2: Validation Guardrails Wiring

Per **ADR 0021 §4**, over-cap documents (100 MB / 200 pages / zip-bomb) are **hard-rejected
during the validation stage** with `status: "failed"`, `stage: "validation"`, and the message
*"Document exceeds safety limit (200 pages / 100MB)."*

- ✅ `backend/app/domain/media/document_validation.py` — size cap, PDF page-count via
  `/Count` regex, zip-bomb ratio checks.
- ✅ Wired into `DocumentWorker` — emits `DocumentValidationFailedEvent` + `ProcessingFailedEvent`
  with `stage="validation"` on failure; parser never runs.
- ✅ Queue surfaces `failed_stage` in `_handle_job_failed` (was hardcoded `"pipeline"` fallback).
- ✅ Queue sets job `stage="validation"` in document routing before parsing begins.
- ✅ Unit tests: `tests/test_document_validation.py` (7) + worker rejection path in
  `tests/test_document_worker.py` → **12 passed**; full suite **151 passed / 2 pre-existing fails**.
- ✅ `walkthrough.md` Phase 2 section with 7-case manual QA table.

Frontend already anticipated the `validation` stage (`useIngestion.ts` renders it).

## 4. Completed — Frontend Wiring: DocumentViewer → Pages API

The backend `GET /media/{id}/pages` endpoint is now consumed end-to-end:

- ✅ `mediaService.ts` — `getDocumentPages(mediaId)` + DTOs.
- ✅ `useIngestion.ts` — `handleFileUpload` sets `activeDocumentId` for document files.
- ✅ `DocumentViewer.tsx` — fetches pages on `activeDocumentId` change, maps backend DTO → local
  `PageSection`, feeds `totalPages`/`pageSections`, graceful placeholder on failure.
- ✅ `npx tsc --noEmit` clean.
- ✅ `walkthrough.md` Phase 5 section with 5-case manual QA table.

---

## 5. Pending Phases

### 5.1 QA Regression — Video/Document Parity ⬜

Re-run the full manual QA script (`manual_qa.md`, 10 backend + frontend tests) against the
current build. Known partial failures recorded in `QA_Test_Results.md` v5.1–5.4 (video citation
seek regression on local model; backend unreachable during earlier runs). Each phase below must be
verified against its mapped tests before being marked done.

---

## 6. Suggested Execution Order

1. **Backend Phase 2** (validation guardrails wiring) — ✅ complete.
2. **Frontend pages wiring** (§4) — ✅ complete.
3. **QA regression** (§5.1) — verify both modalities end-to-end, update `walkthrough.md`.

> Earlier planning iterations referenced Ollama model provisioning and LLM error-surfacing phases
> (Ollama `/api/tags` dual-sided verification, P2 error surfacing, honest model listing, video
> seek, library routing). Those items are tracked separately under the original QA-gap effort and
> are not part of the document-ingestion roadmap above unless explicitly re-scoped.
