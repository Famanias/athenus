# Implementation Plan — Centralized `TelemetryService` & Single System of Record Architecture

This revised implementation plan establishes a **Centralized `TelemetryService`** for the Athenus pipeline. It eliminates dual progress stores, removes scattered magic percentage numbers, and establishes SQLite `ArtifactJobTable` as the single system of record across all pipeline workers, API endpoints, SSE streams, and React UI components.

---

## 🏗️ Architectural Overview & Data Topology

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            PIPELINE WORKERS                                 │
│  (PersistentIngestionWorker, TranscriptWorker, EmbeddingWorker, GraphWorker) │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                Emits Domain Events (StageProgressEvent, etc.)
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     CENTRALIZED TELEMETRY SERVICE                           │
│                       (telemetry_service.py)                                │
│  - INGESTION_STAGES Registry: Single source for stage metadata & progress    │
│  - Single DB Writer: Writes to SQLite ArtifactJobTable                      │
│  - Event Streamer: Broadcasts SSE Telemetry Payload                         │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
                        Single Authoritative DB Write
                                       │
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SQLITE DATABASE (ArtifactJobTable)                       │
│  job_id: "ingestion_med_xxx" | status: "processing" | stage: "transcription"│
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
    REST API Jobs Endpoint                               SSE Stream Broadcast
  (/media/workspace/jobs)                              (/media/stream)
  (Page Refresh Rehydration)                           (Live UI Updates)
            │                                                     │
            └──────────────────────────┬──────────────────────────┘
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     REACT FRONTEND (useIngestion.ts)                        │
│   Reads SSE Telemetry + REST Fallback -> Single Stepper UI (0-100%)         │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Milestone Breakdown

### Milestone 0: Audit All `ArtifactJobTable` Writers & Identity Rules

Before modifying code, audit every file reading or writing `ArtifactJobTable` to establish strict identity rules:

| Component | File Path | Creates/Writes Job? | Target Key | Artifact Type | Format |
|---|---|---|---|---|---|
| Ingestion Queue | `persistent_ingestion_queue.py` | ✅ Yes | `media_id` | `"ingestion"` | `ingestion_{media_id}` |
| Graph Worker | `graph_extraction_worker.py` | ✅ Yes | `media_id` | `"graph"` | `graph_{media_id}` |
| Flashcard Engine | `flashcard_service.py` | ✅ Yes | `workspace_id` | `"flashcards"` | `flashcards_{workspace_id}` |
| Quiz Engine | `quiz_service.py` | ✅ Yes | `workspace_id` | `"quiz"` | `quiz_{workspace_id}` |
| REST Router | `media.py` | 🔍 Read Only | `workspace_id` | `"ingestion"` | N/A |

---

### Milestone 1: Focused `TelemetryService` & `INGESTION_STAGES` Registry (Backend)

#### [NEW] [telemetry_service.py](file:///e:/repos/athenus/backend/app/domain/telemetry/telemetry_service.py)
- Create a focused `TelemetryService` class:
  - **`INGESTION_STAGES` Registry**: Central dictionary defining stage metadata, descriptions, and progress percentages in a single place:
    ```python
    INGESTION_STAGES = {
        "queued": {"progress": 5, "message": "Enqueued in persistent ingestion queue..."},
        "audio_extraction": {"progress": 25, "message": "Extracting 16kHz mono WAV audio..."},
        "transcription": {"progress": 60, "message": "Transcribing speech using Faster-Whisper ASR..."},
        "chunking": {"progress": 75, "message": "Chunking transcript text..."},
        "vector_indexing": {"progress": 85, "message": "Storing vector embeddings in Qdrant..."},
        "collect_context": {"progress": 90, "message": "Retrieving context for graph extraction..."},
        "llm_generation": {"progress": 95, "message": "Extracting domain concepts with LLM..."},
        "ready": {"progress": 100, "message": "Ingestion complete."},
    }
    ```
  - **Event Subscriber**: Subscribes to `StageProgressEvent`, `ProcessingStartedEvent`, `TranscriptCompletedEvent`, `ChunksIndexedEvent`, and `ProcessingFailedEvent`.
  - **Single DB Writer**: Updates SQLite `ArtifactJobTable` for `job_id = f"ingestion_{media_id}"`.
  - **SSE Telemetry Broadcaster**: Broadcasts live progress payloads to connected client streams.

#### [MODIFY] [media_event_handlers.py](file:///e:/repos/athenus/backend/app/application/events/media_event_handlers.py)
- Route incoming pipeline domain events through `TelemetryService`.
- Deprecate duplicate in-memory `ProgressStore` to eliminate dual write paths and RAM/SQLite state drift.

---

### Milestone 2: REST & SSE Telemetry Stream Harmonization

#### [MODIFY] [media.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py)
- Update `/media/workspace/{workspace_id}/jobs` to read directly from `ArtifactJobTable` updated by `TelemetryService`.

---

### Milestone 3: Frontend SSE Streaming & Fallback Polling (Frontend)

#### [MODIFY] [useIngestion.ts](file:///e:/repos/athenus/frontend/src/features/ingestion/useIngestion.ts)
- Connect live UI updates to SSE stream broadcasts from `TelemetryService`.
- Retain REST polling (`GET /media/workspace/{id}/jobs`) strictly as a rehydration fallback on page refresh.

---

## 🧪 Comprehensive Verification & Edge Case Matrix

| Edge Case Test | Test Procedure | Expected Outcome |
|---|---|---|
| **Multi-Video Queue Concurrency** | Upload Video A, Video B, Video C in rapid succession | Video A processes, Videos B & C enter persistent queue (`Queued #1`, `#2`) without state overwriting or race conditions |
| **Failed Transcription Recovery** | Trigger upload with corrupted audio track | Job updates to `status: "failed"`, `stage: "failed"`, logs error in SQLite, worker queue advances to next video |
| **Server Restart Mid-Processing** | Restart backend process while Video A is at 60% | `boot_recovery()` queries SQLite, finds job, and resumes processing automatically |
| **Browser Refresh Mid-Processing** | Refresh browser while Video A is transcribing | REST fallback `/jobs` rehydrates active job state and resumes live SSE progress bar |
| **No-Concepts Edge Case** | Upload audio with zero speech | Pipeline marks job `failed`, logs descriptive message, releases queue lock |

---

## 🧪 Automated Test Suite Commands

```bash
# 1. Backend Telemetry & Ingestion Queue Tests
python -m pytest tests/test_ingestion_pipeline.py
python -m pytest tests/test_knowledge_graph.py

# 2. Full Backend Test Suite
python -m pytest tests/

# 3. Frontend Type & Build Verification
cd frontend
npx tsc --noEmit
npm run build
```