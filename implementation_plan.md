# Implementation Plan: Dockerized Development Architecture for Athenus

---

## 1. Executive Summary

Athenus is a local-first AI Learning Companion delivered as both a **Web Application (Next.js)** and a **Desktop Application (Tauri)** powered by a single **FastAPI Python Backend**. 

This implementation plan establishes a **Dockerized Development Architecture** that streamlines onboarding to a single command (`docker compose up -d --build`) for web developers, while keeping desktop (Tauri) development friction-free.

### Key Outcomes
- **Single-Command Web Setup**: Developers access `http://localhost:3000` with containerized Next.js, FastAPI, and optional local LLM services.
- **Native Desktop Integration**: Desktop developers run Tauri natively while seamlessly talking to the containerized FastAPI backend.
- **Preserved Local-First Philosophy**: Embedded SQLite, file-based Qdrant vector storage, local SentenceTransformers (`bge-small-en-v1.5`), and Faster-Whisper remain 100% offline and local.
- **Developer Experience & Hot Reloading**: Source code bind mounts enable instant hot-reloading for both backend (Uvicorn `--reload`) and frontend (Next.js HMR).
- **GPU Acceleration Architecture**: Support for NVIDIA RTX GPUs (e.g. RTX 3060, 4070, 5090) via NVIDIA Container Toolkit and Docker Compose `--profile gpu`.

---

## 2. Current Architecture Analysis

```
+-----------------------------------------------------------------------------------+
|                                HOST ENVIRONMENT                                   |
|                                                                                   |
|  +----------------------------+        +---------------------------------------+  |
|  |   Tauri Desktop Shell      |        |        Browser (Web Mode)             |  |
|  |   (Rust / Webview)         |        |        http://localhost:3000          |  |
|  +--------------+-------------+        +-------------------+-------------------+  |
|                 |                                          |                      |
|                 | IPC / HTTP                               | HTTP                 |
|                 v                                          v                      |
|  +-----------------------------------------------------------------------------+  |
|  |                           FastAPI Backend                                   |  |
|  |                           (Python 3.11)                                     |  |
|  |  +---------------------+   +---------------------+   +-------------------+  |  |
|  |  |  SQLite (SQLModel)  |   |  Embedded Qdrant    |   | FFmpeg Extractor  |  |  |
|  |  |  ./data/athenus.db  |   |  ./data/qdrant      |   | (16kHz WAV)       |  |  |
|  |  +---------------------+   +---------------------+   +-------------------+  |  |
|  |  +---------------------+   +---------------------+   +-------------------+  |  |
|  |  | SentenceTransformers|   |   Faster-Whisper    |   | Ollama HTTP Client|  |  |
|  |  | (bge-small-en-v1.5) |   |   (CTranslate2)     |   | (localhost:11434) |  |  |
|  |  +---------------------+   +---------------------+   +-------------------+  |  |
|  +-----------------------------------------------------------------------------+  |
+-----------------------------------------------------------------------------------+
```

### Key Architectural Characteristics
1. **Single Backend Core**: FastAPI serves REST endpoints for media management, chat, graph visualization, learning tools, and agent workflows.
2. **Embedded Infrastructure**: SQLite database and file-based Qdrant vector store run embedded inside the Python backend process without requiring separate database server daemons.
3. **Local AI Model Pipelines**: PyTorch models (SentenceTransformers) and CTranslate2 models (Faster-Whisper) load directly into backend memory; system dependencies include `ffmpeg` binary for audio extraction.
4. **LLM Provider Abstraction**: Supports local Ollama (`http://localhost:11434`) as well as optional cloud fallback providers (Groq, OpenRouter, Gemini, Claude).

---

## 3. Existing Services Inventory

| Service / Dependency | Current Runtime | Storage / Location | Containerization Recommendation | Preserved Philosophy |
| :--- | :--- | :--- | :--- | :--- |
| **FastAPI Backend** | Python 3.11 process | `backend/` | **Containerized** (`Dockerfile.dev`) | Core backend logic & API standard preserved. |
| **Next.js Web Frontend** | Node.js 20+ process | `frontend/` | **Containerized** (`Dockerfile.dev`) | React/Next.js HMR preserved; static export intact. |
| **SQLite DB** | Python `sqlmodel` embedded | `./data/athenus.db` | **Embedded in Backend** (Volume Mount) | Local file storage preserved. |
| **Qdrant Vector Store** | Python `qdrant-client` file-based | `./data/qdrant` | **Embedded in Backend** (Volume Mount) | Zero-config vector search preserved. |
| **Faster-Whisper (STT)** | Python `faster-whisper` | Model cache: `~/.cache/huggingface` | **Embedded in Backend** (Volume Mount / Optional GPU passthrough) | 100% offline transcription with CUDA support. |
| **Sentence-Transformers**| Python `sentence-transformers` | Model cache: `~/.cache/huggingface` | **Embedded in Backend** (Volume Mount) | 100% offline embeddings (384-d). |
| **FFmpeg Binary** | Host binary (`shutil.which`) | Host OS | **Installed in Backend Container** | Audio extraction automated in Linux container. |
| **Ollama (LLM)** | Host Ollama service (`:11434`) | Host Ollama models | **Dual Option**: Containerized service or host passthrough (GPU supported) | Developer flexibility (containerized or local host). |
| **Tauri Desktop Shell** | Native Rust binary | `frontend/src-tauri` | **Native on Host OS** | Native OS windowing & IPC preserved. |

---

## 4. Dockerization Strategy

We adopt a **composable multi-target strategy** centered around `docker-compose.yml` with separate container configurations for development, GPU-accelerated execution, and production environments.

### Core Objectives
1. **Developer Experience (DX)**: Zero manual dependency installation besides Docker Desktop. Live code reloading for FastAPI and Next.js.
2. **Parity**: Development containers mimic production runtime while allowing host directory mounting.
3. **Efficiency**: Multi-stage build targets to keep container build times fast and cached.
4. **Hardware Flexibility**: CPU fallback by default, with seamless GPU passthrough via Docker Compose profiles (`--profile gpu`).

---

## 5. Services to Containerize

### 1. `backend` Service (FastAPI)
- **Base Image**: `python:3.11-slim-bookworm`
- **System Packages**: `ffmpeg`, `build-essential`, `curl`
- **Port Mapping**: `8000:8000`
- **Command**: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload`
- **Volume Mounts**: Source code (`./backend:/app`), persistent data (`./data:/app/data`), model cache (`hf-cache:/root/.cache/huggingface`).

### 2. `frontend` Service (Next.js Web)
- **Base Image**: `node:20-alpine`
- **Port Mapping**: `3000:3000`
- **Command**: `npm run dev` (listening on `0.0.0.0`)
- **Volume Mounts**: Source code (`./frontend:/app`), anonymous volume for `node_modules` (`/app/node_modules`), `.next` cache.
- **Environment**: `NEXT_PUBLIC_API_URL=http://localhost:8000`

### 3. `ollama` Service (Optional Compose Profile)
- **Base Image**: `ollama/ollama:latest`
- **Port Mapping**: `11434:11434`
- **Volume Mounts**: `ollama-data:/root/.ollama`
- **Profile**: Activated by default or when host Ollama is not present.

---

## 6. Services to Keep Native

### 1. Tauri Desktop Shell (`frontend/src-tauri`)
- **Reason**: Tauri relies on native OS webviews (WebView2 on Windows, WebKitGTK on Linux, WKWebView on macOS) and Rust compilation. Containerizing Tauri desktop GUI leads to cross-platform display backend instability and violates Tauri's native design.
- **Workflow**: Desktop developers run `docker compose up -d backend` to start the backend, then run `npm run tauri dev` natively on their machine.

---

## 7. GPU Support & Hardware Acceleration Architecture

Many Athenus users possess modern NVIDIA GPUs (e.g., RTX 3060, RTX 4070, RTX 5090) and require GPU hardware acceleration for local AI inference:
- **Faster-Whisper**: Audio transcription accelerated via CTranslate2 CUDA backends (`device="cuda"`).
- **Ollama**: Local LLM generation accelerated via CUDA GGUF execution.

### Architectural Blueprint for GPU Support

We utilize **Docker Compose Profiles** (`--profile gpu`) and the **NVIDIA Container Toolkit** so that CPU users experience zero overhead while GPU users can enable hardware acceleration seamlessly.

#### 1. Hardware & Driver Prerequisites
- **Host Software**: NVIDIA GPU Drivers + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (WSL2 supported on Windows).

#### 2. Compose Specification with `device_requests` (`driver: nvidia`)

```yaml
# docker-compose.yml

services:
  backend:
    build:
      context: .
      dockerfile: docker/backend/Dockerfile.dev
    ports:
      - "8000:8000"
    # CPU default configuration

  # GPU-accelerated Ollama service
  ollama-gpu:
    profiles: ["gpu"]
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama-data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  # GPU-accelerated Backend service (Faster-Whisper CUDA enabled)
  backend-gpu:
    profiles: ["gpu"]
    build:
      context: .
      dockerfile: docker/backend/Dockerfile.gpu
    ports:
      - "8000:8000"
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - hf-cache:/root/.cache/huggingface
    environment:
      - WHISPER_DEVICE=cuda
      - WHISPER_COMPUTE_TYPE=float16
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
```

#### 3. Developer Workflow for GPU Acceleration
```bash
# Start GPU-accelerated development stack
docker compose --profile gpu up -d --build
```

---

## 8. Networking Architecture

```
+-----------------------------------------------------------------------------------------+
|                                    DOCKER NETWORK (athenus-net)                         |
|                                                                                         |
|  +-------------------------+      HTTP       +---------------------------------------+  |
|  |                         |  (browser side) |                                       |  |
|  |    frontend             +---------------->+    backend / backend-gpu              |  |
|  |    (Next.js dev:3000)   |                 |    (FastAPI:8000)                     |  |
|  |                         |                 |                                       |  |
|  +-------------------------+                 +-------------------+-------------------+  |
|                                                                  |                      |
|                                                                  | HTTP                 |
|                                                                  v                      |
|                                              +-------------------+-------------------+  |
|                                              |  ollama / ollama-gpu                  |  |
|                                              |  (Ollama:11434)                       |  |
|                                              +---------------------------------------+  |
+-----------------------------------------------------------------------------------------+
                                                                   ^
                                                                   | host.docker.internal
                                               +-------------------+-------------------+
                                               | Host Ollama (if running on host OS)   |
                                               +---------------------------------------+
```

- **Bridge Network**: Custom bridge network `athenus-net`.
- **Hostname Resolution**: 
  - Internal container-to-container calls use service names (`http://backend:8000`, `http://ollama:11434`).
  - Browser-to-backend calls use `http://localhost:8000`.
  - Host Ollama fallback uses `http://host.docker.internal:11434` via `extra_hosts`.

---

## 9. Persistent Storage Strategy

Data persistence is critical for local-first functionality.

| Data Type | Path in Container | Host Persistence Method | Rationale |
| :--- | :--- | :--- | :--- |
| **SQLite Database** | `/app/data/athenus.db` | Bind Mount (`./data:/app/data`) | Immediate access to DB file on host; shared with desktop app. |
| **Qdrant Vector Data** | `/app/data/qdrant/` | Bind Mount (`./data:/app/data`) | Vector indexes persist across container restarts. |
| **Media Uploads** | `/app/data/uploads/` | Bind Mount (`./data:/app/data`) | User uploaded audio/video files remain locally inspectable. |
| **Hugging Face / Whisper Models** | `/root/.cache/huggingface` | Named Volume (`hf-cache`) | Avoids re-downloading BGE and Whisper models on every container rebuild. |
| **Ollama LLM Models** | `/root/.ollama` | Named Volume (`ollama-data`) | Preserves downloaded GGUF weights (`llama3:8b`). |

---

## 10. Volume Strategy

### Recommended Volume Layout in `docker-compose.yml`:
```yaml
volumes:
  hf-cache:
    driver: local
  ollama-data:
    driver: local
```

### Bind Mount Layout:
```yaml
services:
  backend:
    volumes:
      - ./backend:/app
      - ./data:/app/data
      - hf-cache:/root/.cache/huggingface
```

---

## 11. Environment Variable Strategy

We maintain a centralized `.env.example` file at the root of the repository, copied to `.env` by developers.

### `.env` File Structure
```env
# General
PROJECT_NAME="Athenus"
ENVIRONMENT="development"
DEBUG=true
API_V1_PREFIX="/api/v1"

# Database & Storage
DATABASE_URL="sqlite:////app/data/athenus.db"
QDRANT_PATH="/app/data/qdrant"
QDRANT_COLLECTION="transcript_chunks"
UPLOADS_DIR="/app/data/uploads"

# Local AI Models
DEFAULT_LLM_PROVIDER="ollama"
# Set to http://ollama:11434 if using containerized Ollama, or http://host.docker.internal:11434 for host Ollama
OLLAMA_BASE_URL="http://host.docker.internal:11434"
DEFAULT_LLM_MODEL="llama3:8b"

DEFAULT_STT_PROVIDER="faster_whisper"
WHISPER_MODEL_SIZE="base"
WHISPER_DEVICE="cpu"           # Set to 'cuda' when using --profile gpu
WHISPER_COMPUTE_TYPE="int8"    # Set to 'float16' for GPU acceleration

DEFAULT_EMBEDDING_PROVIDER="sentence_transformers"
EMBEDDING_MODEL_NAME="BAAI/bge-small-en-v1.5"

# Web Frontend Config
NEXT_PUBLIC_API_URL="http://localhost:8000"
```

---

## 12. Frontend ↔ Backend Communication Flow

```
[Browser on Developer Host]
        │
        ├──────► http://localhost:3000 ────────► [Next.js Container]
        │                                             │
        │                                     SSR / Proxy (Optional)
        │                                             │
        └──────► http://localhost:8000/api/v1 ───────► [FastAPI Backend Container]
```

1. **Client-Side Requests**: Browser renders Next.js UI from port `3000` and issues API requests directly to `http://localhost:8000` (port mapped from FastAPI container).
2. **CORS Configuration**: FastAPI `CORSMiddleware` already allows `allow_origins=["*"]`, enabling requests from `localhost:3000` and Tauri native webview origins.
3. **API Standardization**: Update hardcoded `http://localhost:8000` calls in frontend features (`useGraph.ts`, `useFlashcards.ts`) to use `API_BASE_URL` from `src/config/env.ts`.

---

## 13. Desktop ↔ Backend Communication Flow

```
[Developer Machine (Native Host)]
        │
        ├──► Tauri Desktop App (Native GUI)
        │         │
        │         │ HTTP API / SSE (`http://localhost:8000/api/v1`)
        │         v
        └──► [FastAPI Container] (Exposing 8000:8000)
                  │
                  ├──► SQLite (`./data/athenus.db` bind mount)
                  ├──► Qdrant (`./data/qdrant` bind mount)
                  └──► Ollama (`host.docker.internal:11434`)
```

- Desktop developers run `docker compose up -d backend` (or full backend suite).
- Tauri app connects to `http://localhost:8000/api/v1`.
- Both desktop app and web container share the same `./data/athenus.db` database file via host bind mount, ensuring complete state sync between web and desktop modes during testing.

---

## 14. Development Workflow

### Standard CPU Web Developer Workflow
```bash
# 1. Clone repository
git clone https://github.com/Famanias/athenus.git
cd athenus

# 2. Copy environment configuration
cp .env.example .env

# 3. Start standard containerized stack
docker compose up -d --build

# 4. Access web application
# Open http://localhost:3000 in browser
```

### GPU-Accelerated Web Developer Workflow (RTX 3060 / 4070 / 5090)
```bash
# Start GPU-accelerated stack
docker compose --profile gpu up -d --build
```

### Desktop (Tauri) Developer Workflow
```bash
# 1. Start Dockerized backend
docker compose up -d backend

# 2. Start native Tauri application
cd frontend
npm install
npm run tauri dev
```

---

## 15. Production Workflow

For self-hosted server deployment without GUI:
- Multi-stage `Dockerfile` builds optimized production images:
  - Backend: `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4`
  - Frontend: Next.js production build served via lightweight NGINX or Next.js standalone Node server.
- `docker-compose.prod.yml` defines restart policies (`restart: unless-stopped`), security hardening, and production log limits.

---

## 16. Recommended Repository Structure

```
athenus/
├── .dockerignore
├── .env.example
├── docker-compose.yml
├── docker-compose.prod.yml
├── docker/
│   ├── backend/
│   │   ├── Dockerfile
│   │   ├── Dockerfile.dev
│   │   └── Dockerfile.gpu
│   └── frontend/
│       ├── Dockerfile
│       ├── Dockerfile.dev
│       └── nginx.conf
├── scripts/
│   ├── dev.sh
│   ├── dev.ps1
│   ├── setup.sh
│   └── setup.ps1
├── backend/
│   ├── app/
│   ├── requirements.txt
│   └── ...
├── frontend/
│   ├── src/
│   ├── package.json
│   └── ...
├── data/                  # Shared persistent local storage
└── docs/
```

---

## 17. Security Considerations

1. **Non-Root Execution**: Container definitions use non-root users (`node`, `appuser`) where applicable for production targets.
2. **CORS Hardening**: Restrict CORS origins in production environments via environment variables.
3. **Secret Protection**: `.env` files added to `.gitignore` and `.dockerignore` to prevent accidental credential commits.
4. **Local Host Isolation**: Docker network isolates internal services while exposing only explicit ports (3000, 8000, 11434).

---

## 18. Risk Assessment

| Risk | Impact | Mitigation Strategy |
| :--- | :--- | :--- |
| **Missing NVIDIA Container Toolkit on Host** | `--profile gpu` container fails to start. | Provide clear error message and fallback CPU instructions in `README.md`. |
| **PyTorch / CTranslate2 CPU performance in container** | Transcriptions / embeddings could run slower in containerized CPU. | Mount Hugging Face model cache volume; document GPU pass-through option (`--profile gpu`). |
| **Ollama connectivity from container** | Backend container unable to reach Ollama on host. | Include `host.docker.internal:host-gateway` in `extra_hosts` and provide optional containerized Ollama profile. |
| **SQLite DB lock on shared access** | Desktop app and Backend container accessing `./data/athenus.db` simultaneously. | SQLite WAL mode enabled; proper connection handling in SQLModel session. |
| **Port collisions** | Port 3000, 8000, or 11434 already in use on developer machine. | Parameterize ports in `.env` (`PORT_FRONTEND`, `PORT_BACKEND`, `PORT_OLLAMA`). |

---

## 19. Migration Strategy

1. **Zero-Downtime Transition**: Existing local scripts (`python app/main.py` and `npm run dev`) remain fully functional.
2. **Incremental Adoption**: Developers can adopt Docker containerization at their own pace without breaking existing setups.
3. **Frontend Standardizing**: Refactor hardcoded frontend API URLs to environment-driven configuration before enabling containerized web stack.

---

## 20. Step-by-Step Implementation Phases

### Phase 1: Repository Organization & Environment Configuration
- [ ] Create directory structure (`docker/backend/`, `docker/frontend/`, `scripts/`).
- [ ] Create root `.dockerignore` file.
- [ ] Update `.env.example` with Docker-friendly defaults, GPU variables (`WHISPER_DEVICE`, `WHISPER_COMPUTE_TYPE`), and documentation comments.
- [ ] Standardize frontend API client configuration in `frontend/src/features/graph/useGraph.ts` and `frontend/src/features/flashcards/useFlashcards.ts` to use `API_BASE_URL`.

### Phase 2: Backend Containerization (CPU & GPU)
- [ ] Create `docker/backend/Dockerfile.dev` with Python 3.11, system packages (`ffmpeg`), and dependency installation.
- [ ] Create `docker/backend/Dockerfile.gpu` configured with CUDA base libraries for Faster-Whisper acceleration.
- [ ] Create `docker/backend/Dockerfile` multi-stage build for production.
- [ ] Test backend container build and verification (`uvicorn` execution, `ffmpeg` verification, SQLite initialization).

### Phase 3: Frontend Containerization
- [ ] Create `docker/frontend/Dockerfile.dev` with Node 20 alpine and Next.js development server.
- [ ] Create `docker/frontend/Dockerfile` and `docker/frontend/nginx.conf` for production web serving.
- [ ] Test frontend container build and verification.

### Phase 4: Docker Compose Orchestration & GPU Profiles
- [ ] Create root `docker-compose.yml` orchestrating `backend`, `frontend`, and `ollama` services.
- [ ] Add `gpu` profile with NVIDIA Container Toolkit `device_requests` (`driver: nvidia`, `capabilities: [gpu]`) for `ollama-gpu` and `backend-gpu`.
- [ ] Configure `athenus-net` bridge network, `extra_hosts` (`host.docker.internal`), healthchecks, and volume mounts (`hf-cache`, `ollama-data`, `./data`).
- [ ] Create `docker-compose.prod.yml` for production self-hosting deployments.

### Phase 5: Helper Scripts & Developer Tooling
- [ ] Create cross-platform setup and dev scripts (`scripts/dev.sh`, `scripts/dev.ps1`, `scripts/setup.sh`, `scripts/setup.ps1`).
- [ ] Add support for GPU startup flags (`./scripts/dev.sh --gpu`).

### Phase 6: Documentation & Verification
- [ ] Update `README.md` and `docs/DEPLOYMENT.md` with step-by-step onboarding instructions for CPU Web, GPU Web, and Desktop modes.
- [ ] Verify full web application workflow (`docker compose up -d --build` -> `http://localhost:3000`).
- [ ] Verify full desktop application workflow (`docker compose up -d backend` -> `npm run tauri dev`).

---

## Verification Plan

### Automated & Sanity Tests
- Build docker images: `docker compose build`
- Run container healthchecks: `docker compose ps`
- Backend API test: `curl http://localhost:8000/api/v1/health`
- Frontend HTTP test: `curl http://localhost:3000`

### Manual Verification Matrix
1. **CPU Web App Flow**:
   - Run `docker compose up -d --build`.
   - Open browser at `http://localhost:3000`.
   - Test media upload, transcript generation, chat, and graph view.
2. **GPU Web App Flow (NVIDIA RTX)**:
   - Run `docker compose --profile gpu up -d --build`.
   - Verify GPU allocation via `nvidia-smi` inside container and Faster-Whisper CUDA acceleration.
3. **Desktop (Tauri) App Flow**:
   - Run `docker compose up -d backend`.
   - Run `cd frontend && npm run tauri dev`.
   - Confirm desktop GUI communicates with containerized backend at `http://localhost:8000`.
