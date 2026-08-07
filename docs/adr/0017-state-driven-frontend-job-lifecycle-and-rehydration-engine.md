# ADR 0017: State-Driven Frontend Job Lifecycle & Rehydration Engine

## Status
Approved

## Context
When video ingestion reached 100% completion in the backend, the frontend UI remained frozen on the progress stepper and failed to render transcript text until the application was completely restarted.

Investigation revealed two root causes:
1. `BackgroundTaskRuntime.tsx` filtered active SSE streams with `j.status === 'processing' || j.status === 'pending'`, missing jobs with status `'queued'`, preventing SSE streams from connecting.
2. `useVideo` relied on component remounting rather than Zustand state changes to re-fetch transcripts upon job completion.

## Decision
1. Created `JobLifecycle` helper (`frontend/src/features/pipeline/jobLifecycle.ts`) defining explicit status states (`isActive`, `isComplete`, `isFailed`) and included `'queued'` in the active stream subscription filter.
2. Created shared `useJob(mediaId)` hook exposing `isJobComplete` driven by Zustand state updates.
3. Connected `useVideo.ts` to `useJob(activeMediaId)`, triggering automatic transcript re-fetching as soon as `isJobComplete` transitions to `true`.

## Consequences
- **Positive**: Live progress steppers advance smoothly from 5% to 100%; video transcripts re-fetch and render automatically without application restarts or manual tab switching.
- **Negative**: Adds active state subscriptions in media features.
