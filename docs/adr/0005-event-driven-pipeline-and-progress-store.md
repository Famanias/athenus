# 5. Event-Driven Ingestion Pipeline & Shared Progress Store

* **Status**: Accepted
* **Date**: 2026-08-02
* **Context**: Background video ingestion involves multi-stage asynchronous processing (FFmpeg audio extraction, Faster-Whisper ASR, semantic chunking, vector embedding, and Qdrant indexing). The HTTP presentation layer (`media.py`) must not own domain background processing or raw dictionary storage, and both REST (`/status`) and SSE (`/stream`) endpoints must read from a single authoritative progress source.

## Decision
We decouple HTTP presentation routes from domain background execution by implementing:
1. A **`MediaRepository`** abstraction interface hiding dictionary/SQL storage details from HTTP controllers.
2. An application-layer event handler suite (`media_event_handlers.py`) subscribing to domain events (`MediaUploadedEvent`, `ProcessingStartedEvent`, `StageProgressEvent`, `TranscriptCompletedEvent`, `ChunksIndexedEvent`, `ProcessingFailedEvent`).
3. A centralized **`ProgressStore`** tracking live stage snapshots (`current_stage`, `overall_progress`, `status`, `message`, `error`) that immediately replays current state to connecting SSE streams.

## Consequences
* **Positive**: Complete decoupling of HTTP controllers from domain events, single source of truth for REST status and SSE streams, instant state replay for reconnected client streams, and clean extensibility for future SQLite/Postgres persistence drivers.
* **Negative**: Additional event handler wiring and progress store synchronization primitives.
