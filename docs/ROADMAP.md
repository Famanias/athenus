# ROADMAP.md — Athenus Knowledge OS Strategic Product & Architecture Roadmap

This document outlines the strategic evolution of **Athenus Knowledge OS**, mapping completed core infrastructure capabilities and upcoming development phases based on [`plan.md`](file:///e:/repos/athenus/plan.md) and [`local-first-philosophy.md`](file:///e:/repos/athenus/local-first-philosophy.md).

---

## 🎯 Strategic Product Vision & Philosophy

Athenus Knowledge OS is an open-source, local-first, privacy-first AI-native Knowledge Operating System. It is designed to transform long-form educational content into interactive, searchable, explainable, and personalized learning companions.

### Core Architecture & Local-First Tenets
1. **Local-First Execution**: 100% offline-capable by default (Faster-Whisper ASR, BGE Small Embeddings, Embedded Qdrant Vector Store, SQLite Metadata, and Local Ollama LLM Discovery).
2. **Provider Agnostic**: Cloud AI providers (Groq, OpenRouter, Gemini, Claude) act as optional performance enhancements via abstract capability interfaces (`AIServiceBus`).
3. **Plugin-Based Knowledge Sources**: Architecture designed to ingest diverse knowledge formats (Video, Audio, PDF, PPTX, Books, Web Documentation, GitHub Repositories) into a unified knowledge store.

---

## 🚀 Completed Core Infrastructure (v0.1 — Baseline Release)

### 1. Ingestion Pipeline & Speech Processing
* ✅ Local video/audio upload handling (`/api/v1/media/upload`).
* ✅ FFmpeg 16kHz mono PCM audio extraction.
* ✅ Faster-Whisper ASR with word-level timestamp alignment (`[start_time, end_time]`).
* ✅ Semantic transcript chunking into overlapping ~250-word windows.
* ✅ Event-driven ingestion progress store (`ProgressStore`) emitting real-time SSE progress updates.

### 2. Information Retrieval & RAG Engine
* ✅ Dense vector representation using `bge-small-en-v1.5` (384-dimensional Cosine vectors).
* ✅ Embedded Qdrant vector database (`./data/qdrant`) with strict `workspace_id` payload isolation.
* ✅ 8-Stage Layered Retrieval Engine (Query Rewrite, HyDE, Intent Detection, Context Injection, Knowledge Graph Traversal, Hybrid Search, Cross-Encoder Re-Ranking, Grounded Prompt Assembly).
* ✅ Interactive chat with per-message grounded timestamp citations (`[MM:SS - MM:SS]`).

### 3. Multi-Workspace & Multi-Session Architecture
* ✅ Multi-workspace organization & collection management (`WorkspaceService`, SQLite `workspaces` table).
* ✅ Multi-session chat thread lifecycle with lazy session creation (`SessionService`, SQLite `chat_sessions` and `chat_messages` tables).
* ✅ In-app explicit confirmation dialogs for workspace and session deletion.

### 4. Settings Persistence & Pure Local Model Discovery
* ✅ Single source of truth settings persistence in SQLite (`system_settings` table, `SettingsService`).
* ✅ Pure local filesystem Ollama model scanner (`OllamaModelScanner`) with forgiving path normalization (`.ollama` $\rightarrow$ `.ollama/models`).
* ✅ Dynamic LLM provider settings UI with auto-discovered model selection dropdown.

### 5. Desktop Presentation Layer
* ✅ Next.js 16 + React 18 + Tauri Rust desktop wrapper (`npx tauri dev`).
* ✅ Single Authoritative Video Player DOM architecture (CSS-hidden persistent container preventing PiP video detachment).
* ✅ Interactive transcript reader with card-level timestamp click-to-seek navigation.

---

## 📋 Upcoming Development Phases & Unimplemented Feature Tabs

### Phase A: Multimodal File Ingestion Plugins (Beyond Video-Only)
* ⏳ **Generic File Uploads**: Expand beyond video/audio uploads to ingest non-video educational assets.
* ⏳ **Document Plugins**: PDF document parser, PowerPoint (`.pptx`) slide parser, and Markdown file chunker.
* ⏳ **Web & Repository Plugins**: Web documentation scraper and GitHub repository file indexer feeding into the unified RAG pipeline.

### Phase B: Concept Knowledge Graph Visualizer (`view-graph` Tab)
* ⏳ **Interactive Graph Canvas**: Frontend Knowledge Graph UI canvas visualizing concept nodes and directional prerequisite linkages (`source_concept` $\rightarrow$ `target_concept`).
* ⏳ **Concept Traversal & Inspection**: Interactive node selection displaying concept descriptions, linked lecture segments, and prerequisite dependencies.

### Phase C: Active Recall Flashcards & SM-2 Studio (`view-flashcards` Tab)
* ⏳ **Active Recall Flashcards UI**: Dedicated Flashcard Studio tab displaying AI-generated active recall question/answer pairs.
* ⏳ **Spaced Repetition Engine**: Integration of SuperMemo-2 (SM-2) algorithm tracking review intervals, Ease Factors ($EF$), and user mastery levels.
* ⏳ **Anki Export**: One-click export of flashcard decks to `.apkg` format for Anki synchronization.

### Phase D: Adaptive Comprehension Quiz Studio (`view-quiz` Tab)
* ⏳ **Quiz Studio UI**: Interactive Quiz tab presenting adaptive multiple-choice diagnostic tests.
* ⏳ **Automated Diagnostic Feedback**: Instant answer evaluation explaining correct answers with grounded timestamp citations back to lecture videos.

### Phase E: Learning Analytics & Mastery Dashboard (`view-analytics` Tab)
* ⏳ **Analytics Dashboard UI**: Learning metrics panel tracking total study hours, video completion rates, concept mastery percentages, and active recall retention curves.
* ⏳ **Personalized Revision Recommendations**: AI recommendation engine suggesting specific lecture video timestamps for targeted review based on quiz errors.

### Phase F: Advanced Multimodal & Agentic Workflows
* ⏳ **Visual Keyframe OCR & Multimodal Embeddings**: OCR processing on video keyframes (`PaddleOCR` / `Florence-2`) for embedded slide text retrieval.
* ⏳ **Multi-Agent Suite**: Multi-agent coordination (`PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent`) for automated study plan generation.
