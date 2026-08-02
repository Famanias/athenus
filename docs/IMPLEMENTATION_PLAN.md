# IMPLEMENTATION_PLAN.md

# Athenus Knowledge OS — Final Implementation Plan

---

## Overview

This document defines the production engineering roadmap for **Athenus Knowledge OS**.

Following Iteration 3 architectural review feedback, implementation is driven by **Vertical Slice Development** grounded in **Bounded Contexts**, an **AI Service Bus**, an asynchronous **Workflow Engine**, and **Architecture Decision Records (ADRs)**.

---

## Core Engineering Principles

1. **Product Identity**: Athenus is an **AI-native Knowledge Operating System (Knowledge OS)**. RAG is one retrieval subsystem, and video is one knowledge plugin.
2. **Bounded Context Architecture**: The backend is organized into 7 distinct Bounded Contexts (`Knowledge`, `Learning`, `Workspace`, `AI`, `User`, `Evaluation`, `Media`), keeping pure Python domain rules isolated from frameworks and databases.
3. **AI Service Bus & Model Registry**: All AI operations flow through a centralized AI Service Bus coordinating capability routing, streaming, retries, caching, and model metadata tracking via a Model Registry.
4. **Workload Scheduler & Event-Driven Processing**: Heavy asynchronous processing (transcription, embedding, graph construction) is scheduled and prioritized by a Workload Scheduler acting as the local OS for AI workloads.
5. **ADR-Driven Decision Making**: Every architectural decision is recorded in `docs/adr/` before implementation code is written.

---

## Phase 1: Version 0.1 MVP (Video Learning Vertical Slice)

Phase 1 delivers the foundational **Video Learning Assistant** built on the new Bounded Context and AI Service Bus architecture.

```
Upload Video ──► Media Context ──► Event Bus ──► Workload Scheduler ──► Background Workers
                                                                               │
RAG Response ◄── AI Service Bus ◄── 8-Stage Retrieval ◄── Knowledge Context indexed ◄┘
```

---

### Slice 1: Bounded Context Domain Core, AI Service Bus & ADR Process

**Objective**: Establish Bounded Context package layouts, domain entities, Event Bus, AI Service Bus with Model Registry, Workload Scheduler, and initialize Architecture Decision Records (ADRs).

#### Tasks:
* **ADR Initialization**: Create initial Architecture Decision Records under `docs/adr/`:
  * `0001-local-first-knowledge-os-architecture.md`
  * `0002-sqlite-embedded-metadata-store.md`
  * `0003-qdrant-embedded-vector-store.md`
  * `0004-ai-service-bus-and-capability-routing.md`
* **Bounded Context Package Structure**: Create Python package boundaries under `backend/app/domain/`:
  * `knowledge/`, `learning/`, `workspace/`, `ai/`, `user/`, `evaluation/`, `media/`.
* **Domain Entity Definitions**:
  * `MediaItem` & `TranscriptChunk` in `media/` & `knowledge/`.
  * `Workspace` in `workspace/`.
  * `UserMemory` in `user/`.
  * `ConceptNode` & `KnowledgeGraphProtocol` in `knowledge/`.
  * `BaseAgent` protocol contract in `ai/`.
* **AI Service Bus & Model Registry**: Implement `AIServiceBus`, `ModelRegistry`, and `ProviderRouter` in `backend/app/domain/ai/`.
* **Workload Scheduler**: Implement `WorkloadScheduler` handling resource auto-detection (CPU/VRAM) and job prioritization.
* **SQLite Infrastructure & Capability Adapters**:
  * SQLModel repository implementations.
  * Concrete local adapters (`OllamaTextGenAdapter`, `FasterWhisperSTTAdapter`, `SentenceTransformersEmbeddingAdapter`, `EmbeddedQdrantVectorStoreAdapter`).

#### Deliverables & Tests:
* Unit tests for domain entities in each Bounded Context with zero external dependencies.
* Unit tests for `ModelRegistry` resolution and `AIServiceBus` routing.
* ADR files created and indexed in `docs/adr/`.

---

### Slice 2: Event-Driven Video Processing & Asynchronous Worker Pipeline

**Objective**: Implement asynchronous video ingestion pipeline coordinated by the Workload Scheduler, emitting real-time progress via WebSocket/SSE.

#### Tasks:
* Implement FFmpeg audio extractor in `media/` context.
* Implement Workflow Engine & Worker Suite:
  * `TranscriptWorker`: Listens for `MediaUploadedEvent`, executes `ISpeechToTextCapability` via AI Service Bus, emits `TranscriptCompletedEvent`.
  * `EmbeddingWorker`: Chunks transcript with timestamp bounds `[start_time, end_time]`, generates embeddings via AI Service Bus, indexes vectors into Embedded Qdrant.
* Implement Application Use Cases & REST/SSE endpoints (`/api/v1/media/upload`, `/api/v1/media/{media_id}/status`, `/api/v1/media/{media_id}/stream`).

#### Deliverables & Tests:
* Asynchronous integration test processing video file through `MediaUploadedEvent` $\rightarrow$ `TranscriptWorker` $\rightarrow$ `EmbeddingWorker`.
* Verified progress events over SSE/WebSocket.

---

### Slice 3: 8-Stage Layered Retrieval & Decomposed Workspace Intelligence

**Objective**: Implement 8-stage retrieval pipeline (Query Rewrite $\rightarrow$ Intent Detection $\rightarrow$ Context Injection $\rightarrow$ Graph Traversal $\rightarrow$ Hybrid Search $\rightarrow$ Re-Ranking $\rightarrow$ Context Compression $\rightarrow$ Grounded Prompt Assembly) managed by decomposed Workspace Intelligence components.

#### Tasks:
* Implement decomposed Workspace Intelligence components (`MemoryManager`, `RetrievalManager`, `ContextBuilder`, `RecommendationEngine`).
* Implement 8-Stage Retrieval Engine (`MultiStageRetriever`).
* Implement REST/WebSocket query controller (`POST /api/v1/chat/query`) returning streaming LLM responses with clickable citation badges `[MM:SS - MM:SS]`.

#### Deliverables & Tests:
* Retrieval evaluation benchmark confirming Query Rewriting + Hybrid Search + Re-ranking + Context Compression accuracy.

---

### Slice 4: Tauri Desktop Shell & Presentation Layer

**Objective**: Build React/Next.js frontend hosted in Tauri desktop shell with synchronized video player, transcript viewer, chat, and Workload Scheduler progress monitor.

#### Tasks:
* Configure Tauri Desktop Shell (`src-tauri/`) with dynamic port assignment, ephemeral bearer token authentication, and graceful `SIGTERM` shutdown.
* Build Next.js UI Components (Synced Video Player, Interactive Transcript, Streaming Chat, Workload Monitor).

#### Deliverables & Tests:
* Executable Tauri desktop application build end-to-end test.

---

### Slice 5: First-Class Evaluation Subsystem & Verification

**Objective**: Execute automated evaluation suite, test 100% offline capability, and finalize Phase 1 release bundle.

#### Tasks:
* Run Evaluation Framework benchmarking Retrieval Precision/Recall ($k=5,10$), Citation Groundedness, Latency, and Token Cost.
* Perform offline verification with network interface disconnected.
* Record Phase 1 results in [walkthrough.md](file:///C:/Users/PC/.gemini/antigravity-ide/brain/f8e4a25b-4ceb-4a0c-a61f-26070e7f0404/walkthrough.md).

---

## Strategic Roadmap: Future Phases

```
Phase 1 (V0.1) ──► Phase 2 (V0.2) ──► Phase 3 (V0.3) ──► Phase 4 (V0.4) ──► Phase 5 (V1.0)
 Video RAG MVP      Workspaces &       Knowledge Graph    Active Recall      Specialized
 Core Foundation    Multi-Video        & Multimodal       & Learning Tools   Agent Suite
```

### Phase 2: Workspaces & Multi-Video Search (V0.2)
* Multi-video workspace organization & global hybrid search.
* 4-Layer Memory persistence across workspaces.

### Phase 3: Knowledge Graph & Multimodal Retrieval (V0.3)
* Knowledge Graph Worker populating conceptual relationships across media items.
* Visual Keyframe Sampling & PaddleOCR/Tesseract slide text extraction.

### Phase 4: Active Recall & Active Learning Tools (V0.4)
* Summary Worker, Quiz Worker, and Flashcard Worker (Anki SM-2/FSRS export).
* Personalized learning paths and concept gap detection.

### Phase 5: Specialized Agent Suite & Cloud Collaboration (V1.0)
* Agent Coordinator managing specialized agents (`PlannerAgent`, `RetrieverAgent`, `QuizAgent`, `FlashcardAgent`, `CitationValidatorAgent`).
* Multi-user cloud synchronization mode.
