# Root Cause Analysis: Frontend Ingestion Stepper Lock & Transcript Rehydration Failure

**Document Status:** Final  
**Date:** August 7, 2026  
**Target Component:** Athenus Frontend State Engine (`BackgroundTaskRuntime.tsx`, `useIngestion.ts`, `useVideo.ts`, `useAppStore.ts`)  
**Author:** Antigravity AI  

---

## 1. Executive Summary

Testing of the multi-video ingestion pipeline revealed a visual state synchronization failure between backend execution and frontend rendering:

1. A lecture video is uploaded and processed by the backend.
2. The backend completes Faster-Whisper ASR, Qdrant vector indexing, and Knowledge Graph extraction (showing `Artifact: ready`, `Progress: 100%`).
3. The frontend **Pipelines View** remains visually stuck on **Hermes is Receiving Your Lecture (In Progress 15%)**.
4. The **Video View** shows the uploaded video, but **displays no transcript**.
5. Restarting the desktop app (`npx tauri dev`) immediately resolves both views: the video transcript loads and the job registers as completed.

### Confirmed Root Cause
The root cause is a **filter mismatch in `BackgroundTaskRuntime.tsx`**:
`BackgroundTaskRuntime` filters active jobs using `j.status === 'processing' || j.status === 'pending'`, explicitly excluding jobs with `j.status === 'queued'`. Because newly uploaded videos are initialized with `status: 'queued'`, `BackgroundTaskRuntime` **never opens an SSE EventSource stream** for the media item. As a result, backend completion events are never received, progress updates are never written to Zustand, and the custom window event `athenus:transcript-ready` is **never dispatched**, leaving the Video tab unaware that the transcript is ready until a cold app restart forces an initial `fetchTranscript()` call.

---

## 2. Frontend Data Flow & Lifecycle Analysis

```
                              FRONTEND DISCONNECTED EVENT FLOW
                              
  ┌──────────────────┐    uploadMedia()      ┌──────────────────────────┐
  │  React UI        │ ────────────────────► │ Backend API (/upload)    │
  │ (Pipelines View) │                       └─────────────┬────────────┘
  └────────┬─────────┘                                     │
           │                                 Returns media_id & enqueues job
           │                                 Job registered in Zustand:
           │                                 { status: "queued", stage: "queued" }
           │                                               │
           │                                               ▼
           │                         ┌──────────────────────────────────────────┐
           │                         │       BackgroundTaskRuntime.tsx          │
           │                         │  Filters: status === 'processing'|'pending'
           │                         │  ❌ IGNORES status === 'queued'!         │
           │                         └─────────────────────┬────────────────────┘
           │                                               │
           │                                               │ (SSE Stream NEVER opened!)
           │                                               ▼
           │                         ┌──────────────────────────────────────────┐
           │                         │       Backend EventSource Stream         │
           │                         │       (/api/v1/media/{id}/stream)        │
           │                         └─────────────────────┬────────────────────┘
           │                                               │
           │                                               │ (Completion Payload NEVER received!)
           │                                               ▼
           │                         ┌──────────────────────────────────────────┐
           │                         │   window.dispatchEvent(...)              │
           │                         │   "athenus:transcript-ready" NEVER FIRED!│
           │                         └─────────────────────┬────────────────────┘
           │                                               │
           ▼                                               ▼
┌──────────────────────┐                    ┌───────────────────────────────────┐
│ Pipelines View Stepper│                    │ Video Workspace (useVideo.ts)     │
│ Frozen at 15%        │                    │ "No Transcript Available"         │
│ (Reads stale queued) │                    │ (Waiting for transcript-ready!)   │
└──────────────────────┘                    └───────────────────────────────────┘
```

---

## 3. Backend vs. Frontend State Comparison

| Execution Dimension | Backend State (Confirmed Reality) | Frontend State (Stale UI View) | Divergence Cause |
|---|---|---|---|
| **Audio Extraction** | Completed (WAV 16kHz extracted) | Pending / Queued | SSE stream never established by `BackgroundTaskRuntime` |
| **Whisper ASR** | Completed (`INSERT INTO transcript_segments`) | Pending / Queued | SSE `athenus:transcript-ready` event never dispatched |
| **Vector Indexing** | Completed (`INSERT INTO transcript_chunks`) | Pending / Queued | REST jobs polling ignored due to `inspectedJobId` binding |
| **Knowledge Graph** | Completed (`Artifact: ready`, 100%) | Stuck at 15% | Zustand `jobs` store contains stale initial `queued` job |
| **Video Transcript** | Saved in SQLite (`/media/{id}/transcript`) | Empty / Unavailable | `useVideo.ts` listener never triggered |

---

## 4. Event Flow Analysis

### SSE Stream Lifespan Failure
1. In [`BackgroundTaskRuntime.tsx`](file:///e:/repos/athenus/frontend/src/features/pipeline/BackgroundTaskRuntime.tsx#L30-L32):
   ```ts
   const activeJobEntries = Object.values(jobs).filter(
     (j) => j.status === 'processing' || j.status === 'pending'
   );
   ```
   When a user uploads a video, `useIngestion.ts` registers the job in Zustand with `status: 'queued'`.
2. Because `status === 'queued'` is excluded from `activeJobEntries`, `useEffect` in `BackgroundTaskRuntime` skips opening the SSE connection (`createMediaProcessingStream(mediaId)`).
3. The backend finishes transcribing and emits SSE completion payloads, but **no client is listening**.
4. The completion logic in `BackgroundTaskRuntime.tsx` (lines 81–96):
   ```ts
   if (status === 'completed' || current_stage === 'completed') {
     ...
     window.dispatchEvent(
       new CustomEvent('athenus:transcript-ready', { detail: { mediaId } })
     );
   }
   ```
   is **never executed**.

### Video Workspace Transcript Listener Disconnect
1. In [`useVideo.ts`](file:///e:/repos/athenus/frontend/src/features/video/useVideo.ts#L88-L104):
   `useVideo` binds an event listener for `athenus:transcript-ready` to invoke `fetchTranscript()`.
2. Because `athenus:transcript-ready` is never dispatched, `useVideo` never refetches the transcript after processing completes.
3. When the user closes and restarts the application (`npx tauri dev`), `useVideo` mounts cleanly, executes its initial `useEffect(() => { fetchTranscript(); }, [])`, and retrieves the completed transcript from the REST API.

---

## 5. Architectural Weaknesses

1. **Brittle Stream Activation Filter**:
   `BackgroundTaskRuntime` relies on a strict string status match (`'processing' | 'pending'`), causing new background jobs (`'queued'`) to be orphaned from stream tracking.

2. **Single-Point-of-Failure Window Event Propagation**:
   The Video workspace relies exclusively on a custom DOM window event (`athenus:transcript-ready`) dispatched by `BackgroundTaskRuntime` to trigger refetches, rather than reacting to global Zustand job status state changes (`status === 'completed'`).

3. **Lack of Automatic Transcript Refetching on View Mount**:
   `useVideo` does not re-check transcript status when switching tabs if `activeMediaId` has not changed.

---

## 6. Recommended Proposed Solution (No Code Changes Made)

Per your instructions, **no code changes have been made**. To fix this issue in a future implementation phase:

### Step 1: Expand `BackgroundTaskRuntime` Stream Subscription Filter
Include `'queued'` in `activeJobEntries` filter in [`BackgroundTaskRuntime.tsx`](file:///e:/repos/athenus/frontend/src/features/pipeline/BackgroundTaskRuntime.tsx):
```ts
const activeJobEntries = Object.values(jobs).filter(
  (j) => j.status === 'processing' || j.status === 'pending' || j.status === 'queued'
);
```

### Step 2: Bind Transcript Refetching to Zustand Job Completion
In [`useVideo.ts`](file:///e:/repos/athenus/frontend/src/features/video/useVideo.ts), subscribe directly to Zustand's `jobs[activeMediaId]` state. When `jobs[activeMediaId].status` transitions to `'completed'`, invoke `fetchTranscript()` automatically, eliminating reliance on DOM window events.

### Step 3: Trigger Auto-Refetch in `useVideo` on Tab Mount
Ensure `useVideo` re-queries `/api/v1/media/{activeMediaId}/transcript` whenever the Video tab becomes active if `segments.length === 0`.

---

## 7. Validation Strategy

1. **Automated Verification**:
   - Run `npx tsc --noEmit` in `frontend/`.
   - Run `npm run build` in `frontend/`.

2. **Manual Verification Protocol**:
   - Upload a new lecture video in **Pipelines View**.
   - Verify that `BackgroundTaskRuntime` opens the SSE stream immediately upon upload.
   - Verify live progress stepper advances from 15% $\rightarrow$ 50% $\rightarrow$ 85% $\rightarrow$ 100%.
   - Switch to **Video View** immediately after completion without restarting the app: verify transcript is loaded and displayed automatically.
