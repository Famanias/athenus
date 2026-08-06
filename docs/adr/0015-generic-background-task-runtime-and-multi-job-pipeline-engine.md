# ADR 0015: Generic BackgroundTaskRuntime & Multi-Job Pipeline Engine

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: Video ingestion telemetry previously unmounted when navigating away from the Pipelines tab. Furthermore, embedding `EventSource` side-effects directly inside the Zustand state store (`useAppStore`) violated store purity and prevented multi-job concurrency, reconnect retries, and fallback polling.
* **Decision**: Establish a generic **`BackgroundTaskRuntime`** engine:
  1. **Decoupled Side-Effect Ownership**: `BackgroundTaskRuntime` owns `EventSource` lifecycles, exponential backoff reconnects, HTTP fallback polling, and history replay. Zustand `useAppStore` remains a pure state store holding the job registry dictionary (`jobs: { [jobId]: JobState }`).
  2. **Job Identity (`job_id` vs `media_id`)**: Separates source `media_id` from task execution `job_id`, supporting concurrent background jobs (ingestion, graph extraction, flashcard/quiz generation).
  3. **Strict Ingestion State Machine**: Enforces valid stage transitions (`UPLOADED` $\rightarrow$ `AUDIO_EXTRACTION` $\rightarrow$ `TRANSCRIPTION` $\rightarrow$ `CHUNKING` $\rightarrow$ `VECTOR_INDEXING` $\rightarrow$ `GRAPH_EXTRACTION` $\rightarrow$ `COMPLETED`).
  4. **Multi-Job TopToolbar Badge**: Displays single or multi-job progress badges (`⚡ 3 Background Jobs Running`) across all application views.
* **Alternatives Considered**:
  - *Side-Effects in Zustand*: Violated state store purity and made unit testing difficult.
  - *Single `activeIngestionMediaId` Variable*: Prevented concurrent video processing and future multi-task orchestration.
* **Rationale**: Decoupling runtime side-effects from Zustand and modeling jobs as a key-value registry provides a resilient, scalable foundation for present and future background task orchestration.
* **Trade-offs**: Requires dictionary state management instead of a single string, but eliminates UI freezing, connection drop bugs, and stale state.
