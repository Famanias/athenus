# Walkthrough — Decoupled BackgroundTaskRuntime Engine & Persistent Multi-Job Telemetry

This document details the resolution of the background ingestion pause bug through the implementation of a decoupled **`BackgroundTaskRuntime`** engine.

---

## 🔍 Root Cause Analysis & Architecture Redesign

### The Bug
Previously, rendering of the Pipelines view was conditional (`{activeView === 'view-ingestion' && <UnifiedLearningPipeline />}`). Switching tabs unmounted the React component, destroyed local hook state, and closed the SSE stream (`eventSource.close()`). Returning to the tab rendered a fresh component with blank state, hiding live progress.

### The Decoupled Solution Architecture

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

## 🛠️ Summary of Changes

### 1. Pure State Store Reducers ([`useAppStore.ts`](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts))
- **`BackgroundJob` Interface**: Defined structured job state (`job_id`, `media_id`, `workspace_id`, `job_type`, `stage`, `progress`, `status`, `message`, `error`, `startedAt`, `updatedAt`, `history`).
- **Multi-Job Registry**: Added `jobs: Record<string, BackgroundJob>` dictionary and `activeJobId` to Zustand store.
- **Pure State Reducers**: Implemented `upsertJob`, `removeJob`, `setJobHistory`, and `setActiveJobId` without any side-effects in Zustand.

### 2. Decoupled Runtime Component ([`BackgroundTaskRuntime.tsx`](file:///e:/repos/athenus/frontend/src/features/pipeline/BackgroundTaskRuntime.tsx))
- **Root Shell Container**: Mounted at the top level of [`DesktopShell.tsx`](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx) to stay alive indefinitely across all view navigation.
- **SSE Stream Management**: Maintains active `EventSource` connections for in-flight tasks without unmounting.
- **Exponential Backoff Reconnect**: On SSE disconnect, automatically retries reconnection at 2s $\rightarrow$ 5s $\rightarrow$ 10s intervals.
- **HTTP Polling Fallback**: Polling `GET /api/v1/media/{media_id}/status` every 5 seconds ensures UI state never becomes stale if SSE is disrupted.
- **Event History Replay**: Fetches `GET /api/v1/media/{media_id}/history` to rebuild completed stage checkmarks.
- **Completion Events**: Dispatches global `athenus:transcript-ready` events upon task completion.

### 3. Pipeline Hook Refactoring ([`useIngestion.ts`](file:///e:/repos/athenus/frontend/src/features/ingestion/useIngestion.ts))
- Refactored `useIngestion` to read live job state from Zustand's `jobs` registry.
- File uploads register a `job_id` and hand over stream listening directly to `BackgroundTaskRuntime`.

### 4. Global Top Toolbar Indicator ([`TopToolbar.tsx`](file:///e:/repos/athenus/frontend/src/components/navigation/TopToolbar.tsx))
- Added a live progress badge in the top app bar:
  - Single active task: `⚡ Apollo: Transcribing (60%)`
  - Multiple active tasks: `⚡ 3 Background Tasks Running`
- Clicking the badge navigates directly to the Pipelines tab (`view-ingestion`).

---

## 📦 Git Commits Created

| Commit | Scope | Summary |
|---|---|---|
| `fdc6961` | Frontend | `feat(pipeline): implement decoupled BackgroundTaskRuntime with multi-job registry, backoff reconnects, polling fallbacks, and top bar progress badge` |
| `fdeea05` | Documentation | `docs: add ADR 0015 for Generic BackgroundTaskRuntime & Multi-Job Pipeline Engine` |

---

## 🧪 Verification Results

- **Frontend Production Build**: `npm run build` compiled cleanly in `4.9s` with zero TypeScript errors.
- **Backend Test Suite**: All **114 passed** out of 114 tests in backend pytest suite.
