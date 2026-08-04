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
| **Containerization** | **Docker / Compose v2** | Podman / manual setup | Dockerized dev stack (backend + frontend + Ollama) enables single-command onboarding and GPU passthrough via the NVIDIA Container Toolkit; native desktop dev remains fully supported. |

---

## Containerized Services

| Compose Service | Image / Dockerfile | Port | Runtime Role |
| :--- | :--- | :--- | :--- |
| `backend` | `docker/backend/Dockerfile.dev` / `Dockerfile.gpu` | 8000 | FastAPI (Uvicorn `--reload`); GPU overlay uses CUDA image |
| `frontend` | `docker/frontend/Dockerfile.dev` | 3000 | Next.js dev server (HMR) |
| `ollama` | `ollama/ollama:latest` | 11434 | Local LLM; GPU-enabled via overlay |
| `backend` (prod) | `docker/backend/Dockerfile` | 8000 | Multi-stage, non-root, `--workers 1` |
| `frontend` (prod) | `docker/frontend/Dockerfile` + `nginx.conf` | 80 | Static export served by nginx |

**Deployment Modes**: CPU dev (`docker compose up -d --build`), GPU dev (`-f docker-compose.gpu.yml`), self-hosted prod (`docker-compose.prod.yml`). Tauri desktop remains a **native host process** talking to the containerized backend. See [`DEPLOYMENT.md`](DEPLOYMENT.md) and [`ONBOARDING.md`](ONBOARDING.md).
