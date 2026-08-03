# TECH_STACK.md

# Athenus — Technology Stack & Tradeoffs

---

## Core Technologies

| Component | Selected Technology | Alternative Evaluated | Selection Rationale & Tradeoffs |
| :--- | :--- | :--- | :--- |
| **Desktop Shell** | **Tauri (Rust)** | Electron | **Tauri** chosen for ultra-low RAM footprint (~30MB vs ~150MB Electron), native binary security, and Rust sidecar integration. |
| **Presentation** | **React + Next.js + TS** | Vue / Svelte | **Next.js** provides rapid UI development, robust SSR/SSG, and large ecosystem for custom video players. |
| **Backend API** | **FastAPI (Python 3.11)** | Express.js / Go | **FastAPI** provides native Python async execution, Pydantic data validation, OpenAPI doc generation, and ML library ecosystem. |
| **Embedded Database** | **SQLite (SQLModel)** | PostgreSQL | **SQLite** chosen for zero-config single-user desktop mode. PostgreSQL supported for cloud/multi-user mode. |
| **Vector DB** | **Embedded Qdrant** | Chroma / Milvus | **Embedded Qdrant** (`qdrant-client` local path) eliminates mandatory Docker Desktop requirement for desktop end-users. |
| **Speech-to-Text** | **Faster-Whisper** | OpenAI Whisper API | **Faster-Whisper** provides 4x faster local CTranslate2 inference with integer quantization and zero API cost. |
| **Embeddings** | **BAAI BGE Small** | OpenAI `text-embedding-3` | **BAAI BGE** (`bge-small-en-v1.5`) runs 100% offline, generating 384-d vectors with top-tier retrieval performance. |
| **Local LLM** | **Ollama** | LM Studio | **Ollama** offers simple CLI REST API integration for streaming local LLM text generation. |
