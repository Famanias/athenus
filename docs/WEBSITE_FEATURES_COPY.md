# Athenus Website — Features & How It Works Copy

Reusable marketing copy for the Athenus Knowledge OS website, written honestly against the actual codebase state (see `docs/GAP_ANALYSIS.md`).

---

# Feature Copy — Athenus Knowledge OS

## Section header

- **Eyebrow:** Features
- **Headline:** Engineered for Deep Learning & Total Privacy
- **Subtitle:** Everything you need to turn hours of video lectures and course media into searchable, explainable knowledge — running 100% offline on your desktop.

---

## ⚡ Shipped & Available Today (completed implementations)

### 1. Multimodal Video Ingestion
Drag-and-drop MP4/MKV video or WAV/MP3 audio. Local Faster-Whisper transcribes with word-level timestamps, then a semantic chunker and BGE embeddings index everything offline.
*Wired: upload → FFmpeg audio extract → transcribe → chunk → Qdrant vector index, with live SSE progress.*

### 2. Local-First Knowledge Storage
All transcripts, vector indexes, chat history, and settings live in a local SQLite database (`./data/athenus.db`) and embedded Qdrant. Works fully offline. No telemetry, no server uploads.

### 3. Workspaces & Multi-Session Organization
Organize courses into isolated workspaces. Each keeps its own media library, vector index, and knowledge graph, with strict workspace ID isolation against cross-leakage.

### 4. Grounded RAG Chat with Timestamp Citations
Ask questions and get answers grounded in your own media. Returns clickable `[MM:SS]` badges you can jump to in the video player, plus the exact transcript segments referenced.
- **Active playback context:** the RAG pulls the transcription ±30s around your current position while you watch.

### 5. Hybrid Vector + Keyword Retrieval (partially live)
Dense Qdrant cosine search is fused with sparse BM25 keyword ranking to surface the most relevant passage. *(Cross-encoder re-ranking and query rewrite are still being tuned — see Roadmap.)*

### 6. Settings Persistence & Local Model Discovery
Provider/model settings saved to SQLite and auto-restored on launch. Local Ollama model discovery scans your filesystem and populates a live dropdown — no manual config.

---

## 🚧 On the Roadmap (In Progress / Planned)

> These reflect the unfinished components currently in the codebase. List them as "Coming soon."

### 1. True 8-Stage Retrieval (full depth)
Currently live: graph traversal, hybrid search, grounded prompt assembly, playback context injection. Coming: real query rewrite + HyDE, intent detection, cross-encoder re-ranking, semantic context compression — the full documented 8-stage chain.

### 2. Streaming Chat Responses
Live queries currently return a single completion. Roadmap: streaming token-by-token responses for a more conversational feel.

### 3. Knowledge Graph Visualizer
Concept extraction and prerequisite relationships exist in the backend. The interactive graph canvas on the frontend is being built to view and navigate concept nodes and prerequisites.

### 4. Active Recall Suite — Quizzes
Quiz generation is scaffolded. Currently a single static example question; the real AI-generated, content-derived quiz engine with adaptive feedback & grounded citations is in development.

### 5. Active Recall Suite — AI Flashcards with Anki Export
Flashcards likewise scaffolded. The AI-generated card deck, SM-2 spaced repetition scheduler, and native `.apkg` Anki export are coming next.

### 6. Chapter Summaries
Summary generation hooks into the pipeline but results are not yet persisted/surfaced in the UI. Coming: structured per-chapter summaries in the workspace.

### 7. Agentic AI Suite
Planner, Retriever, and Citation Validator agents are scaffolded. The multi-step autonomous planning/retrieval orchestration and the UI are being progressively built out.

### 8. Multimodal — Keyframe OCR & Slide Text Retrieval
Frame extraction exists as infrastructure. Coming soon: OCR on video keyframes (e.g., PaddleOCR) and embedded slide text retrieval.

---

## 🔮 Far Future (Vision)

- PDF, PPTX, eBook, and research-paper ingestion
- Web & GitHub repository documentation indexing
- Learning analytics dashboard (mastery %, retention curves, revision recommendations)

---

# How It Works (3-Step Learning Workflow)

## Section header

- **Eyebrow:** How It Works
- **Headline:** From Raw Lecture to Lasting Mastery in Three Steps
- **Subtitle:** Import your videos once, and Athenus keeps working — indexing, answering, and drilling you until the knowledge sticks.

---

## Step 1 — Import & Index (Seconds)

Drag-and-drop your lecture video or audio. Local Faster-Whisper transcribes every word with timestamps, the semantic chunker splits the transcript, and BGE embeddings index it into your workspace's vector store — all fully offline, with live progress.

**What you get:** A searchable, timestamped transcript and vector index ready for retrieval.

---

## Step 2 — Converse & Explore (Minutes)

Ask complex questions across any video in your workspace. Athenus retrieves the most relevant passages (hybrid vector + keyword search), grounds every answer, and returns clickable `[MM:SS]` timestamp citations that jump straight to the exact frame — including the transcript around where you're currently watching.

**What you get:** Grounded answers with verifiable proof, never blind chatbot guesses.

---

## Step 3 — Master & Retain (Forever)

Traverse prerequisite concept maps, test yourself with auto-generated quizzes, and review AI-crafted flashcards on an SM-2 spaced repetition schedule you can export to Anki.

**What you get:** Active recall loops that convert passive watching into durable knowledge.

*(Steps 3 features are progressively shipping — see Roadmap above.)*
