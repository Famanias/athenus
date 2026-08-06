# Implementation Plan — BackgroundTaskRuntime (Generic Multi-Job Pipeline Engine)

Re-architect background processing into a decoupled **`BackgroundTaskRuntime`**, separating event streaming side-effects from Zustand state management, supporting concurrent multi-job registries (`jobs: { [jobId]: JobState }`), exponential backoff SSE reconnects, HTTP polling fallbacks, and explicit stage state machines.

---

## 🏗️ Architecture Topology

```
                  Backend (FastAPI & EventBus)
                               │
            ┌──────────────────┴──────────────────┐
            ▼ SSE Stream                          ▼ REST Telemetry
   /api/v1/media/{id}/stream             /api/v1/media/{id}/history
            │                                     │
            └──────────────────┬──────────────────┘
                               ▼
                   [BackgroundTaskRuntime]
            (SSE Lifecycle, Retry Manager, Fallback Polling,
             Rehydration, State Machine Validation)
                               │
                      Writes Validated State
                               │
                               ▼
                       [useAppStore]
           (Pure State Store: jobs: { [jobId]: JobState })
                               │
                      React Unidirectional Data Flow
                               │
            ┌──────────────────┼──────────────────┐
            ▼                  ▼                  ▼
      [TopToolbar]       [Pipelines View]   [Toast Notifications]
```

---

## 🔍 Core Architectural Features

### 1. Decoupled `BackgroundTaskRuntime` (No Side Effects in Zustand)
- `useAppStore` acts purely as a **state store**. It owns state properties (`jobs`, `activeJobId`), while `BackgroundTaskRuntime` owns `EventSource` lifecycles, exponential backoff retries, and HTTP polling.

### 2. Multi-Job Registry & Job Identity (`job_id` vs `media_id`)
- Store `jobs` as a dictionary keyed by `job_id`:
  ```ts
  export interface BackgroundJob {
    job_id: string;
    media_id: string;
    workspace_id: string;
    job_type: 'ingestion' | 'graph_extraction' | 'flashcard_gen' | 'quiz_gen';
    stage: 'uploaded' | 'audio_extraction' | 'transcription' | 'chunking' | 'vector_indexing' | 'graph_extraction' | 'completed' | 'failed';
    progress: number;
    status: 'pending' | 'processing' | 'completed' | 'failed';
    message: string;
    startedAt: string;
    updatedAt: string;
    history: Array<{ stage: string; progress: number; status: string; timestamp: string }>;
  }
  ```

### 3. Strict Ingestion State Machine
- Enforce valid state transitions:
  `UPLOADED` $\rightarrow$ `AUDIO_EXTRACTION` $\rightarrow$ `TRANSCRIPTION` $\rightarrow$ `CHUNKING` $\rightarrow$ `VECTOR_INDEXING` $\rightarrow$ `GRAPH_EXTRACTION` $\rightarrow$ `COMPLETED` / `FAILED`.

### 4. Exponential Backoff Reconnect & Polling Fallback
- If SSE connection drops:
  - Retry after 2s $\rightarrow$ 5s $\rightarrow$ 10s.
  - Fall back to polling `GET /api/v1/media/{media_id}/status` every 5 seconds until SSE reconnects or the job completes.

### 5. Event History Replay
- On UI mount or reconnect, fetch `GET /api/v1/media/{media_id}/history` to rebuild completed stage checkmarks (`✔ Audio extraction`, `✔ Whisper ASR`, `✔ Chunking`).

---

## Proposed Changes

### Frontend Implementation

#### [NEW] [BackgroundTaskRuntime.tsx](file:///e:/repos/athenus/frontend/src/features/pipeline/BackgroundTaskRuntime.tsx)
- Root container component mounted inside `DesktopShell.tsx`.
- Manages `EventSource` streams for all active jobs in `jobs` registry.
- Handles exponential backoff reconnects, fallback HTTP polling, history replay, and notification toasts.

#### [MODIFY] [useAppStore.ts](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts)
- Add `jobs: Record<string, BackgroundJob>` dictionary to Zustand store.
- Add pure state reducers: `upsertJob(job)`, `removeJob(jobId)`, `setJobHistory(jobId, history)`.

#### [MODIFY] [useIngestion.ts](file:///e:/repos/athenus/frontend/src/features/ingestion/useIngestion.ts)
- Update hook to read jobs from Zustand `jobs` registry and delegate file upload trigger to `BackgroundTaskRuntime`.

#### [MODIFY] [TopToolbar.tsx](file:///e:/repos/athenus/frontend/src/components/navigation/TopToolbar.tsx)
- Update top bar indicator to support multi-job display:
  - Single active job: `⚡ Apollo: Transcribing Biology.mp4 (63%)`
  - Multiple active jobs: `⚡ 3 Background Jobs Running`

#### [MODIFY] [DesktopShell.tsx](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx)
- Mount `<BackgroundTaskRuntime />` at the root shell level.

---

## Verification Plan

### Automated Tests
- Backend test: `python -m pytest tests/test_ingestion_pipeline.py`
- Frontend production build: `npm run build`

### Manual Verification
1. Upload a video in **Pipelines** (`view-ingestion`).
2. Navigate to **Chat**, **Flashcards**, and **Knowledge Graph** tabs while video processes.
3. Verify that the **TopToolbar** badge shows active live progress (e.g. `⚡ Apollo: Transcribing (45%)`).
4. Disconnect Wi-Fi / simulate network interruption: verify exponential backoff retry and HTTP status polling fallback.
5. Reload page mid-ingestion: verify history rehydration rebuilds completed stage checkmarks.
