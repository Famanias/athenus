# APPLICATION_ARCHITECTURE.md

# AI Learning Platform (Knowledge OS)

## Application Architecture & Deployment Strategy

---

# Overview

The AI Learning Platform is designed as a **local-first, offline-capable Knowledge Operating System (Knowledge OS)** that transforms educational content into an interactive learning experience.

Unlike traditional Learning Management Systems (LMS) or simple RAG chatbots, the platform is an extensible AI engineering system that ingests knowledge from multiple sources, builds a unified knowledge base, and provides intelligent learning assistance.

Version 1 focuses exclusively on **video content**, but the architecture must be designed so additional content sources can be integrated without redesigning the system.

---

# Design Philosophy

The platform follows five core principles:

* Local-first
* Offline-capable
* Privacy-first
* Provider-agnostic
* Plugin-based

Cloud services enhance the platform but should never be required for core functionality.

---

# Application Type

The platform should be developed as a **desktop-first application powered by a local web architecture**.

This combines the advantages of modern web development with the capabilities of native desktop software.

Recommended stack:

* **Desktop Shell:** Tauri (preferred) or Electron
* **Frontend:** React + Next.js + TypeScript
* **Backend:** FastAPI (Python)
* **Database:** SQLite for local desktop mode (via SQLModel / SQLAlchemy + Alembic); PostgreSQL for cloud & multi-user deployments
* **Vector Database:** Embedded Qdrant (`qdrant-client` local storage by default; Docker or Qdrant Cloud optional)
* **AI Models:** Local by default

---

# Why Desktop-First?

Educational videos are often large (hundreds of MB to multiple GB).

The application needs direct access to:

* Local filesystem
* GPU acceleration
* Local AI models
* Background processing
* Docker containers
* Large file indexing
* Persistent caches

These capabilities are significantly easier to implement in a desktop environment than in a browser.

---

# Why Use Web Technologies?

Using React and Next.js provides:

* Faster UI development
* Better developer experience
* Cross-platform compatibility
* Large ecosystem
* Reusable frontend architecture

The desktop shell simply hosts the web application.

---

# High-Level Architecture

```text
                    Tauri Desktop Shell
                            │
            ┌───────────────┴───────────────┐
            │                               │
     React + Next.js UI             FastAPI Backend
            │                               │
            └───────────────┬───────────────┘
                            │
                  Internal REST API
                            │
      ┌─────────────────────┼─────────────────────┐
      │                     │                     │
 Knowledge Services   AI Providers        Storage Layer
```

---

# Desktop Shell & Sidecar Integration Architecture

When executing in Desktop Mode, Tauri manages the FastAPI Python application as a local sidecar process.

```text
┌─────────────────────────────────────────────────────────┐
│                    Tauri Desktop Shell                  │
│                                                         │
│  ┌───────────────────────┐   Dynamic Port + Bearer Auth │
│  │ Next.js Frontend (UI) │ ──────────────────────────┐  │
│  └───────────────────────┘                           │  │
│                                                      │  │
│  ┌───────────────────────────────────────────────┐   │  │
│  │ FastAPI Backend Sidecar (Python Executable)   │ ◄─┘  │
│  └───────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────┘
```

Key Requirements:

* **Process Management:** Tauri spawns and monitors the FastAPI sidecar executable upon launch.
* **Dynamic Port Allocation:** FastAPI scans for available local ports starting at default `8000`, returning the assigned port back to Tauri via stdout initialization signal.
* **IPC & API Security:** Tauri generates an ephemeral secret token on startup and injects it into FastAPI via environment variable. All frontend-to-backend REST/WebSocket requests must supply this token in an `Authorization: Bearer <token>` header to prevent unauthorized local process access.
* **Graceful Lifecycle Shutdown:** Upon desktop application close, Tauri emits a `SIGTERM` signal to FastAPI, triggering clean teardown of DB connections and vector store locks before process exit.

# Clean Domain-Driven Architecture & Bounded Contexts

The application enforces a strict **Domain-Driven Layered Architecture** organized into discrete **Bounded Contexts** to eliminate architectural coupling.

```text
                     Presentation Layer
                    (React + Next.js UI)
                             │
                             ▼
                     Application Layer
           (Use Cases & Workflow Orchestrator)
                             │
                             ▼
 ┌─────────────────────────────────────────────────────────┐
 │                      Domain Layer                       │
 │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐  │
 │  │ Knowledge │ │ Learning  │ │ Workspace │ │   AI    │  │
 │  └───────────┘ └───────────┘ └───────────┘ └─────────┘  │
 │  ┌───────────┐ ┌───────────┐ ┌───────────┐              │
 │  │   User    │ │Evaluation │ │   Media   │              │
 │  └───────────┘ └───────────┘ └───────────┘              │
 └────────────────────────────┬────────────────────────────┘
                              │
                              ▼
                     Infrastructure Layer
         (SQLite Repositories, Event Bus, Task Queue,
            Workload Scheduler, Vector Database)
                              │
                              ▼
                    AI Service Bus Layer
 (Model Registry, Provider Router, Capability Adapters)
```

## Bounded Context Boundaries

1. **Knowledge Context**: Ingested assets, transcripts, semantic chunks, and concept relation linkages.
2. **Learning Context**: Quizzes, flashcards, study plans, concept mastery tracking, and revision scheduling.
3. **Workspace Context**: Workspace metadata, collection management, file organization, user permissions.
4. **AI Context**: AI Service Bus, Capability definitions, Model Registry, Provider Router, Agent Orchestration.
5. **User Context**: Structured User Memory, personal preferences, learning speed, mastery history.
6. **Evaluation Context**: Retrieval precision/recall, citation groundedness, latency, token cost metrics.
7. **Media Context**: Video file metadata, audio extraction, keyframe sampling, media state management.

Each Bounded Context owns its domain entities, value objects, domain events, and repository contracts independently.

---

## Knowledge Processing Layer

Responsible for converting raw educational content into structured knowledge.

Pipeline:

Content

↓

Ingestion

↓

Preprocessing

↓

Metadata Extraction

↓

Chunking

↓

Embeddings

↓

Vector Database

↓

Knowledge Store

---

# Event-Driven Architecture & Task Queue Workers

Long-running and heavy computational tasks (transcription, embedding generation, knowledge graph construction, quiz generation) operate asynchronously via an **Event-Driven Architecture**.

```text
User Action ──► API Command ──► Domain Event ──► Event Bus ──► Background Worker Queue
                                                                       │
                                                                       ▼
UI Notification (WS/SSE) ◄── Processing Complete ◄── Worker Execution ──┘
```

## Event Bus & Workflow Orchestration
* **Domain Event Publisher**: Emits events (`MediaUploadedEvent`, `TranscriptCompletedEvent`, `ChunksEmbeddedEvent`, `ConceptGraphUpdatedEvent`).
* **Workflow Orchestrator**: Manages multi-step job pipelines, retries, exponential backoff, and progress streaming to the client UI.

## Background Worker Suite
1. **Transcript Worker**: Executes speech-to-text audio processing.
2. **Embedding Worker**: Generates vector embeddings for semantic chunks.
3. **Knowledge Graph Worker**: Extracts concept entities and relationships between chunks.
4. **Thumbnail & Keyframe Worker**: Extracts video keyframes and visual samples.
5. **Summary Worker**: Constructs structured topic outlines and chapter markers.
6. **Quiz Worker**: Generates active-recall comprehension questions.
7. **Flashcard Worker**: Formulates spaced-repetition flashcard decks (Anki-compatible).

---

# Workspace Intelligence Architecture

Rather than a single monolithic service, Workspace Intelligence is decomposed into specialized, testable components:

```text
                        ┌────────────────────────────────┐
                        │ Workspace Intelligence Manager │
                        └───────────────┬────────────────┘
                                        │
        ┌───────────────┬───────────────┼───────────────┬───────────────┐
        │               │               │               │               │
┌───────▼───────┐┌──────▼───────┐┌──────▼───────┐┌──────▼───────┐┌──────▼───────┐
│Memory Manager ││Retrieval Mgr ││Context Builder││Recommend Engine│Agent Coord │
└───────────────┘└───────────────┘└───────────────┘└───────────────┘└───────────────┘
```

* **Memory Manager**: Controls the 4-Layer Memory Model (Short-Term, Working, Long-Term, Semantic Memory).
* **Retrieval Manager**: Executes multi-stage retrieval pipelines.
* **Context Builder**: Formulates compressed, citation-grounded prompts for LLM capabilities.
* **Recommendation Engine**: Proactively suggests next topics, quizzes, and flashcard reviews based on user mastery scores.
* **Agent Coordinator**: Dispatches tasks to specialized AI agents.

## Knowledge Graph Interfaces
To ensure early contract stability, Knowledge Graph operations are defined via explicit interfaces:
* `add_node(node: ConceptNode) -> None`
* `add_edge(source_id: str, target_id: str, relation: RelationType) -> None`
* `find_related(concept_id: str, max_depth: int) -> List[ConceptNode]`
* `recommend_prerequisites(target_concept_id: str) -> List[ConceptNode]`
* `discover_paths(start_concept_id: str, end_concept_id: str) -> List[ConceptPath]`

---

# Multi-Stage Layered Retrieval Architecture

Retrieval is executed as an **8-stage pipeline** incorporating query rewriting and context compression:

```text
Query ──► [1. Query Rewrite] ──► [2. Intent Detection] ──► [3. Context Injection]
                                                                  │
[6. Re-Ranking] ◄── [5. Hybrid Search (Vector+BM25)] ◄── [4. Graph Traversal]
       │
       ▼
[7. Context Compression] ──► [8. Grounded Prompt Assembly] ──► AI Service Bus
```

1. **Query Rewrite**: Expands abbreviations and reformulates ambiguous user questions using HyDE.
2. **Intent Detection**: Identifies target request (timestamp lookup, concept explanation, quiz generation, summary).
3. **Workspace Context Injection**: Attaches active media context and user working memory.
4. **Knowledge Graph Traversal**: Traverses prerequisite nodes for conceptual context.
5. **Hybrid Search**: Dense vector lookup (Qdrant) + Sparse keyword search (BM25).
6. **Cross-Encoder Re-Ranking**: Scores top-$N$ candidate chunks using a cross-encoder model.
7. **Context Compression**: Removes redundant sentences to maximize information density within LLM context windows.
8. **Grounded Prompt Assembly**: Constructs prompt with verified timestamp boundaries `[start_time - end_time]`.

---

# Workload Scheduler Subsystem

The Resource Manager is promoted to a **Workload Scheduler** that acts as the local operating system for AI workloads:

* **Resource Monitoring**: Tracks CPU cores, system RAM, GPU VRAM, and active process threads.
* **Model Lifecycle Management**: Dynamically loads and unloads local models (Ollama, Faster-Whisper, BGE) into VRAM/RAM on demand.
* **Workload Prioritization**: Prioritizes real-time user chat queries over background batch workers (transcription, embedding generation, graph building).
* **Task Cancellation & Concurrency Throttling**: Cancels stale background jobs when a user changes workspaces or closes the app.

---

# AI Service Bus & Model Registry Architecture

Every AI request flows through a centralized **AI Service Bus**.

```text
Application / Domain Layer
            │
            ▼
     AI Service Bus ───► Model Registry
            │
            ▼
     Provider Router
            │
    ┌───────┴───────┐
    ▼               ▼
Local Provider  Cloud Provider
```

## AI Service Bus Responsibilities
* Capability Routing
* Streaming & Token Parsing
* Automatic Retries & Exponential Backoff
* Task Cancellation & Telemetry Logging
* Prompt Response Caching
* Evaluation Hooks

## Model Registry
Maintains first-class metadata for all registered models:
* `provider_id` (e.g. `ollama`, `groq`, `faster_whisper`)
* `model_id` (e.g. `llama3:8b`, `whisper-large-v3`)
* `capabilities` (e.g. `TEXT_GENERATION`, `SPEECH_TO_TEXT`)
* `context_window` (e.g. `8192`)
* `vram_required_mb` (e.g. `5120`)
* `download_status` (`installed`, `available`, `downloading`)

## Provider Router
Evaluates hardware availability, Model Registry metadata, latency targets, and user cost preferences before selecting the execution target.

---

# Formal Agent Contracts

Specialized AI Agents implement a standardized protocol:

```python
class BaseAgent(Protocol):
    def is_applicable(self, task: TaskContext) -> bool: ...
    def required_context(self, task: TaskContext) -> ContextSpec: ...
    def required_tools(self) -> List[ToolSpec]: ...
    async def execute(self, input_data: AgentInput) -> AgentOutput: ...
```

Agents emit structured JSON outputs and operate strictly under the coordination of the `AgentCoordinator`.

---

# Architecture Decision Records (ADRs)

Architectural decisions are formally documented in numbered ADR files under `docs/adr/`.

* `0001-local-first-knowledge-os-architecture.md`
* `0002-sqlite-embedded-metadata-store.md`
* `0003-qdrant-embedded-vector-store.md`
* `0004-ai-service-bus-and-capability-routing.md`

All future significant decisions must be recorded via ADRs prior to implementation changes.

---

# Local-First AI Stack

Default local providers:

LLM

* Ollama

Speech

* Faster-Whisper

Embeddings

* BAAI BGE
* Nomic Embeddings

Vector Database

* Embedded Qdrant (via `qdrant-client` local storage; Docker optional)

Storage

* Local filesystem

Metadata Database

* SQLite (Desktop) / PostgreSQL (Cloud)

The application must function completely offline.

---

# Optional Cloud Providers

Users may optionally enable:

LLMs

* OpenRouter
* Groq
* Gemini
* Claude

Speech

* Deepgram

Embeddings

* Voyage AI
* OpenAI

Vector Database

* Qdrant Cloud

Object Storage

* Supabase Storage
* Amazon S3

Cloud services should be configurable through settings without requiring code changes.

---

# Capability-Based Provider Interfaces & Intelligent Routing

Business logic consumes abstract **Capabilities** rather than vendor-specific SDKs.

```text
               Application & Domain Layers
                            │
                            ▼
                  Capability Interfaces
  (ITextGen, ISpeechToText, IEmbedding, IVision, IReasoning)
                            │
                            ▼
                Intelligent Provider Router
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────▼───────┐                       ┌───────▼───────┐
│ Local Providers│                      │ Cloud Providers│
│(Ollama,Whisper│                       │(Groq, Gemini, │
│ BGE, Qdrant)  │                       │ Claude, Voyage│
└───────────────┘                       └───────────────┘
```

## Capability Interfaces
* `ITextGenerationCapability`: General LLM text generation and streaming.
* `ISpeechToTextCapability`: Audio transcription with word/segment timestamps.
* `IEmbeddingCapability`: Text & multimodal vector embedding generation.
* `IVisionCapability`: Image/frame analysis and visual OCR.
* `IReasoningCapability`: Complex multi-step reasoning & evaluation.
* `IPlannerCapability`: Agent task decomposition and workflow planning.

## Intelligent Provider Router
Automates provider selection based on dynamic evaluation rules:
* Simple Q&A / Summaries $\rightarrow$ Local Ollama (Low latency, zero cost).
* Complex Mathematical Reasoning $\rightarrow$ Cloud Reasoning Provider (Claude / Gemini) if enabled.
* Fast Batch Transcription $\rightarrow$ Local Faster-Whisper (or Deepgram Cloud fallback).

---

# Plugin Architecture

The application should be built around a plugin system.

Knowledge Sources

├── Video Plugin (Version 1)

├── PDF Plugin

├── Audio Plugin

├── PowerPoint Plugin

├── Documentation Plugin

├── Website Plugin

├── GitHub Plugin

Every plugin feeds into the same Knowledge Processing Pipeline.

---

# Workspace Architecture

Users work inside Workspaces.

Workspace

├── Uploaded Content

├── Knowledge Base

├── Chat History

├── Learning Materials

├── Notes

├── Quizzes

├── Progress

The Workspace becomes the primary organizational unit.

---

# Communication Architecture

Frontend

↓

REST API

↓

Services

↓

Repositories

↓

AI Providers

↓

Local Models / Cloud Models

Avoid direct communication between UI and AI components.

---

# Deployment Modes

## 1. Local Mode (Default)

Runs entirely on the user's computer.

Components:

* Tauri
* FastAPI
* Ollama
* Faster-Whisper
* PostgreSQL
* Qdrant

Advantages

* Maximum privacy
* Offline support
* No API costs

Tradeoffs

* Slower on low-end hardware
* Requires model downloads

---

## 2. Hybrid Mode

Uses local infrastructure by default while selectively routing tasks to cloud providers.

Example:

Speech

↓

Local Faster-Whisper

LLM

↓

Groq

Embeddings

↓

Local BGE

Advantages

* Better speed
* Better model quality
* Lower costs than fully cloud-based

Tradeoffs

* Internet dependency for selected services

---

## 3. Cloud Mode

Deployable to:

* Railway
* Fly.io
* Render
* DigitalOcean
* AWS
* Azure
* Google Cloud
* Coolify
* Self-hosted VPS

Components become:

Frontend

↓

Cloud FastAPI

↓

Cloud Database

↓

Qdrant Cloud

↓

Managed AI Providers

Advantages

* Accessible anywhere
* Easier collaboration
* Higher scalability

Tradeoffs

* Hosting costs
* Privacy considerations
* Internet required

---

# Why FastAPI?

FastAPI becomes the platform's central API.

Benefits:

* Desktop application
* Cloud deployment
* Future mobile support
* Public API
* CLI integration
* Automation

The frontend remains unchanged regardless of deployment mode.

---

# Scalability Strategy

The architecture should scale in the following order:

Version 1

Single-user desktop

↓

Version 2

Multi-workspace

↓

Version 3

Multimodal AI

↓

Version 4

Agentic workflows

↓

Version 5

Cloud-hosted collaboration

Each stage should require minimal architectural changes.

---

# Why This Architecture?

This architecture allows the platform to function as:

* A desktop application
* A self-hosted server
* A cloud service
* An open-source AI platform

without changing the core application architecture.

This separation of concerns ensures that AI models, deployment strategies, storage providers, and frontend technologies remain interchangeable, enabling long-term maintainability, extensibility, and scalability.

The end goal is to build a production-quality AI Learning Platform that showcases modern AI engineering practices, beginning with video-based learning and evolving into a complete Knowledge Operating System capable of supporting multiple content types, multimodal retrieval, intelligent learning assistance, and future agentic AI workflows.
