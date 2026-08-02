# CONTEXT.md

# Project Context: Athenus Knowledge OS

This document serves as the living memory of the project. It records the active scope, architectural status, and accepted decisions.

---

# Project Name

**Athenus Knowledge OS**

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
* **Automated Tests**: 25 of 25 unit and integration tests passing in `backend/tests/`.

---

# Primary Objective

Build a flagship open-source AI Engineering project demonstrating:
* Modern RAG (8-Stage Layered Retrieval)
* Multimodal AI (Video, Audio, Keyframes)
* Local-First AI (Ollama, Faster-Whisper, BGE Small, Embedded Qdrant)
* Agentic AI Workflows (`AgentCoordinator`, `PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent`)
* Production Engineering & Clean Architecture (7 Bounded Contexts)

---

# Application Architecture

Desktop-first application using a local web architecture.

* **Frontend**: React + Next.js + TypeScript + Tailwind CSS
* **Backend**: FastAPI (Python 3.11)
* **Desktop Shell**: Tauri (Rust) with sidecar bearer token authorization
* **Database**: SQLite (SQLModel) for Desktop; PostgreSQL for Cloud/Multi-user
* **Vector Database**: Embedded Qdrant (`./data/qdrant`)

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
* **AI Service Bus & Model Registry Architecture**: Centralized gateway for capability routing and model metadata resolution (`llama3:8b`, `whisper-base`, `bge-small-en-v1.5`).
* **Workload Scheduler Subsystem**: Resource-aware AI task concurrency throttle.
* **Event-Driven Task Queue & Background Workers**: Asynchronous worker pipeline (`TranscriptWorker`, `EmbeddingWorker`, `KnowledgeGraphWorker`, `SummaryWorker`, `QuizWorker`, `FlashcardWorker`).
* **Decomposed Workspace Intelligence**: Decomposed into `MemoryManager`, `RetrievalManager`, `ContextBuilder`, `RecommendationEngine`, and `AgentCoordinator`.
* **4-Layer Memory Model**: Short-Term Memory, Working Memory, Long-Term Memory, Semantic Memory (Knowledge Graph).
* **Separation of Storage vs Memory**: Knowledge Storage (immutable chunks/embeddings) vs User Memory (progress/notes/SM-2 flashcards).
* **8-Stage Layered Retrieval Engine**: Query Rewrite, HyDE, Intent Detection, Context Injection, Knowledge Graph Traversal, Hybrid Search (Vector + BM25), Cross-Encoder Re-Ranking, Context Compression, Grounded Prompt Assembly.
* **Capability-Based Provider Abstraction & Provider Router**
* **Architecture Decision Record (ADR) Process**: Established under `docs/adr/` (`0001` - `0004`).
* **First-Class AI Evaluation Subsystem**: Automated benchmark suite evaluating Retrieval Precision/Recall@K, Groundedness, Latency, and Token Cost.
