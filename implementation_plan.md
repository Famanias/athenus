# Implementation Plan — Phase 3: Unified Knowledge Lifecycle

Formalize a complete, unified ingestion lifecycle for every uploaded lecture resource, recording stage transitions, execution timestamps, progress percentages, and audit logs directly in SQLite.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions for Phase 3:**
> 1. **Persistent Processing Log Schema (`ProcessingLogTable`)**: Create a dedicated SQLite audit table recording every stage event (`audio_extraction`, `transcription`, `chunking`, `embedding`, `indexing`) with timestamps, stage progress, messages, and error tracebacks.
> 2. **Lifecycle Event Synchronization**: Extend `media_event_handlers.py` and `ProgressStore` so that every published domain event automatically appends an audit record to SQLite.
> 3. **Processing History Diagnostic Endpoint (`GET /api/v1/media/{id}/history`)**: Add a REST endpoint returning the full timestamped processing history log for any media asset.
> 4. **Workflow Checkpoint**: Stop after Phase 3 verification and self-review to request user approval before beginning Phase 4.

---

## Proposed Changes

### Database Layer (`backend/app/infrastructure/db/`)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- **[NEW]** Add `ProcessingLogTable` SQLModel and SQLAlchemy ORM class:
  - `id`: Primary key (autoincrement int or string ID)
  - `media_id`: Indexed string
  - `workspace_id`: Indexed string
  - `stage`: String (`audio_extraction`, `transcription`, `chunking`, `embedding`, `indexing`)
  - `status`: String (`processing`, `completed`, `failed`)
  - `progress`: Integer (0–100%)
  - `message`: Optional string
  - `error_message`: Optional string
  - `created_at`: Datetime timestamp

---

### Application Event Handlers & Event Bus (`backend/app/application/events/`)

#### [MODIFY] [media_event_handlers.py](file:///e:/repos/athenus/backend/app/application/events/media_event_handlers.py)
- Update handlers for `ProcessingStartedEvent`, `StageProgressEvent`, `TranscriptCompletedEvent`, `ChunksIndexedEvent`, and `ProcessingFailedEvent` to persist audit records to `ProcessingLogTable` in SQLite.

---

### Presentation & API Layer (`backend/app/presentation/api/v1/`)

#### [MODIFY] [media.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py)
- **[NEW]** Add endpoint `GET /api/v1/media/{media_id}/history` returning list of `ProcessingLogDTO` entries sorted by timestamp.

---

### Verification & Test Suite (`backend/tests/`)

#### [NEW] [test_knowledge_lifecycle.py](file:///e:/repos/athenus/backend/tests/test_knowledge_lifecycle.py)
- Add lifecycle audit test:
  - Simulate media processing across all pipeline stages.
  - Query `GET /api/v1/media/{id}/history`.
  - Assert complete timestamped progression from `audio_extraction` to `indexing` / `completed` is recorded in SQLite.

---

## Verification Plan

### Automated Tests
1. **Knowledge Lifecycle Pytest**:
   ```bash
   cd backend
   python -m pytest tests/test_knowledge_lifecycle.py
   python -m pytest
   ```
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Verification
1. Upload a video file in **Pipelines** (`view-ingestion`).
2. Call `GET http://localhost:8000/api/v1/media/{media_id}/history` in browser or curl.
3. Verify that a complete timestamped JSON log array showing progress transitions (25% $\rightarrow$ 60% $\rightarrow$ 75% $\rightarrow$ 90% $\rightarrow$ 100%) is returned.
