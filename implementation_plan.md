# Implementation Plan — Event-Driven Video Ingestion Pipeline & Real-Time SSE Synchronization

Make the video upload → audio extraction (FFmpeg) → speech-to-text (Faster-Whisper) → semantic chunking → vector indexing (Embedded Qdrant) pipeline fully operational and synchronized between backend background workers and the frontend, using an event-driven architecture where **workers emit domain events** and **REST + SSE both consume a single shared progress source**.

---

## User Review Required

> [!IMPORTANT]
> **Architecture guardrail — this plan introduces:**
> 1. A **repository abstraction** so no API or HTTP code ever touches raw `dict()` storage again.
> 2. **Application-layer event handlers** — `media.py` stays HTTP-only and never owns domain behavior.
> 3. A **shared Progress Store** that both `GET /status` (REST) and `GET /stream` (SSE) read from, so there is one source of truth.
> 4. A richer, replayable event model with **progress, correlation ids, and timestamps**.

---

## 2. Target Architecture

```text
                  ┌──────────────┐   MediaUploadedEvent /
Worker (transcript│     EventBus │   TranscriptCompleted / …events
 & embedding) ────► (in-process) │
                  └──────┬───────┘
                         │ publishes
                         ▼
            ┌──────────────────────────┐
            │  Event Handler (application)│   <- decoupled from HTTP
            │  media_event_handlers.py  │
            │    └─ Repository.update_status()      STORE
            │    └─ ProgressStore.record(stage, %)
            └──────────────┬───────────┘
                           │
              ┌────────────┴────────────┐
              │      MediaRepository          │   Today: dict()
              │  + Progress Store             │  Later: SQLite / Postgres
              └────────────┬───────────────T─────▼
                           │            REST reads repo
                GET /status │            (always current snapshot)
                GET /transcript
                           │
                           ▼
                     Progress Store
                     emits snapshot → SSE
                           │
                           ▼
                       Frontend UI
```

**Key invariant:** Workers never touch HTTP or storage directly. They publish domain events. Handlers translate events into (a) repository updates and (b) progress entries. Full synchrony).

---

## 3. New Abstraction: `MediaRepository`

### [NEW] `backend/app/application/repositories/media_repository.py`
Define a single interface both the workers‑side handlers and the REST endpoints use. HTTP code must **never** reference `in_memory_media_db` / `in_memory_transcripts_db` again.

```python
class MediaRepository:
    def upsert(self, item: MediaItem) -> None: ...
    def get(self, media_id: str) -> Optional[MediaItem]: ...
    def update_status(self, media_id: str, status: ProcessingStatus,
                      error: Optional[str] = None) -> None: ...
    def save_transcript(self, media_id: str, segments: List[dict]) -> None: ...
    def get_transcript(self, media_id: str) -> List[dict]: ...
```

- **[NEW] `InMemoryMediaRepository`** — concrete impl backed by `dict()`. This is the *only* code that references dictionaries.
- Later swap via config/DI to `SqliteMediaRepository`, `PostgresMediaRepository`, etc. — **no API code changes.**

**Migration in `media.py`:** replace the two module-level dicts with a single `media_repository: MediaRepository = InMemoryMediaRepository()` instance used by all handlers and endpoints.

---

## 4. Remove Domain Logic From `media.py`

`presentation/api/v1/media.py` becomes **HTTP-only**. It no longer:
- subscribes to the `EventBus`,
- mutates `in_memory_media_db`,
- owns status transitions.

### [NEW] `backend/app/application/events/media_event_handlers.py`
A single module of async handlers that translate domain events into repository/progress updates. Registered at bootstrap (see §6), **not** inside the router.

| Event | Handler effect |
|-------|----------------|
| `MediaUploadedEvent` | `repo.update_status(id, UPLOADED)` |
| `ProcessingStartedEvent` | `repo.update_status(id, AUDIO_EXTRACTION)`; `progress.emit({stage,progress:0,...})` |
| `StageProgressEvent` | `repo.update_status(id, <current stage>)`; `progress.emit({stage, progress, message})` |
| `TranscriptCompletedEvent` | `repo.save_transcript(segments)`; `repo.update_status(id, EMBEDDING)`; emit progress |
| `ChunksIndexedEvent` | `repo.update_status(id, COMPLETED, chunk_count)`; emit `completed` |
| `ProcessingFailedEvent` | `repo.update_status(id, FAILED, error)`; emit `failed` |

The path for a completed upload:
```text
Worker → EventBus → Handler → Repository → SSE Publisher → Frontend
```

---

## 5. Richer Event Model

### 5.1 New events (currently missing)

- **[NEW] `ProcessingStartedEvent`** — emitted at the top of `transcript_worker.handle_media_uploaded` before any work. Explicitly sets `AUDIO_EXTRACTION`, removing the implicit `PENDING → TRANSCRIBING` inference.
- **[NEW] `StageProgressEvent`** — carries granular **percentage** progress, so the UI shows live percentages instead of coarse stage flips.

### 5.2 Standardized payloads

Every domain event now carries correlation + progress context via the existing `DomainEvent` (which already has `aggregate_id` and `occurred_at`):

```python
DomainEvent(
    event_type="StageProgressEvent",
    aggregate_id=media_id,          # = media_id
    payload={
        "media_id": media_id,
        "event_id": <ulid/uuid4>,   # [NEW] per-event correlation id
        "timestamp": <iso8601>,      # source: DomainEvent.occurred_at
        "stage": "transcription",
        "progress": 42,
        "message": "Processing speech..."
    }
)
```

- **Correlation ids:** add `event_id` (and re-use `occurred_at`) to every event so logs/debugging and SSE payloads are fully traceable.
- **Stage progress:** include `progress` (0–100) and `message` alongside `stage` on `StageProgressEvent` and `ProcessingStartedEvent`.

### 5.3 [NEW] `ProgressStore`

Rather than SSE subscribing directly to the `EventBus`, introduce a small progress store used by **both** REST and SSE:

### [NEW] `backend/app/application/events/progress_store.py`
```python
class ProgressStore:
    def upsert(self: None, media_id: str, stage: str, progress: int,
               message: str, status: str) -> None: ...
    def snapshot(self, media_id: str) -> Optional[dict]: ...
    def is_complete(self, media_id: str) -> bool: ...
```

- **REST `GET /status`** and **SSE** both read `progress_store.snapshot()`.
- Reconnected/late SSE clients immediately receive the latest `snapshot` (replay).
- Multiple front-end clients can observe the same job.
- Future WebSockets / CLI progress / notifications reuse the same store.

---

## 6. Bootstrapping Subscribers (single place)

### [NEW] `backend/app/bootstrap/event_subscribers.py`
```python
def register_media_subscribers(event_bus, repo, progress_store):
    event_bus.subscribe("MediaUploadedEvent",   lambda e: on_uploaded(e, repo, progress_store))
    event_bus.subscribe("ProcessingStartedEvent", lambda e: on_started(e, repo, progress_store))
    event_bus.subscribe("StageProgressEvent",    lambda e: on_progress(e, repo, progress_store))
    event_bus.subscribe("TranscriptCompletedEvent", lambda e: on_transcript(e, repo, progress_store))
    event_bus.subscribe("ChunksIndexedEvent",    lambda e: on_indexed(e, repo, progress_store))
    event_bus.subscribe("ProcessingFailedEvent", lambda e: on_failed(e, repo, progress_store))
```
Call this once in `backend/app/main.py` lifespan, alongside `init_db`. **No router imports this; no listeners live in HTTP.**

---

## 7. Backend Changes by File

### [MODIFY] `backend/app/services/workers/transcript_worker.py`
- Emit `ProcessingStartedEvent` (stage `audio_extraction`) before extraction.
- Emit `StageProgressEvent` at distinct milestones (e.g. started extraction `25`, audio ready `50`, transcription start `60`).
- On success, emit `TranscriptCompletedEvent` with `segments = [{"start_time","end_time","text"}]` **plus** `event_id` + `timestamp`.

### [MODIFY] `backend/app/services/workers/embedding_worker.py`
- Emit `StageProgressEvent` for `chunking` (`chunks: N`) and `embedding`.
- On upsert, emit `ChunksIndexedEvent` with `chunk_count` + correlation fields.

### [MODIFY] `backend/app/presentation/api/v1/media.py`
- Remove module-level dicts → use `MediaRepository`.
- Remove all `EventBus` subscription logic (moved to bootstrap handlers).
- `POST /media/upload`: write file, `repo.upsert`, then emit `MediaUploadedEvent` (Background task stays).
- `GET /media/{id}/status`: return `progress_store.snapshot()` (status + error + current progress), always 200 with `state` so late REST calls aren't stale.
- `GET /media/{id}/transcript`: `repo.get_transcript()`.
- `GET /media/{id}/stream` (SSE): on connect, **immediately yield the current `progress_store.snapshot()`**, then stream subsequent `StageProgressEvent` / `completed` / `failed` messages as they occur.

### [MODIFY] `backend/app/domain/media/entities.py`
Align `ProcessingStatus` with the user-visible pipeline stages:
```text
UPLOADED → AUDIO_EXTRACTION → TRANSCRIBING → CHUNKING → EMBEDDING → INDEXING → COMPLETED
```
- Add a `validate_transition(from, to)` helper laying out both `Retriable` and `Terminal` transitions, even if `retry/cancel/resume` aren't implemented now (define for the future):
  - `UPLOADED → AUDIO_EXTRACTION → TRANSCRIBING → CHUNKING → EMBEDDING → INDEXING → COMPLETED`
  - Any non-terminal → `FAILED`.
  - Allow `FAILED → <stage>` (Retry/Resume) transition.

---

## 8. Frontend Changes

### [MODIFY] `frontend/src/features/ingestion/useIngestion.ts`
- Parse the richer SSE payload (`stage`, `progress`, `message`, `status`) rather than guessing by `status` string.
- Update only the *matching stage*'s `progress` percentage, not a full finalize on any event.
- Drive UI from an explicit state machine `{uploaded, audio_extraction, transcribing, chunking, embedding, indexing, completed, failed}` matching the backend.
- Handle `onerror`: mark the current stage `failed` with the message (stop fabricating 100% success).

### [MODIFY] `frontend/src/features/ingestion/UploadDropzone.tsx`
- Render `progress` from SSE per stage (0–100 bar) and the last `message`.

### Existing (no change needed)
- `services/mediaService.ts` already provides `uploadMedia`, `getTranscript`, `createMediaProcessingStream`, all routed via `apiClient` + `API_BASE_URL` (no hardcoded `localhost`).

---

## 9. Verification Plan

### 9.1 Automated tests (add below)
```
cd backend
python -m pytest tests/test_ingestion_pipeline.py
python -m pytest
```

**Additional required unit/integration coverage** (from review):
1. **Worker unit tests** — assert each worker emits the correct domain events on success and on failure (mock `AIServiceBus`, `FFmpegAudioExtractor`, `vector_store`).
2. **Event-handler tests** — fake `MediaRepository` + `ProgressStore`; assert `StageProgress`, `TranscriptCompleted`, `ChunksIndexed`, `ProcessingFailed` update repo + store.
3. **SSE integration tests** — use `httpx`/`TestClient`; open the stream, publish events in order, assert payloads + ordering.
4. **Reconnect tests** — open SSE after processing already started; assert the initial snapshot + subsequent updates are delivered.
5. **Failure tests** — simulate FFmpeg, Whisper, embedding, and Qdrant failures; assert `FAILED` status + error propagation to REST and SSE.

### 9.2 Frontend
```bash
cd frontend
npx tsc --noEmit
```

### 9.3 Manual Verification
1. Launch backend + `npx tauri dev` → Navigate to **Upload Asset** (`view-ingestion`).
2. Drop a video/audio file into `UploadDropzone`.
3. Observe live progress transitions: **FFmpeg Audio Extraction → Faster-Whisper → Semantic Chunker → BGE Embedding → Qdrant Upsert → Completed**, with animated 0–100% per stage.
4. Navigate to **Synchronized Video Player** & **Library** → verify real extracted transcript segments and indexed asset.
5. **Reconnect test:** open the ingestion page *after* a job has started, confirm the UI immediately shows mid-progress state (snapshot), not a blank/0% page.
6. **Failure test:** upload a corrupt/non-media file → confirm stage fails, error message surfaces, no fake 100%.

---

## 10. Out of Scope / Future States (design acknowledged, not implemented now)

- `Retry`, `Cancel`, `Resume` actions — state machine defined in §7 so they can be added without rework.
- Persistence behind `MediaRepository` (SQLite/Postgres/Supabase adapter).
- WebSockets/CLI progress consumers reusing `ProgressStore`.
- True event-store persistence (currently in-memory) for full replay across restarts.
- Per-event durability (Outbox pattern) so event→repo updates can be retried transactionally.