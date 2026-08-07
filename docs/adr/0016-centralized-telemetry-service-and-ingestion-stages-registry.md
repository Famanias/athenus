# ADR 0016: Centralized Telemetry Service & Ingestion Stages Registry

## Status
Approved

## Context
Previously, ingestion progress calculations were scattered across media handlers, event buses, and frontend hooks with hardcoded stage checks (`if stage == "transcription": progress = 60`). This created status drift where SSE listeners and SQLite job tables recorded mismatched stage percentages and message states.

## Decision
1. Created `TelemetryService` in `backend/app/domain/telemetry/telemetry_service.py` with a single, immutable metadata registry (`INGESTION_STAGES`):
   - `queued` (5%) $\rightarrow$ `audio_extraction` (25%) $\rightarrow$ `transcription` (60%) $\rightarrow$ `chunking` (75%) $\rightarrow$ `vector_indexing` (85%) $\rightarrow$ `collect_context` (90%) $\rightarrow$ `llm_generation` (95%) $\rightarrow$ `ready` (100%).
2. Configured media event handlers to record progress directly into the SQLite `ArtifactJobTable` as the single backend system of record.
3. Decoupled telemetry progress calculation from worker retry logic, analytics, and projections.

## Consequences
- **Positive**: Standardized progress percentage calculations across all ingestion stages; eliminated status drift between backend event handlers and frontend progress bars.
- **Negative**: Requires updating `INGESTION_STAGES` metadata dictionary when introducing new pipeline stages.
