# ONBOARDING.md

# Athenus — Developer Onboarding Guide

Fresh-clone setup for all development modes: **Web (Docker)**, **Web (GPU)**, **Desktop (Tauri)**, and **Native Non-Docker (Virtualenv)**.

---

## 1. Prerequisites

| Tool | Required for | Notes |
| :--- | :--- | :--- |
| **Git** | Everything | |
| **Docker Desktop** (or Docker Engine + Compose v2) | Web / GPU / containerized backend | Windows: use the **WSL2** backend. Optional for native mode. |
| **Python 3.10+** | Native Non-Docker backend | Required for manual virtualenv execution without Docker. |
| **Node.js 20+** | Desktop (Tauri) / native frontend | Required for native web dev and desktop shell. |
| **Rust toolchain** | Desktop (Tauri) | Plus platform webview: WebView2 (Windows), WebKitGTK (Linux), WKWebView (macOS). |
| **NVIDIA GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)** | GPU mode only | Optional; skip for CPU. |

No Python install is needed for Dockerized workflows. For native host execution, Python 3.10+ and virtual environment tools are required.

---

## 2. Web Mode (recommended, zero manual installs)

```bash
git clone https://github.com/Famanias/athenus.git
cd athenus

# Create .env from the template (required — docker-compose.yml's `env_file: .env`
# errors if the file is missing).
cp .env.example .env
#   or on Windows: ./scripts/setup.ps1   |   on macOS/Linux: ./scripts/setup.sh

# Start the full CPU stack (backend :8000, frontend :3000, Ollama :11434)
docker compose up -d --build
#   or: ./scripts/dev.ps1 | ./scripts/dev.sh
```

Open **http://localhost:3000** in your browser.

> **PowerShell note:** if execution policy blocks `./scripts/dev.ps1`, run
> `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1`, or just use the
> plain `docker compose` commands — the scripts only auto-create `.env` and call
> the same compose commands.

### First-use model downloads & Live Model Discovery
- **Live Ollama REST API Discovery**: The backend uses `LocalModelProviderRegistry` and `OllamaProviderAdapter` to query `GET http://ollama:11434/api/tags`. Installed models automatically populate in UI dropdowns across all runtime environments—no manual folder mounts or path configuration needed.
- **BGE + Whisper**: downloaded into the named `hf-cache` volume on first
  transcription/embedding, then reused across restarts.

---

## 3. GPU Mode (NVIDIA GPUs, e.g. RTX 3060 / 4070 / 5090)

1. Install NVIDIA drivers and the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) (WSL2 supported on Windows).
2. Start with the GPU overlay (builds a CUDA-enabled backend image):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
#   or: ./scripts/dev.ps1 --gpu | ./scripts/dev.sh --gpu
```

3. Verify GPU allocation:

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml exec backend nvidia-smi
```

> The GPU path is an **overlay** compose file that upgrades the existing
> `backend`/`ollama` services (CUDA image + `device_requests`) rather than
> spawning duplicates. The `--profile gpu` flag alone does **not** activate GPU
> mode — the overlay file is required.

---

## 4. Desktop (Tauri) Mode — native shell, containerized backend

```bash
# Terminal 1 — containerized backend
docker compose up -d backend

# Terminal 2 — native Tauri app
cd frontend
npm install
npm run tauri dev
```

The desktop app reaches the API at `http://localhost:8000` and shares the same
`./data/athenus.db` (SQLite + Qdrant + uploads) as the web containers via the host bind mount.

> Do **not** run `docker compose up -d` (full stack) while also running
> `npm run tauri dev` — the containerized Next.js and Tauri's dev server would
> both claim port 3000.

---

## 5. Native / Non-Docker Mode (Manual Virtual Environment)

For developers running directly on the host OS without Docker containers:

### Step 1: Backend Virtual Environment Setup
```bash
# Navigate to the backend directory
cd backend

# Create a Python virtual environment
python -m venv venv

# Activate the virtual environment:
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Windows (cmd):
.\venv\Scripts\activate.bat
# Linux / macOS:
source venv/bin/activate

# Upgrade pip and install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 2: Environment Configuration
```bash
# Return to project root (if needed) and copy .env template
cp .env.example .env
```

### Step 3: Run Native Ollama Service
```bash
# Ensure Ollama service is installed and running on default port 11434 (https://ollama.com)
ollama serve

# Pull a default LLM model (e.g. llama3:8b)
ollama pull llama3:8b
```

### Step 4: Start Backend Server
```bash
# From the backend directory with venv activated:
python app/main.py
# Or via uvicorn directly:
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The FastAPI backend will start at `http://localhost:8000` with interactive docs at `http://localhost:8000/docs`.

### Step 5: Start Frontend Server
```bash
# In a separate terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Option A: Web Mode (Next.js Dev Server)
npm run dev

# Option B: Desktop Mode (Tauri Shell)
npm run tauri dev
```

### Step 6: Native Model Storage Inspection
In native mode, the backend has direct host filesystem access. You can configure and inspect host model storage directories (e.g., `E:\ollama\models` or `~/.ollama/models`) in **Settings → AI Models & Capability Bus Providers → Model Storage**.

---

## 6. Local Model Providers & Settings Diagnostic Panel

In **Settings → Model Sources**, Athenus provides clean, decoupled diagnostic panels:

1. **Ollama Service Daemon (Live Connection)**:
   - Queries REST health (`/api/version`) and installed models (`/api/tags`).
   - Displays real-time status badge (`✓ Connected` / `✕ Offline`), active endpoint URL (`http://localhost:11434` or `http://ollama:11434`), and model sizes.
   - Includes a manual **[ Refresh Models ]** button for instant sync.
2. **Model Storage (Offline Filesystem Inspection)**:
   - Allows native host directory inspection (e.g. `E:\ollama\models`) without interfering with live REST API model discovery.

---

## 7. Sanity Checks & Lifecycle Operations

```bash
docker compose ps                        # backend should report "healthy"
curl http://localhost:8000/api/v1/health  # {"status":"ok",...}
curl -I http://localhost:3000             # HTTP 200
docker compose logs -f backend            # follow ingestion/transcription progress
```

### Docker Lifecycle Operations

| Operation | Command | Description |
| :--- | :--- | :--- |
| **Restart All Services** | `docker compose restart` | Restarts all running containers gracefully. |
| **Restart Single Service** | `docker compose restart backend`<br>`docker compose restart frontend`<br>`docker compose restart ollama` | Restarts a specific container service. |
| **Rebuild & Update Code** | `docker compose up -d --build` | Recompiles and updates code changes across services. |
| **Rebuild Single Service** | `docker compose up -d --build frontend` | Rebuilds only the frontend container (e.g. after UI edits). |
| **Stop All Services** | `docker compose stop` | Halts containers without removing networks or data volumes. |
| **Stop Single Service** | `docker compose stop frontend` | Stops frontend container (useful to free port 3000 for `npx tauri dev`). |
| **Take Down Stack** | `docker compose down` | Stops containers and removes network bridges (preserves `./data` and volumes). |
| **Fresh Uninstall & Volume Reset** | `docker compose down -v` | Stops stack and **deletes named volumes** (database, model cache, transcripts). |
| **Complete Fresh Purge** | `docker compose down -v --rmi all --remove-orphans` | Deletes all containers, volumes, networks, and built Docker images. |
| **Docker System Cleanup** | `docker system prune -a --volumes` | Removes all unused containers, images, and cached build layers. |

### Updating Docker After Code Revisions

The **development stack** (`docker-compose.yml`) bind-mounts source code into the
containers, so most edits are picked up **without any rebuild**:

- `backend` → `./backend:/app` mounted, started with `uvicorn --reload` → backend
  code changes hot-reload automatically.
- `frontend` → `./frontend:/app` mounted, started with `npm run dev` (HMR) →
  frontend code changes hot-reload automatically.
- `ollama` → pulled image, no build step.

**When a rebuild IS required (dev stack):**
- `backend/requirements.txt` changed (new Python dependency) → the `pip install`
  layer must be rebuilt.
- `frontend/package.json` / `package-lock.json` changed (new npm dependency) →
  the `npm install` layer must be rebuilt.
- You simply want to force-recreate from current code without trusting hot reload.

| Revision | Command | Notes |
| :--- | :--- | :--- |
| **Backend only** (code) | `docker compose restart backend` | Hot reload already applies it; restart only if reload didn't fire. |
| **Backend only** (new dep in `requirements.txt`) | `docker compose up -d --build backend` | Rebuilds the backend image's pip layer; containers recreated. |
| **Frontend only** (code) | `docker compose restart frontend` | HMR already applies it; restart only if HMR missed it. |
| **Frontend only** (new npm dep) | `docker compose up -d --build frontend` | Rebuilds the `npm install` layer. |
| **Both backend + frontend** (code only) | `docker compose restart` | Graceful restart, no rebuild. |
| **Both backend + frontend** (deps changed) | `docker compose up -d --build` | Full rebuild of both images, then recreates containers. |
| **GPU stack** | `docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build` | Always use the GPU overlay form of any command above. |
| **Production stack** | `docker compose -f docker-compose.prod.yml up -d --build` | Prod image has **no bind mounts** — every backend/frontend revision requires a rebuild. |

> **Why rebuild is often unnecessary in dev:** because source is bind-mounted,
> `docker compose up -d --build` re-copies code into the image but the mount
> shadows it anyway. Only the dependency layers (`pip install` / `npm install`)
> actually differ between rebuilds. After a revision, `git pull` + letting hot
> reload work is the fastest loop; reserve `--build` for dependency changes.

> **If a rebuild appears stuck** at `exporting layers`: the backend image is
> ~10 GB (torch / faster-whisper / sentence-transformers), and exporting those
> layers through Docker Desktop's WSL2 VM takes minutes with no progress output.
> Wait — it is not frozen. Avoid unnecessary rebuilds to skip this cost.

---

## 8. Environment Configuration

- **`.env.example` keeps native defaults** (`./data/...`, `http://localhost:11434`) so
  native (non-Docker) development keeps working.
- Container-specific values (`/app/data/...`, `OLLAMA_BASE_URL=http://ollama:11434`)
  are injected by `docker-compose.yml`'s `environment:` block — do **not** rewrite
  `.env.example` to container paths.
- **Configurable Ollama Timeout**: set `OLLAMA_TIMEOUT=3.0` in `.env` for slower or remote daemon connections.
- **Port collisions**: override `PORT_FRONTEND`, `PORT_BACKEND`, `PORT_OLLAMA` in `.env`.
  If you move the backend port, also update `NEXT_PUBLIC_API_URL` in `docker-compose.yml`.
- **Host Ollama passthrough**: set `OLLAMA_BASE_URL=http://host.docker.internal:11434`
  in `docker-compose.yml` (`host.docker.internal` is wired via `extra_hosts: host-gateway`).

---

## 9. Common Troubleshooting

| Symptom | Cause / Fix |
| :--- | :--- |
| `env file .env not found` | Run `cp .env.example .env` (or a `scripts/setup.*` script) first. |
| Backend stays `unhealthy` | First boot loads models/schema slowly — wait, then check `docker compose logs backend`. |
| Port already in use | Set `PORT_*` overrides in `.env` (Section 8). |
| GPU container fails to start | NVIDIA Container Toolkit not installed/configured — see Section 3; fall back to CPU mode. |
| Chat returns offline-fallback text | Ollama still pulling `llama3:8b` or unreachable — check Ollama status in Settings diagnostic panel or `docker compose logs ollama`. |
| Unmounted host folder error in Docker | Containerized backend cannot reach host drive paths directly. Use live REST discovery (`GET /api/tags`) or mount directory in `docker-compose.yml`. |
| `scripts/dev.ps1` blocked | `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1`, or use compose commands directly. |

---

## 10. Next Steps

- Full deployment documentation: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)
- Architecture context: [`docs/CONTEXT.md`](CONTEXT.md)
- Backend test suite (native): `cd backend && python -m pytest tests`

