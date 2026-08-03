# ADR 0003: Unified Ingestion Stage Machine & Persistent Audit Logging

* **Status**: Accepted & Implemented
* **Date**: 2026-08-03
* **Context**: Video ingestion stage progress was stored in RAM in `ProgressStore`. If ingestion stalled or failed, no execution logs or telemetry history existed to diagnose why the failure occurred.
* **Decision**: Implement `ProcessingLogTable` in SQLite database and automatically persist stage progress events (`upload`, `audio_extraction`, `transcription`, `chunking`, `vector_indexing`) via `progress_store.record_stage_progress()`. Expose `GET /api/v1/media/{media_id}/history` endpoint.
* **Alternatives Considered**:
  - *Text Log Files on Disk*: Difficult to query programmatically via REST API or UI.
* **Rationale**: Relational table audit logging provides structured, timestamped diagnostic telemetry accessible directly by frontend UI and REST tools.
* **Trade-offs**: Slightly increased database writes per ingestion run, mitigated by fast SQLite transactions.
