<!-- TODO: replace with a real Athenus wordmark image -->
<p align="center">
  <img src="docs/athenus-wordmark.png" alt="Athenus" width="238">
</p>

<p align="center">
  A local-first AI operating system for interactive learning, multimodal retrieval, and agentic AI workflows.
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> ·
  <a href="docs/DEPLOYMENT.md">Setup Guide</a> ·
  <a href="docs/CONTRIBUTING.md">Contributing</a> ·
  <a href="docs/ROADMAP.md">Roadmap</a>
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="backend/"><img src="https://img.shields.io/badge/Python-3.11+-brightgreen.svg" alt="Python 3.11+"></a>
  <a href="src-tauri/"><img src="https://img.shields.io/badge/Tauri-1.5+-blueviolet.svg" alt="Tauri 1.5+"></a>
  <a href="frontend/"><img src="https://img.shields.io/badge/Next.js-16+-black.svg" alt="Next.js 16+"></a>
  <a href="backend/tests/"><img src="https://img.shields.io/badge/Tests-50%20Passed-success.svg" alt="Tests: 50 Passed"></a>
</p>

<!-- TODO: replace with a real interface screenshot -->
<p align="center">
  <img src="docs/athenus-screenshot.png" alt="Athenus interface">
</p>

---

## Quick Start

> Athenus is a local-first desktop app. Everything — transcription, embeddings, vector search, and chat — runs on your machine with zero API cost. Native installs, GPU/ASR notes, and configuration live in the [setup guide](docs/DEPLOYMENT.md).

```bash
git clone https://github.com/Famanias/athenus.git
cd athenus
cp .env.example .env

# Terminal 1 — Backend engine (FastAPI on :8000)
cd backend
python -m venv venv
.\venv\Scripts\activate    # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
python app/main.py

# Terminal 2 — Desktop application (Tauri + Next.js)
cd frontend
npm install
npx tauri dev
```

## Features

- **Chat + RAG** — multi-session chat with grounded answers and per-message clickable `[MM:SS]` timestamp citations that jump the video player to the exact scene.
- **8-Stage Layered Retrieval** — hybrid search (Qdrant dense + BM25 sparse), HyDE query rewriting, cross-encoder re-ranking, and context compression.
- **Local-First & Privacy** — Faster-Whisper speech-to-text, BGE Small embeddings, Embedded Qdrant, and local Ollama LLMs run 100% offline.
- **Agentic AI Suite** — a multi-agent coordinator orchestrating `PlannerAgent`, `RetrieverAgent`, and `CitationValidatorAgent`.
- **Knowledge Graph Engine** — concept node traversal and automated prerequisite discovery with strict per-workspace isolation.
- **Active Recall Learning** — automated chapter outlines, quizzes, and spaced-repetition flashcards (Anki SM-2 export).
- **Multi-Video Workspaces** — group media into isolated workspaces with cross-media search and persistent chat threads.
- **Provider-Agnostic** — optional cloud LLMs (Groq, OpenRouter, Gemini, Claude) behind an abstract AI Service Bus.
- **Observable AI** — persistent audit logs and real-time SSE progress streaming for every ingestion and retrieval step.

## Demo

Interactive HTML mockups of the interface live in [`docs/mockups/`](docs/mockups/): the [home dashboard](docs/mockups/home-dashboard.html), [video workspace](docs/mockups/video-workspace.html), and [transcript reader](docs/mockups/transcript-reader.html).

## Contributing

Help is welcome. The best entry points are fresh-install testing, provider/ASR setup bugs, frontend polish, docs, and small focused refactors. See [CONTRIBUTING.md](docs/CONTRIBUTING.md) and [ROADMAP.md](docs/ROADMAP.md). Run the backend test suite with:

```bash
cd backend
python -m pytest tests
```

## Security

Athenus is a local-first, offline-capable workspace with powerful local tools. Keep private data and `.env` out of Git, and do not expose the FastAPI or vector-store ports publicly without auth. Deployment and security details are in the [setup guide](docs/DEPLOYMENT.md).

## License

MIT — see [LICENSE](LICENSE).
