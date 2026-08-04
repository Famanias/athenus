# ONBOARDING.md

# Athenus — Developer Onboarding Guide

Fresh-clone setup for all three development modes: **Web (Docker)**, **Web (GPU)**, and **Desktop (Tauri)**.

---

## 1. Prerequisites

| Tool | Required for | Notes |
| :--- | :--- | :--- |
| **Git** | Everything | |
| **Docker Desktop** (or Docker Engine + Compose v2) | Web / GPU / containerized backend | Windows: use the **WSL2** backend. |
| **Node.js 20+** | Desktop (Tauri) / native frontend | Only needed for the native Tauri path. |
| **Rust toolchain** | Desktop (Tauri) | Plus platform webview: WebView2 (Windows), WebKitGTK (Linux), WKWebView (macOS). |
| **NVIDIA GPU + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)** | GPU mode only | Optional; skip for CPU. |

No Python install is needed for any Dockerized workflow.

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

### First-use model downloads
- **Ollama**: the backend targets the containerized Ollama (`http://ollama:11434`).
  The first LLM chat auto-pulls the default model (`llama3:8b`, several GB — takes minutes).
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

## 5. Sanity Checks After First Boot

```bash
docker compose ps                        # backend should report "healthy"
curl http://localhost:8000/api/v1/health  # {"status":"ok",...}
curl -I http://localhost:3000             # HTTP 200
docker compose logs -f backend            # follow ingestion/transcription progress
```

### Stopping / resetting

```bash
docker compose down         # stop; keeps ./data and model volumes
docker compose down -v      # stop AND delete named volumes (models re-download)
```

---

## 6. Environment Configuration

- **`.env.example` keeps native defaults** (`./data/...`, `http://localhost:11434`) so
  native (non-Docker) development keeps working.
- Container-specific values (`/app/data/...`, `OLLAMA_BASE_URL=http://ollama:11434`)
  are injected by `docker-compose.yml`'s `environment:` block — do **not** rewrite
  `.env.example` to container paths.
- **Port collisions**: override `PORT_FRONTEND`, `PORT_BACKEND`, `PORT_OLLAMA` in `.env`.
  If you move the backend port, also update `NEXT_PUBLIC_API_URL` in `docker-compose.yml`.
- **Host Ollama passthrough**: set `OLLAMA_BASE_URL=http://host.docker.internal:11434`
  in `docker-compose.yml` (`host.docker.internal` is wired via `extra_hosts: host-gateway`).

---

## 7. Common Troubleshooting

| Symptom | Cause / Fix |
| :--- | :--- |
| `env file .env not found` | Run `cp .env.example .env` (or a `scripts/setup.*` script) first. |
| Backend stays `unhealthy` | First boot loads models/schema slowly — wait, then check `docker compose logs backend`. |
| Port already in use | Set `PORT_*` overrides in `.env` (Section 6). |
| GPU container fails to start | NVIDIA Container Toolkit not installed/configured — see Section 3; fall back to CPU mode. |
| Chat returns offline-fallback text | Ollama still pulling `llama3:8b` or unreachable — check `docker compose logs ollama`. |
| `scripts/dev.ps1` blocked | `powershell -ExecutionPolicy Bypass -File scripts/dev.ps1`, or use compose commands directly. |

---

## 8. Next Steps

- Full deployment documentation: [`docs/DEPLOYMENT.md`](DEPLOYMENT.md)
- Architecture context: [`docs/CONTEXT.md`](CONTEXT.md)
- Implementation plan (Dockerization source): [`implementation_plan.md`](../implementation_plan.md)
- Backend test suite (native): `cd backend && python -m pytest tests`
