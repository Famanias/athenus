# Athenus — Project Walkthrough

*A local-first AI operating system for interactive learning, multimodal retrieval, and agentic AI workflows.*

---

## What Is Athenus?

**Athenus** is a desktop application (also runnable in a browser via Docker) that turns your personal video and document library into an **interactive, AI-powered learning environment**. Think of it as a "second brain" that watches your lectures, reads your PDFs, and then lets you:

- **Chat with your content** — Ask questions and get grounded answers with clickable timestamps that jump straight to the relevant moment in a video or page in a document.
- **Auto-generate study materials** — Flashcards (with spaced-repetition scheduling), quizzes, and concept maps — all derived from your actual content.
- **Explore knowledge graphs** — See how concepts connect across videos and documents, with automated prerequisite discovery.
- **Track your learning** — Spaced-repetition reviews, quiz scores, and study streaks — all stored locally.

**The defining philosophy**: *Everything runs on your machine.* No API keys required, no data leaves your device unless you explicitly opt into cloud providers.

---

## How It Works — The Big Picture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        USER INTERFACE (Next.js + Tauri)              │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │  Pipeline   │  │   Chat /    │  │  Knowledge  │  │  Learning  │  │
│  │  (Ingest)   │  │    RAG      │  │    Graph    │  │   Suite    │  │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │
└─────────┼────────────────┼────────────────┼───────────────┼─────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      BACKEND API (FastAPI)                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────────┐  │
│  │   Media &    │ │   Chat &     │ │  Knowledge   │ │  Learning  │  │
│  │  Ingestion   │ │  Retrieval   │ │    Graph     │ │  Services  │  │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └─────┬──────┘  │
└─────────┼────────────────┼────────────────┼───────────────┼─────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    EVENT-DRIVEN WORKERS (Async)                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐   │
│  │  Transcript │ │  Embedding  │ │    Graph    │ │  Artifact   │   │
│  │   Worker    │ │   Worker    │ │ Extraction  │ │   Workers   │   │
│  └─────────────┘ └─────────────┘ └─────────────┘ └─────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
          │                │                │               │
          ▼                ▼                ▼               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    LOCAL AI & STORAGE LAYER                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Ollama  │ │ Faster-  │ │   BGE    │ │ Embedded │ │  SQLite  │  │
│  │  (LLMs)  │ │ Whisper  │ │Embeddings│ │  Qdrant  │ │  (Meta)  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Core Workflows

### 1. Video Ingestion Pipeline

**You drop an `.mp4` (or `.mkv`, `.mov`, `.mp3`, `.wav`…) → Athenus does the rest.**

| Stage | What Happens | Tech |
|-------|-------------|------|
| **Upload** | File saved to `data/uploads/`, metadata registered in SQLite | FastAPI, SQLModel |
| **Audio Extraction** | FFmpeg pulls audio track to a temporary `.wav` | `ffmpeg-python` |
| **Transcription** | Faster-Whisper (local, CPU/GPU) → timestamped segments | `faster-whisper` (CTranslate2) |
| **Chunking** | Semantic chunker groups segments into ~512-token pieces with timestamps | Custom `SemanticChunker` |
| **Embedding** | BAAI/bge-small-en-v1.5 (384-dim) vectors computed locally | `sentence-transformers` |
| **Vector Index** | Chunks + vectors upserted to Embedded Qdrant (cosine similarity) | `qdrant-client` (embedded mode) |
| **Full-Text Index** | Chunks also mirrored to SQLite FTS5 table for BM25 keyword search | SQLite FTS5 + triggers |
| **Knowledge Graph** | LLM (via Ollama) extracts concepts & relations → merged into canonical graph | `AIServiceBus` + `ConceptMergingService` |
| **Complete** | Job marked `completed`, SSE stream notifies frontend | `EventBus` + `ProgressStore` |

**Result**: You now have a searchable, chat-able video with a concept map.

---

### 2. Document Ingestion Pipeline

**PDFs, DOCX, PPTX, XLSX, EPUB, MD, TXT — all handled.**

| Stage | What Happens | Tech |
|-------|-------------|------|
| **Upload** | File saved, registered with `doc_` prefix | FastAPI |
| **Structure Parsing** | AnyDoc extracts headings, tables, page breaks, Markdown | `AnyDocDocumentParsingAdapter` |
| **Scanned Page Detection** | AnyDoc flags image-only/scanned pages | Heuristic: low text + image markers |
| **OCR (on-demand)** | RapidOCR (ONNX Runtime) runs **only** on flagged pages | `RapidOCROCRAdapter` + hardware semaphore |
| **Page-Aware Chunking** | Chunks preserve page numbers & section titles | `SemanticChunker.chunk_document_pages` |
| **Embedding & Index** | Same vector + FTS5 pipeline as video | Qdrant + SQLite FTS5 |
| **Knowledge Graph** | Same extraction & merging pipeline | `GraphExtractionWorker` |

**Key difference from video**: Documents have *native structure* (headings, pages, tables) that AnyDoc preserves. OCR runs **only** when needed — saving huge amounts of compute.

---

### 3. Chat + RAG (Retrieval-Augmented Generation)

**You ask: "What did the lecturer say about transformers at 12:30?"**

```
User Query
    │
    ▼
┌──────────────────────────────────────┐
│  Query Classifier                    │
│  (filters conversational chaff)      │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  8-Stage Layered Retrieval           │
│  1. Dense Vector Search (Qdrant)     │
│  2. Sparse BM25 Search (SQLite FTS5) │
│  3. Hybrid Fusion (RRF)              │
│  4. HyDE Query Rewriting             │
│  5. Cross-Encoder Re-ranking         │
│  6. Context Compression              │
│  7. Citation Validation              │
│  8. Grounded Answer Generation       │
└──────────────┬───────────────────────┘
               ▼
┌──────────────────────────────────────┐
│  Multi-Agent Coordinator             │
│  • PlannerAgent     → execution plan │
│  • RetrieverAgent   → fetch context  │
│  • CitationValidatorAgent → verify  │
└──────────────┬───────────────────────┘
               ▼
        Final Answer
        + [MM:SS] citations
        (click → jump to video)
```

**Why 8 stages?** Pure vector search misses exact keywords; pure keyword search misses semantics. The hybrid pipeline catches both, re-ranks for relevance, compresses to fit context windows, and validates every citation against the source.

---

### 4. Knowledge Graph Engine

**Concepts don't live in isolation — they connect.**

- **Nodes** = concepts (e.g., "Transformer", "Attention Mechanism", "BERT")
- **Edges** = relations (`prerequisite_for`, `relates_to`, `part_of`, `example_of`)
- **Grounding** = every concept links back to source chunks + timestamps
- **Isolation** = each workspace has its own graph (no cross-contamination)
- **Prerequisite Discovery** = automated: "To understand BERT, you need Transformers first"

The graph is built by an LLM extracting concepts from chunks, then a **deterministic merging service** canonicalizes duplicates (e.g., "attention" + "self-attention" → one node).

---

### 5. Active Recall Learning Suite

| Feature | How It Works |
|---------|-------------|
| **Flashcards** | LLM generates Q/A pairs from chunks → stored as `FlashcardDeck` + `Flashcard` rows |
| **Spaced Repetition** | **SuperMemo-2 (SM-2)** algorithm: ratings 1–4 (Again/Hard/Good/Easy) → next review date |
| **Anki Export** | One-click `.apkg` export for Anki users |
| **Quizzes** | LLM generates multiple-choice questions from concepts → `Quiz` + `QuizQuestion` tables |
| **Attempts & Analytics** | Scores, timing, concept mastery tracked in `QuizAttempt`, `ConceptMastery`, `WorkspaceAnalytics` |

---

## Data Storage — Where Everything Lives

Athenus uses **three complementary storage systems**, each optimized for a different access pattern.

### 1. SQLite (`data/athenus.db`) — The Source of Truth

**Relational metadata, transcripts, chat, learning progress.**

```
┌────────────────────────────────────────────────────────────────┐
│                        CORE TABLES                              │
├─────────────────────┬──────────────────────────────────────────┤
│ Table               │ Purpose                                   │
├─────────────────────┼──────────────────────────────────────────┤
│ workspaces          │ Top-level containers (isolated projects) │
│ media_items         │ Videos & documents (title, path, status) │
│ transcript_segments │ Raw Whisper segments (start, end, text)  │
│ transcript_chunks   │ Semantic chunks (512 tok, timestamps)    │
│ chat_sessions       │ Conversation threads per workspace       │
│ chat_messages       │ Individual messages + citations JSON     │
│ processing_logs     │ Per-stage progress for ingestion jobs    │
├─────────────────────┼──────────────────────────────────────────┤
│           KNOWLEDGE GRAPH TABLES                               │
├─────────────────────┼──────────────────────────────────────────┤
│ knowledge_concepts  │ Canonical concept nodes (name, embed)    │
│ knowledge_relations │ Edges (source, target, type, weight)     │
│ concept_aliases     │ Synonyms for fuzzy matching              │
├─────────────────────┼──────────────────────────────────────────┤
│           LEARNING ARTIFACT TABLES                             │
├─────────────────────┼──────────────────────────────────────────┤
│ flashcard_decks     │ Decks (versioned, media-linked)          │
│ flashcards          │ Cards (SM-2 state: ease, interval, reps) │
│ flashcard_reviews   │ Review history (rating, timestamp)       │
│ quizzes             │ Quiz definitions                         │
│ quiz_questions      │ MCQs with grounding metadata             │
│ quiz_attempts       │ User attempts (score, answers, time)     │
├─────────────────────┼──────────────────────────────────────────┤
│           ANALYTICS & SETTINGS                                 │
├─────────────────────┼──────────────────────────────────────────┤
│ workspace_analytics │ Aggregated stats (cards, quizzes, streak)│
│ concept_mastery     │ Per-concept mastery level (0.0–1.0)      │
│ study_sessions      │ Time-tracked study sessions              │
│ system_settings     │ Global prefs (LLM, STT, embedding, GPU)  │
├─────────────────────┼──────────────────────────────────────────┤
│           FULL-TEXT SEARCH (FTS5 VIRTUAL TABLE)                │
├─────────────────────┼──────────────────────────────────────────┤
│ transcript_chunks_fts│ BM25 index over chunk text (triggers)   │
└─────────────────────┴──────────────────────────────────────────┘
```

**Why SQLite?**
- Zero-config, single file, ACID, works everywhere
- FTS5 gives production-grade BM25 search *inside* the same file
- Triggers keep FTS5 in sync with `transcript_chunks` automatically
- Self-healing: on boot, a repair routine fixes corrupted FTS5 vtables (common when copying DBs across platforms)

---

### 2. Embedded Qdrant (`data/qdrant/`) — Vector Search

**Dense embeddings for semantic similarity.**

```
Collection: athenus_chunks (384-dim, COSINE)
│
├── Point: {id: "chunk_uuid", vector: [...], payload: {...}}
│
├── Payload fields:
│   ├── workspace_id     (filter: isolate workspaces)
│   ├── media_id         (filter: single video/doc)
│   ├── source_type      (video | document | pdf)
│   ├── document_id      (for multi-page docs)
│   ├── page_number      (for page-aware citation)
│   ├── section_title    (for context)
│   ├── chunk_index      (ordering)
│   ├── start_time       (video timestamp)
│   ├── end_time
│   └── text             (the chunk text itself)
```

**Why Embedded Qdrant?**
- Runs in-process (no separate server needed)
- Persists to disk (`data/qdrant/`)
- Same API as Qdrant Cloud — swap later if needed
- Automatic fallback to in-memory mode if disk lock occurs

---

### 3. File System (`data/`) — Blobs & Caches

```
data/
├── uploads/           # Original video/audio/document files (user content)
├── qdrant/            # Qdrant embedded persistence
├── samples/           # Demo assets
├── hf-cache/          # HuggingFace model cache (BGE, Whisper) — shared across rebuilds
└── ollama-data/       # (Docker volume) Pulled GGUF models (llama3:8b, etc.)
```

---

## The AI Stack — All Local, All Swappable

| Capability | Default Local Provider | Cloud Fallback (Optional) |
|------------|------------------------|---------------------------|
| **LLM (Chat/Reasoning)** | Ollama (llama3:8b, qwen2.5, etc.) | Groq, OpenRouter, Gemini, Claude |
| **Embeddings** | BAAI/bge-small-en-v1.5 (384-dim) | Voyage AI |
| **Speech-to-Text** | Faster-Whisper (tiny/base/small/medium/large) | Deepgram |
| **OCR** | RapidOCR (ONNX, CPU) | — |
| **Vector DB** | Embedded Qdrant | Qdrant Cloud |
| **Object Storage** | Local filesystem | MinIO, S3 |

**Provider Abstraction**: Every capability goes through an interface (`ITextGenerationCapability`, `IEmbeddingCapability`, `ISpeechToTextCapability`, …). The `AIServiceBus` routes requests to the active provider. The `ProviderRouter` picks models based on a policy (`prefer_local: true`, VRAM limits, cloud fallback toggle).

**Result**: Swap Ollama → Groq in settings; zero code changes.

---

## Multi-Agent Coordinator

For complex queries, Athenus doesn't just call one LLM — it orchestrates a **team of specialized agents**:

| Agent | Role | Tools |
|-------|------|-------|
| **PlannerAgent** | Breaks query into steps: retrieve → answer → quiz | `retriever`, `quiz_generator` |
| **RetrieverAgent** | Executes the 8-stage retrieval pipeline | `multi_stage_retriever` |
| **CitationValidatorAgent** | Verifies every citation grounds in source | `groundedness_evaluator` |

The `AgentCoordinator` runs applicable agents in sequence, passing context forward. This is the "agentic" in "agentic AI workflows."

---

## Workspace Isolation — Your Projects Don't Mix

```
Workspace: "ML Course"          Workspace: "History Lectures"
├── media_items (course videos)     ├── media_items (history videos)
├── transcript_chunks               ├── transcript_chunks
├── knowledge_concepts (ML terms)   ├── knowledge_concepts (history terms)
├── knowledge_relations             ├── knowledge_relations
├── flashcard_decks                 ├── flashcard_decks
├── quizzes                         ├── quizzes
└── chat_sessions                   └── chat_sessions
```

- **Zero cross-contamination**: Retrieval, graph, chat, learning — all scoped to `workspace_id`
- **Independent settings**: Each workspace can have its own model preferences
- **Archive/Pin**: Organize without deleting

---

## Deployment Modes

| Mode | How to Run | Use Case |
|------|------------|----------|
| **Docker (Web)** | `./scripts/dev.sh` → http://localhost:47734 | Quick start, any OS, no install |
| **Docker (GPU)** | `./scripts/dev.sh --gpu` | NVIDIA GPU acceleration for Whisper + Ollama |
| **Tauri Desktop** | `docker compose up -d backend` → `npm run tauri dev` | Native app, system tray, file associations |
| **Host Ollama** | `docker compose -f docker-compose.yml -f docker-compose.host-models.yml up -d` | Reuse models you already pulled |

All modes share the **same backend** and **same data directory** (`./data/`).

---

## What AI Helped Create

Athenus was built with **heavy AI assistance** across the entire lifecycle:

| Area | How AI Was Used |
|------|----------------|
| **Architecture Design** | ADRs (Architecture Decision Records) drafted & refined with AI; trade-off analysis for local-first vs. cloud, embedded vs. client-server vector DB, event-driven vs. request-response |
| **Backend Implementation** | FastAPI routes, SQLModel schemas, event handlers, worker pipelines, adapters for 7+ AI providers — scaffolded & iterated with AI |
| **Frontend Implementation** | Next.js + TypeScript + Zustand stores, React components (pipeline, chat, graph, flashcards, quiz), Tailwind styling — co-written with AI |
| **AI Pipeline Engineering** | 8-stage retrieval design, hybrid search fusion, HyDE implementation, cross-encoder reranker, citation validation logic — all AI-collaborated |
| **Testing & CI** | 160 backend tests (pytest), GitHub Actions workflow (frontend typecheck, backend test, Tauri build), test stabilization — AI-assisted |
| **Documentation** | `walkthrough.md`, `document_ingestion_flow.md`, `document_processing_architecture.md`, ADRs — AI-generated from code |
| **DevOps** | Dockerfiles (multi-stage, CPU/GPU), docker-compose overlays, setup scripts (PowerShell + Bash), healthchecks — AI-drafted |
| **Agentic Workflows** | The `AgentCoordinator`, `PlannerAgent`, `RetrieverAgent`, `CitationValidatorAgent` — meta: AI agents built with AI help |

**Human Role**: Architecture decisions, UX direction, integration testing, saying "no" to over-engineering, ensuring local-first purity, debugging the weird edge cases (FTS5 corruption, GPU driver mismatches, ONNX Runtime threading).

---

## Key Design Decisions (The "Why")

| Decision | Rationale |
|----------|-----------|
| **Local-first by default** | Privacy, cost, offline capability, no vendor lock-in |
| **Event-driven workers** | Decouples ingestion stages; enables progress streaming; survives restarts via persistent queue |
| **SQLite + FTS5 + Qdrant** | Each storage engine does what it's best at: relations, keyword search, vector search |
| **Embedded Qdrant (not client-server)** | Zero infra, same API, persists to disk, trivial backup (copy the folder) |
| **AnyDoc + RapidOCR (on-demand)** | Structure extraction ≠ OCR; running OCR on every page wastes 100× compute |
| **Provider abstraction everywhere** | Swap Ollama → Groq in settings; add new providers without touching business logic |
| **Workspace isolation at schema level** | No `WHERE workspace_id = ?` bugs; every query scoped by design |
| **SM-2 for spaced repetition** | Proven algorithm; Anki-compatible export; simple 1–4 rating UX |
| **Tauri for desktop** | Small bundle (~10 MB), Rust backend, web frontend reuse, system integration |
| **Docker Compose for everything** | One command (`dev.sh`) spins up backend + frontend + Ollama + Qdrant + volumes |

---

## Quick Start (30 Seconds)

```bash
git clone https://github.com/Famanias/athenus.git
cd athenus
./scripts/setup.sh        # creates .env, pulls nothing
./scripts/dev.sh          # docker compose up -d --build
# Wait ~60s for containers to be healthy...
open http://localhost:47734
```

**First time only** (pull a model):
```bash
./scripts/ollama-pull.sh   # downloads llama3:8b (~4.7 GB) into ollama-data volume
```

**Desktop app** (optional):
```bash
cd frontend
npm install
npx tauri dev
```

---

## File Structure Cheat Sheet

```
athenus/
├── backend/
│   ├── app/
│   │   ├── application/          # Event handlers, services, repositories
│   │   ├── domain/               # Pure business logic (ai, knowledge, learning, workspace)
│   │   ├── infrastructure/       # Adapters (Ollama, Whisper, Qdrant, AnyDoc, RapidOCR), DB
│   │   ├── api/                  # FastAPI routes (media, chat, graph, learning, settings)
│   │   └── core/                 # Config, runtime, event bus
│   └── tests/                    # 160 pytest tests
├── frontend/
│   ├── src/
│   │   ├── features/             # Feature modules (ingestion, chat, graph, flashcards, quiz, video, document, pipeline, library, settings, analytics, transcript)
│   │   ├── components/           # Shared UI components
│   │   ├── store/                # Zustand stores (app, chat, ingestion, workspace)
│   │   └── services/             # API client, media service
│   └── src-tauri/                # Tauri config, Rust commands
├── docker/                       # Dockerfiles (backend, frontend)
├── scripts/                      # setup.sh, dev.sh, ollama-pull.sh, .ps1 Windows equivalents
├── data/                         # SQLite, Qdrant, uploads, caches (gitignored)
├── docs/                         # Deployment, onboarding, contributing, roadmap, ADRs, UI mockups
├── .github/workflows/ci.yml      # CI pipeline
├── docker-compose.yml            # CPU stack
├── docker-compose.gpu.yml        # GPU overlay
├── docker-compose.host-models.yml# Host Ollama overlay
├── walkthrough.md                # Phase-by-phase implementation log
├── document_ingestion_flow.md    # Canonical pipeline trace
├── document_processing_architecture.md  # AnyDoc + RapidOCR deep dive
├── implementation_plan.md        # Current sprint plan
├── local-first-philosophy.md     # Core principles
├── architecture-review-*.md      # Architecture reviews
└── PROJECT_WALKTHROUGH.md        # ← You are here
```

---

## TL;DR — The Elevator Pitch

> **Athenus** = Your private AI tutor that watches your lectures, reads your PDFs, builds a knowledge graph, generates flashcards & quizzes with spaced repetition, and lets you chat with citations that jump to the exact second — **all running locally on your laptop, no cloud required.**

---

*Generated for video walkthrough — August 2026*