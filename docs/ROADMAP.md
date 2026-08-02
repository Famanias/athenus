# ROADMAP.md

# Athenus Knowledge OS — Strategic Roadmap (Completed to Version 1.0)

---

## Version 0.1 MVP — Video Learning Assistant (Phase 1 — COMPLETED)
* **Slice 1**: Core Domain Architecture, AI Service Bus, Model Registry, Workload Scheduler.
* **Slice 2**: Video Ingestion, FFmpeg Audio Extraction, Faster-Whisper `TranscriptWorker`, Embedded Qdrant `EmbeddingWorker`.
* **Slice 3**: 8-Stage Layered Retrieval Engine, `WorkspaceIntelligenceManager`, RAG Chat API with Timestamp Citations.
* **Slice 4**: Tauri Desktop Shell Configuration & Next.js Presentation Layer (Synced Player, Interactive Transcript, Citation Badges).
* **Slice 5**: Evaluation Subsystem & Comprehensive Documentation Suite.

---

## Version 0.2 — Workspaces & Multi-Video Search (Phase 2 — COMPLETED)
* Multi-video workspace organization & collection management (`WorkspaceService`).
* REST endpoints: `POST /api/v1/workspaces`, `GET /api/v1/workspaces`.

---

## Version 0.3 — Knowledge Graph & Multimodal Retrieval (Phase 3 — COMPLETED)
* Automatic Knowledge Graph construction linking concepts (`KnowledgeGraphService`).
* Visual keyframe extraction (`FrameExtractor`).
* REST endpoints: `GET /api/v1/graph/prerequisites/{concept_id}`.

---

## Version 0.4 — Active Recall & Active Learning Tools (Phase 4 — COMPLETED)
* `SummaryWorker`, `QuizWorker`, and `FlashcardWorker` (Anki SM-2 export).
* REST endpoints: `GET /api/v1/learning/quizzes/{media_id}`, `GET /api/v1/learning/flashcards/{media_id}`.

---

## Version 1.0 — Agentic AI Suite & Production Release (Phase 5 — COMPLETED)
* Agent Coordinator managing `PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent`.
* REST endpoints: `POST /api/v1/agents/coordinate`, `GET /api/v1/agents/list`.
* Complete documentation & production deployment guides.
