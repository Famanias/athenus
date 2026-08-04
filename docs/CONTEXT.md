# CONTEXT.md

# Project Context: Athenus

This document serves as the living memory of the project. It records the active scope, architectural status, and accepted decisions.

---

# Project Name

**Athenus**

---

# Vision

Build a local-first, AI-native learning platform (Knowledge Operating System) that transforms educational content into interactive, searchable, and explainable learning experiences.

The platform supports multiple knowledge sources while remaining modular, extensible, offline-capable, and provider-agnostic.

---

# Current Scope & Content Support

Primary knowledge sources supported:
* Educational Videos & Audio Transcripts
* Concept Graphs & Slide Keyframes

Future knowledge sources:
* PDFs
* Websites & Documentation
* GitHub repositories
* eBooks & Research Papers

---

# Current Phase & Implementation Status

**Current Phase**: Version 1.0 Final Release Complete (Phases 1 through 5 fully implemented and verified).

**Status**:
* **Phase 1 (v0.1 MVP)**: Local Video Upload, Audio Extraction (FFmpeg), Faster-Whisper Transcription, Semantic Chunker, Embedded Qdrant Vector Indexing, 8-Stage Retrieval, RAG Chat with Timestamp Citations, Next.js UI, Tauri Desktop Shell Config.
* **Phase 2 (v0.2)**: Multi-video Workspace Management (`WorkspaceService`, `/api/v1/workspaces`).
* **Phase 3 (v0.3)**: Knowledge Graph Engine (`KnowledgeGraphService`), Keyframe Sampling (`FrameExtractor`), `KnowledgeGraphWorker`, Concept Prerequisite APIs (`/api/v1/graph`).
* **Phase 4 (v0.4)**: Active Recall Learning Tools: `SummaryWorker`, `QuizWorker`, `FlashcardWorker` (Anki SM-2 export), Learning APIs (`/api/v1/learning`).
* **Phase 5 (v1.0)**: Agentic AI Suite (`AgentCoordinator`, `PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent`), Agent APIs (`/api/v1/agents`).
* **Frontend Presentation Layer (Phases A-F Complete)**: Next.js + React + Tauri Desktop App (`npx tauri dev`) with Athena Theme (`#051424` & `#e9c349`), custom typography (`TT Carvist`, `Geist`, `JetBrains Mono`), Zustand state store, and 6 domain feature modules (`features/chat/`, `features/video/`, `features/transcript/`, `features/library/`, `features/flashcards/`, `features/quiz/`, `features/graph/`, `features/ingestion/`, `features/settings/`).
* **Runtime Verification**: End-to-end integration verified. Native Tauri desktop app (`npx tauri dev`) communicates with FastAPI backend RAG query endpoint (`python app/main.py`).
* **Automated Tests**: 56 of 56 unit and integration tests passing in `backend/tests/`.
* **Clean UI & Real Data Pipeline**: All sample/mock data removed; clean empty states implemented across all 6 frontend feature modules (`features/library/`, `features/video/`, `features/transcript/`, `features/quiz/`, `features/flashcards/`, `features/graph/`).
* **Event-Driven Pipeline & Single Progress Source**: Asynchronous video ingestion pipeline decoupled from HTTP layer using `MediaRepository`, application-layer event handlers (`media_event_handlers.py`), and snapshot replay via `ProgressStore`.
* **SQLite System Settings Persistence**: `SystemSettings` table in SQLite (`./data/athenus.db`) managed via `SettingsService` and auto-rehydrated on application launch.
* **Local Ollama Model Discovery**: Pure local filesystem model discovery (`OllamaModelScanner`) with dynamic dropdown selection in LLM settings.
* **Dockerized Development Architecture**: Single-command web stack (`docker compose up -d --build` → http://localhost:3000) with containerized FastAPI backend, Next.js frontend, and Ollama; GPU acceleration via an overlay file (`docker-compose.gpu.yml`, NVIDIA Container Toolkit); Tauri desktop shell remains native against the containerized backend. See [`docs/DEPLOYMENT.md`](DEPLOYMENT.md) and [`docs/ONBOARDING.md`](ONBOARDING.md).

---

# Primary Objective

Build a flagship open-source AI Engineering project demonstrating:
* Modern RAG (8-Stage Layered Retrieval)
* Multimodal AI (Video, Audio, Keyframes)
* Local-First AI (Ollama Scanner, Faster-Whisper, BGE Small, Embedded Qdrant)
* Agentic AI Workflows (`AgentCoordinator`, `PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent`)
* Production Engineering & Clean Architecture (7 Bounded Contexts)

---

# Application Architecture

Desktop-first application using a local web architecture.

* **Frontend**: React + Next.js 16 + TypeScript + Vanilla CSS Design System
* **Backend**: FastAPI (Python 3.11)
* **Desktop Shell**: Tauri (Rust) with sidecar bearer token authorization
* **Database**: SQLite (SQLModel) for Desktop; PostgreSQL for Cloud/Multi-user
* **Vector Database**: Embedded Qdrant (`./data/qdrant`) with in-memory fallback on disk lock contention

---

# Deployment Philosophy

Supports three deployment modes:
* **Local Mode (Default)**: Runs 100% offline on user's machine.
* **Hybrid Mode**: Local Whisper/BGE + optional cloud LLM reasoning (Groq/OpenRouter/Gemini/Claude).
* **Cloud Mode**: Docker / Railway / Coolify multi-user cloud deployment.

---

# Accepted Architectural Decisions

* **Desktop-First & Local-First Architecture**
* **Domain-Driven Architecture with 7 Bounded Contexts**: `Knowledge`, `Learning`, `Workspace`, `AI`, `User`, `Evaluation`, `Media`.
* **AI Service Bus & Model Registry Architecture**: Centralized gateway for capability routing and model metadata resolution (`whisper-base`, `bge-small-en-v1.5`).
* **Workload Scheduler Subsystem**: Resource-aware AI task concurrency throttle.
* **Event-Driven Task Queue & Background Workers**: Asynchronous worker pipeline (`TranscriptWorker`, `EmbeddingWorker`, `KnowledgeGraphWorker`, `SummaryWorker`, `QuizWorker`, `FlashcardWorker`).
* **Decomposed Workspace Intelligence**: Decomposed into `MemoryManager`, `RetrievalManager`, `ContextBuilder`, `RecommendationEngine`, and `AgentCoordinator`.
* **4-Layer Memory Model**: Short-Term Memory, Working Memory, Long-Term Memory, Semantic Memory (Knowledge Graph).
* **Separation of Storage vs Memory**: Knowledge Storage (immutable chunks/embeddings) vs User Memory (progress/notes/SM-2 flashcards).
* **8-Stage Layered Retrieval Engine**: Query Rewrite, HyDE, Intent Detection, Context Injection, Knowledge Graph Traversal, Hybrid Search (Vector + BM25), Cross-Encoder Re-Ranking, Context Compression, Grounded Prompt Assembly.
* **Capability-Based Provider Abstraction & Provider Router**
* **MediaRepository & ProgressStore Ingestion Pattern**: Decoupled HTTP layer using repository abstractions and domain-event snapshot streaming (`docs/adr/0005-event-driven-pipeline-and-progress-store.md`).
* **Multi-Workspace & Multi-Session Architecture**: In-app workspace switching, lazy chat session creation, and explicit confirmation modals (`docs/adr/0006-multi-workspace-and-multi-session-architecture.md`).
* **SQLite Settings Persistence & Local Ollama Model Scanner**: Persistent settings table in SQLite and pure filesystem scanner (`docs/adr/0007-sqlite-settings-persistence-and-local-ollama-scanner.md`).
* **Dockerized Development Architecture**: Containerized web stack (backend/frontend/Ollama), GPU overlay for NVIDIA acceleration, native Tauri desktop, single `.env` for native + container runtimes, GPU-aware Whisper settings (`docs/adr/0008-dockerized-development-architecture.md`).
* **Architecture Decision Record (ADR) Process**: Established under `docs/adr/` (`0001` - `0008`).
* **First-Class AI Evaluation Subsystem**: Automated benchmark suite evaluating Retrieval Precision/Recall@K, Groundedness, Latency, and Token Cost.
* **Machine Learning & Deep Learning Reviewer Guide**: Comprehensive architectural theory reference in `docs/ML_DL_ARCHITECTURE.md`.
