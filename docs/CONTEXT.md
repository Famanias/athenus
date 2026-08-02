# CONTEXT.md

# Project Context

This document serves as the living memory of the project.

It should be updated throughout development.

---

# Project Name

(TBD)

Current Working Title:

AI Learning Platform (Knowledge OS)

---

# Vision

Build a local-first, AI-native learning platform that transforms educational content into an interactive learning experience.

The platform should eventually support multiple knowledge sources while remaining modular, extensible, and provider-agnostic.

---

# Current Scope

Primary knowledge source:

* Videos

Future knowledge sources:

* PDFs
* Audio
* PowerPoint
* Websites
* GitHub repositories
* Documentation
* Books

---

# Current Phase

Pre-Development

Status:

Architecture & documentation.

No implementation has begun.

---

# Primary Objective

Build a flagship open-source AI Engineering project demonstrating:

* Modern RAG
* Multimodal AI
* Local AI
* Agentic workflows
* Production engineering

---

# Application Type

Desktop-first application using a local web architecture.

Frontend:

React + Next.js

Backend:

FastAPI

Desktop Shell:

Tauri (preferred)

---

# Deployment Philosophy

Support three modes:

* Local
* Hybrid
* Cloud

Local mode is the default experience.

---

# AI Philosophy

The platform helps users learn.

It is not simply a chatbot.

Learning is the product.

Chat is one interface.

---

# Architectural Principles

* Local-first
* Offline-capable
* Privacy-first
* Provider-agnostic
* Plugin-based
* Modular
* Extensible

---

# Future AI Agents

Planned agents include:

* Planner
* Retriever
* Transcript
* Vision
* Learning
* Quiz
* Flashcard
* Citation
* Evaluation

These are future roadmap items and should not be implemented prematurely.

---

# Current MVP

Version 1 includes:

* Video upload
* Speech-to-text
* Transcript generation
* Embeddings
* Vector search
* Chat
* Timestamp citations

---

# Long-Term Vision

The platform evolves into a Knowledge Operating System capable of supporting:

* Multimodal retrieval
* Personalized learning
* Adaptive study plans
* Knowledge graphs
* Agentic AI workflows

---

# Design Decisions

Current accepted decisions:

* Desktop-first architecture
* Local-first philosophy
* Domain-Driven Architecture with 7 Bounded Contexts (`Knowledge`, `Learning`, `Workspace`, `AI`, `User`, `Evaluation`, `Media`)
* AI Service Bus & Model Registry Architecture for centralized capability routing
* Workload Scheduler Subsystem acting as local OS for AI workloads
* Event-Driven Task Queue & Background Worker Architecture (`TranscriptWorker`, `EmbeddingWorker`, `GraphWorker`, `QuizWorker`, `FlashcardWorker`)
* Decomposed Workspace Intelligence (`MemoryManager`, `RetrievalManager`, `ContextBuilder`, `RecommendationEngine`, `AgentCoordinator`)
* 4-Layer Memory Model (Short-term, Working, Long-term, Semantic Graph)
* Separation of Knowledge Storage (immutable chunks/embeddings) vs User Memory (progress/notes)
* 8-Stage Layered Retrieval Engine (Query Rewrite, HyDE, Context Injection, Graph Traversal, Hybrid Search, Re-Ranking, Context Compression, Grounded Prompt Assembly)
* Capability-Based Provider Abstraction & Provider Router
* Architecture Decision Record (ADR) Process established under `docs/adr/`
* Embedded SQLite database for Desktop Mode (PostgreSQL for Cloud/Multi-user)
* Embedded Qdrant for Desktop Vector Storage (Docker/Cloud optional)
* Tauri-FastAPI sidecar IPC security (Bearer token authorization & dynamic port binding)
* First-class AI Evaluation Subsystem (Retrieval Precision/Recall, Citation Groundedness, Latency/Cost)

Update this section whenever important architectural decisions are finalized.

---

# Open Questions

Record unresolved architectural questions here.

Examples:

* Authentication strategy
* Collaboration features
* Knowledge graph implementation
* Local model recommendations
* Plugin SDK design

This section should shrink over time as decisions are made.

---

# Known Constraints

Current hardware target:

* Mid-range consumer PCs
* Local GPU acceleration when available
* Fully functional CPU-only fallback

Cloud providers are optional.

---

# Success Criteria

The project succeeds if it demonstrates excellent AI engineering practices while remaining usable, extensible, open-source, and approachable for self-hosting.
