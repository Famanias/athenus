# Implementation Plan — Remediation Roadmap & Milestone Architecture

Living remediation roadmap for resolving Problems A–E across document presentation, page navigation, fallback behavior, AI response integrity, and RAG retrieval scope.

---

## 1. Milestone & Phase Breakdown

### Milestone 1 — Document Presentation
- **Phase 1.1 (Problem A)**: Fix PDF Rendering (Replace fragile `<iframe>` embed in `PdfRenderer.tsx` with Blob URL / Canvas rendering with load/error verification).
- **Phase 1.2 (Problem B)**: Fix PDF Page Count & Navigation State (Fetch `total_pages` from `GET /api/v1/media/{id}/pages`, add strict navigation guards `1 <= page <= totalPages`, enable multi-page citation jumps).
- **Phase 1.3 (Problem C)**: Fix Fallback & Source File Behavior (Re-label misleading "Open Source Location" button to "Download Source File", ensure clean fallback metadata card).

### Milestone 2 — RAG Reliability
- **Phase 2.1 (Problem D)**: Fix Corrupted AI Responses & Empty Context (Detect empty retrieved context in `MultiStageRetriever.py`; return graceful fallback instruction to LLM).
- **Phase 2.2 (Problem E)**: Fix Workspace-Wide RAG Retrieval & Active Context (Replace hard single-source `filter_media_id` Qdrant filter with workspace-wide vector retrieval + active-item context boosting).

### Milestone 3 — End-to-End Integration & Regression
- **Phase 3.1**: Full System Parity & Verification (Verify document presentation, video workspace parity, document RAG, video RAG, cross-source RAG, citation jumps, Docker/runtime integrity).

---

## 2. Phase Execution Protocol

For **every Phase**, the agent must execute:
1. **Investigate**: Verify exact root cause in codebase before editing.
2. **Implement**: Make minimal, targeted code changes.
3. **Automated Verification**: Run `npx tsc --noEmit` and `pytest`.
4. **Manual QA Table**: Present concrete, step-by-step manual test instructions.
5. **STOP**: Pause and wait for explicit user manual validation before proceeding.

---

## 3. Current Phase Focus — Phase 1.1 (Problem A: PDF Rendering)

- **Objective**: Ensure PDF documents (`.pdf`) uploaded to Athenus visually render the actual PDF content in the browser/Tauri viewer without blank purple background failures.
- **Confirmed Root Cause**: `PdfRenderer.tsx` embeds `<iframe src="http://localhost:8000/api/v1/media/{id}/file#page=1">`. In Tauri desktop webview sandboxes and modern browser security contexts, embedding raw backend HTTP URLs inside an `<iframe>` is blocked or fails to load, leaving only the dark purple wrapper background (`#1a1a2e`) visible.
- **Implementation Approach**: Update `PdfRenderer.tsx` to fetch the file binary from `getMediaUrl(mediaId)`, create a Blob URL (`URL.createObjectURL(blob)`), and embed/render the Blob object URL with load/error status handling.
- **Files Affected**:
  - `frontend/src/features/document/renderers/PdfRenderer.tsx`
