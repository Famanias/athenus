# Manual QA Master Test Script — Athenus Knowledge OS

This document is the canonical, standalone **Manual Quality Assurance (QA) Test Script** for verifying the **Athenus Knowledge OS** desktop application, covering both the generalized multi-source ingestion pipeline (PDF, Office documents, Video/Audio) and existing core features.

---

## 1. Before You Start — Environment & Docker Setup

Athenus uses a hybrid architecture:
- **Backend Services**: Run inside Docker containers managed via Docker Compose (`athenus-backend`, `athenus-ollama`).
- **Desktop Shell**: Runs natively via Tauri + Next.js 16 (`npx tauri dev`).

### 1.1 Preparing the Docker Environment

Execute the following commands from the repository root (`e:\repos\athenus`):

```bash
# 1. Start and build the containerized backend services
docker compose up -d --build backend ollama

# 2. Verify container health status
docker compose ps
```

#### Why `docker compose up -d --build backend` is Required:
- `./backend` is bind-mounted to `/app` inside the container, and Uvicorn executes with `--reload`.
- Running `--build` ensures that any newly added Python packages in `backend/requirements.txt` (such as `firecrawl-anydoc` or `rapidocr_onnxruntime`) are installed into the container image before startup.

#### Required Environment Prerequisites:
| Resource | Target Value | Verification Command |
| :--- | :--- | :--- |
| **Backend Container** | `athenus-backend` (Up & Healthy) | `curl -fsS http://localhost:8000/api/v1/health` |
| **Ollama Container** | `athenus-ollama` (Up) | `curl -fsS http://localhost:11434/api/version` |
| **Backend API Port** | `http://localhost:8000` | Exposed on host port 8000 |
| **Ollama API Port** | `http://localhost:11434` | Exposed on host port 11434 |
| **Frontend Dev Server** | `http://localhost:3000` | Served via Next.js Turbopack |

---

## 2. Docker Rebuild & Hot-Reload Reference Table

Use this quick-reference matrix to determine when a simple restart is sufficient versus when a full Docker image rebuild is mandatory:

| Change Made | Command | Why |
| :--- | :--- | :--- |
| **Backend Python Source Code** (`backend/app/...`) | `docker compose restart backend`<br>*(or save file for auto-reload)* | `./backend` is bind-mounted to `/app` and Uvicorn runs with `--reload`. Process restart forces instant re-initialization. |
| **Python Dependency** (`backend/requirements.txt`) | `docker compose up -d --build backend` | `requirements.txt` is copied and `pip install` executed during Docker image build. |
| **Backend Dockerfile** (`docker/backend/Dockerfile.dev`) | `docker compose up -d --build backend` | Changes container build instructions and base layers. |
| **Docker Compose Config** (`docker-compose.yml`) | `docker compose up -d --build --force-recreate backend` | Re-evaluates container environment variables, published ports, volume mounts, and networks. |
| **Environment Variables** (`.env` or compose env) | `docker compose up -d --force-recreate backend` | Re-injects updated environment variables into the running container. |
| **Database or Upload Data Reset** (`data/`) | Stop backend, delete `./data/athenus.db` or `./data/uploads/*`, then restart | Purges local SQLite DB or uploads directory for fresh testing. |

---

## 3. Launching the Tauri Desktop Application

From the repository root, launch the Tauri desktop application:

```bash
# Navigate to the frontend directory and launch Tauri in dev mode
cd frontend
npx tauri dev
```

### Expected Startup Sequence:
1. **Next.js Turbopack Compilation**:
   ```text
   ▲ Next.js 16.2.12 (Turbopack)
   - Local: http://localhost:3000
   ✓ Ready in ~8.6s
   ```
2. **Tauri Shell Window**:
   - The desktop app window opens displaying the Athenus Knowledge OS interface.
3. **Backend Connectivity**:
   - The app auto-connects to `http://localhost:8000/api/v1/health`.
   - Active workspace initializes to `"default"`.

---

## 4. Monitoring Backend Container Logs

To observe real-time telemetry, worker events, and SQL transactions during QA tests, run the following in a separate terminal:

```bash
docker compose logs -f backend
```

### Log Indicators to Watch For:
- `DocumentUploadedEvent`: Indicates a document upload was enqueued.
- `DocumentParsedEvent`: Confirms AnyDoc structure parsing / RapidOCR completed.
- `ChunksIndexedEvent`: Confirms 384-d vectors were stored in Embedded Qdrant.
- `200 OK`: Indicates successful REST API calls.

---

## 5. Comprehensive Manual QA Test Suite

Execute the following test cases in order. Mark each test as **PASS** or **FAIL** in the checkboxes.

### 5.1 Ingestion & Document Pipeline Tests

| # | Test | Steps | Expected Behavior | Pass/Fail |
| :-: | :--- | :--- | :--- | :-: |
| **1** | **Multi-Format Document Selection & Upload** | 1. Click **Pipelines** in the sidebar.<br>2. Drag and drop a local `.pdf`, `.docx`, or `.txt` document into the Upload Dropzone.<br>3. Verify selected filename appears.<br>4. Click **Select Local File** / Upload. | The dropzone accepts document formats (`.pdf`, `.docx`, `.txt`), updates button state to `Selected: <filename>`, enqueues the upload, and transitions the pipeline monitor state to `queued`. | ☐ |
| **2** | **Document Ingestion Stage Stepper Progression** | 1. Observe the Pipeline Monitor stepper after uploading a document.<br>2. Monitor real-time stage updates.<br>3. Watch backend container logs via `docker compose logs -f backend`. | Stepper displays document-specific stages (*Receiving Document Upload* $\rightarrow$ *Parsing Document Structure (AnyDoc)* $\rightarrow$ *Extracting Text from Scanned Pages (RapidOCR)* $\rightarrow$ *Indexing Vector Embeddings*). Progress reaches 100% and completes with `✓ Completed`. | ☐ |
| **3** | **Oversized Document Safety Rejection** | 1. Attempt to upload a document exceeding 100MB or 200 pages (or simulate via API with `max_file_size_mb=0.0001`).<br>2. Observe error notice in UI. | The application gracefully rejects the oversized payload with an explicit error banner stating that the file exceeds safety limits. Container does not crash or hang. | ☐ |

---

### 5.2 RAG Chat Retrieval & Citation Tests

| # | Test | Steps | Expected Behavior | Pass/Fail |
| :-: | :--- | :--- | :--- | :-: |
| **4** | **Document-Aware Chat Query & Citation Badges** | 1. Navigate to **Chat** view.<br>2. Ensure the active workspace context is set to an ingested document.<br>3. Type a query grounded in the document (e.g., *"What are the main concepts in this document?"*).<br>4. Send the question. | Assistant response generates answer text accompanied by interactive `📄 Page X (Section)` citation badges styled with accent borders. | ☐ |
| **5** | **PDF Page Jump & 2.5s Target Highlight** | 1. Click an interactive `📄 Page X` citation badge in a chat assistant message.<br>2. Observe active view and Document Reader workspace.<br>3. Check target page block formatting. | The view switches to the Document Reader, automatically navigates to Page $X$, and applies a 2.5-second accent highlight ring around the target section before clearing the target state. | ☐ |
| **6** | **Video Citation & Seek Regression Guarantee** | 1. Select a video asset in the workspace.<br>2. Ask a question grounded in the video.<br>3. Click a generated `⏱ MM:SS` timestamp citation badge. | The Video Player loads, seeks directly to timestamp `MM:SS`, and begins playback. Existing video citation functionality operates without regressions. | ☐ |

---

### 5.3 Workspace Modality & Library Integration Tests

| # | Test | Steps | Expected Behavior | Pass/Fail |
| :-: | :--- | :--- | :--- | :-: |
| **7** | **Library Grid Asset Modality Indicators** | 1. Navigate to **Workspace Library** (`view-dashboard`).<br>2. Inspect asset cards in the grid. | Document items display document icons (`📄`) and badge `"📄 Document"`. Video items display video icons (`🎬`) and duration badges. | ☐ |
| **8** | **Dual-Modality Workspace Switching** | 1. In Library Grid, click a Document asset.<br>2. Observe workspace player area.<br>3. Return to Library and click a Video asset. | Document selection loads the self-contained `DocumentViewer`. Video selection loads the `PersistentMediaPlayer`. Switching occurs smoothly without DOM reparenting crashes. | ☐ |
| **9** | **Workspace Switch State Isolation** | 1. Select a document in Workspace A.<br>2. Switch active workspace to Workspace B via the Workspace dropdown.<br>3. Inspect active document context. | Workspace B initializes with clean state (`activeDocumentId: null`, `activeSourceType: 'video'`, `currentPage: null`). Workspace A document state does not leak into Workspace B. | ☐ |

---

### 5.4 Asynchronous Lifecycle & System Resilience Tests

| # | Test | Steps | Expected Behavior | Pass/Fail |
| :-: | :--- | :--- | :--- | :-: |
| **10** | **Navigation & Refresh Recovery During Ingestion** | 1. Start ingesting a multi-page document.<br>2. While stage progress is at ~50%, navigate to Chat or Flashcards.<br>3. Return to Pipelines view.<br>4. Refresh browser view. | Ingestion continues processing in background. Returning to Pipelines view rehydrates live job state via polling/SSE without resetting progress to 0%. | ☐ |
| **11** | **Docker Backend Container Restart Resilience** | 1. Start a chat query or document ingestion.<br>2. In terminal, execute `docker compose restart backend`.<br>3. Observe UI behavior in Tauri desktop shell. | The frontend displays connection retry state, auto-reconnects when the container completes health check, and resumes state synchronization without requiring Tauri restart. | ☐ |
| **12** | **21-Table System Factory Reset** | 1. Open System Settings (`view-settings`).<br>2. Click **Clear All Data / Factory Reset**.<br>3. Confirm reset dialog. | Clears all 21 SQLite database tables, purges embedded Qdrant vector collections, unlinks uploaded files in `./data/uploads`, and resets UI to clean workspace defaults. | ☐ |

---

## 6. Known Limitations vs. Expected Behaviors

| Feature / Behavior | Classification | Description |
| :--- | :--- | :--- |
| **RapidOCR Non-Latin Script Emphasis** | **Known Limitation** | RapidOCR ONNX default models are optimized for English/Latin script (`en_PP-OCRv4`). CJK/Cyrillic OCR packages are explicitly deferred. |
| **Bounding Box Canvas Rendering** | **Known Limitation** | Bounding box coordinates (`bbox`) are extracted by `OCRLineDTO`, but frontend highlight rendering on raw PDF canvas is deferred. |
| **SQLite Single-Writer Concurrency** | **Expected Behavior** | SQLite WAL mode supports concurrent readers with single-writer serialization (intended for offline desktop single-user OS simplicity). |
| **FastAPI Hot-Reloading** | **Expected Behavior** | Editing Python files in `backend/app/` automatically triggers Uvicorn hot-reload inside the container without requiring image rebuilds. |

---

## 7. Final QA Verification Checklist & Summary

Run through all 12 test cases above and complete the execution summary below:

### Execution Summary:
- **Total Tests Executed**: `12`
- **Passed**: `____`
- **Failed**: `____`
- **Blocked**: `____`

### Severity Breakdown (If any failures occurred):
- **Critical Issues**: `____`
- **High Issues**: `____`
- **Medium Issues**: `____`
- **Low Issues**: `____`

### Overall QA Verdict:
- [ ] **PASS** (All 12 tests passed cleanly)
- [ ] **PASS WITH ISSUES** (Minor non-blocking issues noted)
- [ ] **FAILED** (Critical functionality broken)

---

### QA Inspector Notes & Observations:
```text
[Record any manual test observations, latency timings, or edge-case findings here]
```
