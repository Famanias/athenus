# DEPLOYMENT.md

# Athenus — Deployment Strategies

---

## 1. Local Desktop Mode (Default)

* **Shell**: Tauri native binary (`frontend/src-tauri/`)
* **Backend**: PyInstaller bundled Python sidecar executable
* **Database**: Embedded SQLite (`./data/athenus.db`)
* **Vector Store**: Embedded Qdrant (`./data/qdrant`)
* **Models**: Local Ollama + Faster-Whisper + BGE Small Embeddings

### Native development workflow
```bash
cp .env.example .env
cd backend
python -m venv venv
pip install -r requirements.txt
python app/main.py          # FastAPI on :8000

# Second terminal
cd frontend
npm install
npx tauri dev
```

---

## 2. Dockerized Web Development (Single Command)

Everything runs in containers except the browser. Requires **Docker Desktop** (or Docker Engine + Compose v2 on Linux). No Python/Node install needed.

| Service  | Image / Dockerfile          | Port   | Notes |
| :---     | :---                        | :---   | :--- |
| `backend`| `docker/backend/Dockerfile.dev` | 8000 | FastAPI + Uvicorn `--reload`, bind-mounted source |
| `frontend`| `docker/frontend/Dockerfile.dev` | 3000 | Next.js dev server with HMR |
| `ollama` | `ollama/ollama:latest`      | 11434 | Containerized local LLM |

### CPU workflow
```bash
git clone https://github.com/Famanias/athenus.git
cd athenus
./scripts/setup.sh          # or setup.ps1 on Windows (creates .env if missing)
./scripts/dev.sh            # or: docker compose up -d --build
# Open http://localhost:3000
```

### GPU workflow (NVIDIA, e.g. RTX 3060 / 4070 / 5090)
1. Install NVIDIA GPU drivers and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (WSL2 supported on Windows).
2. Start with the GPU overlay (builds a CUDA-enabled backend image):
```bash
./scripts/dev.sh --gpu
# equivalent: docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
```
3. Verify GPU allocation: `docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec backend nvidia-smi`.

> **Note on the GPU profile**: the GPU path is an *overlay* compose file that upgrades the existing `backend`/`ollama` services (CUDA torch image + `device_requests`), rather than spawning duplicate services. The `--profile gpu` flag alone does not activate GPU mode — the overlay file is required.

### Desktop (Tauri) + containerized backend
```bash
cd athenus
docker compose up -d backend
cd frontend
npm install
npm run tauri dev
```
Both the web container and the native desktop shell share `./data/` (SQLite + Qdrant + uploads) via the host bind mount.

### Local Model Storage & Docker Bind Mounts
- **Platform Runtime Detection (`RuntimeService`)**: The backend automatically detects its execution environment (`NATIVE`, `DOCKER`, `TAURI`, `WEB`).
- **Native Desktop Mode**: The backend runs directly on host OS with full filesystem access to custom model paths (e.g. `E:\ollama\models`).
- **Docker Container Mode**: Unmounted host paths return friendly environment guidance explaining container boundaries.
- **Optional Docker Host Bind Mount**: To allow a Docker containerized backend to scan a custom host directory (e.g., `E:\ollama\models`), add an optional bind mount under `services.backend.volumes` in `docker-compose.yml`:
  ```yaml
  volumes:
    - ./backend:/app
    - ./data:/app/data
    - hf-cache:/root/.cache/huggingface
    # Optional host model directory bind mount:
    # - E:\ollama\models:/mnt/ollama
  ```

### Environment configuration
- `.env.example` keeps **native** defaults (`./data/...`, `http://localhost:11434`) so native dev keeps working.
- `docker-compose.yml` overrides container paths (`/app/data/...`) and `OLLAMA_BASE_URL=http://ollama:11434` via its `environment:` block — do **not** rewrite `.env.example` to container paths.
- Switch Ollama to host passthrough by setting `OLLAMA_BASE_URL=http://host.docker.internal:11434` in `docker-compose.yml` (`host.docker.internal` is wired via `extra_hosts: host-gateway`).
- Health check: `curl http://localhost:8000/api/v1/health`.

### Common commands
```bash
docker compose up -d --build      # start stack
docker compose ps                 # status / healthchecks
docker compose logs -f backend    # follow backend logs
docker compose down               # stop (keeps named volumes + ./data)
docker compose down -v            # stop AND delete named volumes (models re-download)
```

---

## 3. Self-Hosted Server Mode (Docker Compose)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```
* Backend: optimized multi-stage image (`docker/backend/Dockerfile`), non-root, `restart: unless-stopped`, single worker (embedded SQLite/Qdrant are single-process file stores).
* Frontend: Next.js static export (`output: "export"`) served by nginx on port 80.
* Ollama: containerized on 11434.
* SQLite for single-node persistence; embedded Qdrant vector store.

> **Note — cloud LLM provider keys in production:** `docker-compose.prod.yml` does **not** use `env_file`, so keys from your local `.env` are not injected into the container automatically. To use cloud providers (Groq / OpenRouter / OpenAI / Anthropic / custom), pass the keys explicitly, e.g.:
>
> ```bash
> GROQ_API_KEY=... OPENROUTER_API_KEY=... \
>   OPENAI_API_KEY=... ANTHROPIC_API_KEY=... \
>   docker compose -f docker-compose.prod.yml up -d --build
> ```
>
> or add explicit `environment:` entries to the `backend` service in `docker-compose.prod.yml`. Keys are read at runtime by `ProviderConfigResolver` from the container environment (`backend/app/core/config.py`).

> For true multi-user scale-out, the documented target (see `docs/adr/0003-qdrant-embedded-vector-store.md` and `CONTEXT.md`) is PostgreSQL + containerized Qdrant; the embedded stack above is appropriate for self-hosted single-instance use.

## 4. Cloud Mode (Railway / VPS)
* FastAPI deployed to Railway / Coolify
* Supabase / PostgreSQL for cloud metadata
* Qdrant Cloud for managed vector database
