# Athenus Knowledge OS

> **Local-First, Offline-Capable AI Operating System for Interactive Learning, Multimodal Retrieval, & Agentic AI**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.11+](https://img.shields.io/badge/Python-3.11+-brightgreen.svg)](backend/)
[![Tauri: 1.5+](https://img.shields.io/badge/Tauri-1.5+-blueviolet.svg)](src-tauri/)
[![Next.js: 14+](https://img.shields.io/badge/Next.js-14+-black.svg)](frontend/)
[![Tests: 25 Passed](https://img.shields.io/badge/Tests-25%20Passed-success.svg)](backend/tests/)

---

## Overview

**Athenus Knowledge OS** is an open-source, local-first AI engineering platform that transforms educational media into interactive, searchable, explainable, and personalized learning experiences.

Featuring:
* **100% Offline Capability**: Local speech-to-text (Faster-Whisper), local embeddings (BAAI BGE Small), local vector storage (Embedded Qdrant), and local LLMs (Ollama).
* **Zero API Cost & Privacy-First**: All videos, transcripts, embeddings, notes, and user progress remain on your device.
* **8-Stage Layered Retrieval**: Hybrid Search (Dense Qdrant + Sparse BM25), Query Rewriting (HyDE), Cross-Encoder Re-Ranking, and Context Compression.
* **Interactive Timestamp Citations**: Every RAG answer includes clickable timestamp badges (`[MM:SS - MM:SS]`) that jump the video player directly to referenced scenes.
* **Multi-Video Workspaces**: Group media files into isolated workspaces with cross-media search.
* **Knowledge Graph Engine**: Concept node traversal and automated prerequisite discovery.
* **Active Recall Learning Tools**: Automated chapter outlines, quizzes, and spaced-repetition flashcards (Anki SM-2 export).
* **Agentic AI Suite**: Multi-agent coordinator orchestrating `PlannerAgent`, `RetrieverAgent`, and `CitationValidatorAgent`.

---

## Architecture Documentation Suite

All system documentation files are available in [docs/](file:///e:/repos/athenus/docs/):
* [ARCHITECTURE.md](file:///e:/repos/athenus/architecture.md) — System Architecture & Bounded Contexts
* [AI_PIPELINE.md](file:///e:/repos/athenus/docs/AI_PIPELINE.md) — Ingestion & 8-Stage Retrieval Pipeline
* [APPLICATION_ARCHITECTURE.md](file:///e:/repos/athenus/docs/APPLICATION_ARCHITECTURE.md) — Tauri Shell & Next.js Presentation Layer
* [AGENT_ARCHITECTURE.md](file:///e:/repos/athenus/docs/AGENT_ARCHITECTURE.md) — Agentic AI Suite Architecture
* [MEMORY_ARCHITECTURE.md](file:///e:/repos/athenus/docs/MEMORY_ARCHITECTURE.md) — 4-Layer Memory Model & Storage Separation
* [WORKSPACE_ARCHITECTURE.md](file:///e:/repos/athenus/docs/WORKSPACE_ARCHITECTURE.md) — Workspace Collections & Boundaries
* [PLUGIN_ARCHITECTURE.md](file:///e:/repos/athenus/docs/PLUGIN_ARCHITECTURE.md) — Modular Knowledge Source Plugins
* [TECH_STACK.md](file:///e:/repos/athenus/docs/TECH_STACK.md) — Technology Stack Comparison & Tradeoffs
* [DATABASE.md](file:///e:/repos/athenus/docs/DATABASE.md) — SQLite Schema & Qdrant Payload Specifications
* [API.md](file:///e:/repos/athenus/docs/API.md) — Complete REST & SSE API Reference (v1.0)
* [DEPLOYMENT.md](file:///e:/repos/athenus/docs/DEPLOYMENT.md) — Desktop, Docker, and Cloud Deployment Options
* [EVALUATION.md](file:///e:/repos/athenus/docs/EVALUATION.md) — AI Evaluation Framework & Benchmarks
* [ROADMAP.md](file:///e:/repos/athenus/docs/ROADMAP.md) — Strategic Roadmap (V0.1 to V1.0)
* [RULES.md](file:///e:/repos/athenus/docs/RULES.md) — Architecture & Coding Rules
* [MEMORY.md](file:///e:/repos/athenus/docs/MEMORY.md) — Living System Memory Reference
* [CONTRIBUTING.md](file:///e:/repos/athenus/docs/CONTRIBUTING.md) — Open Source Contributor Guidelines
* [Architecture Decision Records (ADRs)](file:///e:/repos/athenus/docs/adr/) — Formally Recorded Decisions (`0001` - `0004`)

---

## License

Athenus Knowledge OS is open-source software licensed under the [MIT License](LICENSE).
