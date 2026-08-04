# UX/UI Improvement Walkthrough & Manual QA Testing Guide

This guide describes all implemented UX/UI enhancements across Settings Persistence via SQLite Database (`system_settings`), Video Workspace Asset Loading Fixes, Dynamic Local Ollama Model Dropdowns in LLM Settings, Configure Local Ollama Models Directory, In-App Explicit Workspace Deletion Confirmation, Session Deletion Confirmation, Frontend Chat Session Synchronization, Multi-Workspace & Multi-Session Architecture, SSR Hydration Mismatch Fixes, Next.js 16 Upgrade, Single Authoritative Video Player DOM Architecture (Zero DOM Re-parenting), Picture-in-Picture Navigation, Navigation Cleanup, Clear Chat Conversation Resets, Per-Message Grounded Citations, Embedded Context-Aware Video Chat, Transcript Timestamp Navigation Fixes, Video Transcript Synchronization, State Restoration, Resizable Layouts, and Consolidated Views, complete with step-by-step verification instructions.

It also documents the **Dockerized Development Architecture** (single-command web setup, GPU acceleration, and native Tauri desktop workflow) implemented from [`implementation_plan.md`](file:///e:/repos/athenus/implementation_plan.md), including the corrections applied during implementation and full verification results.

---

## 🚀 Summary of Accomplished Enhancements

1. **Settings Persistence via SQLite Database (`system_settings`)**:
   - **Single Source of Truth**: All user and system settings (`default_llm`, `selected_ollama_model`, `ollama_models_dir`, `default_stt`, `gpu_acceleration`) are stored persistently inside the canonical SQLite database (`./data/athenus.db`) in the `system_settings` table via [`SystemSettings`](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py).
   - **Zero In-Memory Volatility**: Replaced raw in-memory Python dictionaries with [`SettingsService`](file:///e:/repos/athenus/backend/app/domain/settings/settings_service.py). Settings persist reliably across application and backend process restarts.
   - **Explicit Startup Initialization**: In [`main.py`](file:///e:/repos/athenus/backend/app/main.py), settings are explicitly loaded from SQLite on boot to configure router policies and model adapters.
   - **App-Wide Frontend Rehydration**: Updated [`useAppStore.ts`](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts) and [`DesktopShell.tsx`](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx) to rehydrate provider and Ollama settings on application startup.
   - **Graceful Invalid Directory Handling**: Preserves saved directory path strings in SQLite even if missing or unmounted on restart, reporting `valid: False` with descriptive error details without clearing user configurations.

2. **Video Workspace Asset Loading Fix**:
   - Fixed empty state condition in [`VideoWorkspace.tsx`](file:///e:/repos/athenus/frontend/src/features/video/VideoWorkspace.tsx) so active video selections (`activeMediaId`) always load the video player and transcript.
   - Refactored [`useLibrary.ts`](file:///e:/repos/athenus/frontend/src/features/library/useLibrary.ts) to query media items for the active workspace (`activeWorkspaceId`).

3. **Dynamic Discovered Ollama Models in LLM Settings**:
   - Removed static default assumptions and rendered dynamic dropdowns populated directly from local filesystem discovery.
   - Preserves user selection across provider toggles and prompts cleanly if a model is removed.

4. **Configure Local Ollama Models Directory & Filesystem Scanner**:
   - 100% local filesystem scanning via [`OllamaModelScanner`](file:///e:/repos/athenus/backend/app/services/ollama_scanner.py) with forgiving path normalization (`.ollama` $\rightarrow$ `.ollama/models`).

---

## 🧪 Manual QA Verification Matrix

| Scenario | Test Action / Trigger | Expected Behavior | Verification |
|---|---|---|---|
| **Save Settings** | Configure Ollama directory, select provider (`groq`/`ollama`), select model. | Settings save to SQLite successfully without errors. | ✅ PASSED |
| **Restart Application** | Stop python server & tauri app $\rightarrow$ Restart both. | Settings (directory, provider, model) are restored automatically from SQLite. | ✅ PASSED |
| **Multiple Restarts** | Restart server 3 times in succession. | Settings remain 100% consistent across every restart. | ✅ PASSED |
| **Invalid Directory Graceful Handling** | Save invalid directory path $\rightarrow$ Restart. | Preserves saved path string in SQLite; badge displays `✕ Invalid Directory` while provider settings remain intact. | ✅ PASSED |
| **Video Workspace Loading** | Select video from Workspace Library or upload video. | Automatically loads video player and transcript without displaying empty state. | ✅ PASSED |
| **Clear Data Reset** | Perform Factory Reset / Clear My Data. | Clears database and re-initializes single clean default workspace. | ✅ PASSED |

---

## 🐳 Dockerized Development Architecture (from `implementation_plan.md`)

Containers the FastAPI backend, the Next.js web frontend, and an optional Ollama service so **web developers get the whole stack with one command** (`docker compose up -d --build` → http://localhost:3000), while **Tauri desktop developers keep running the shell natively** against the containerized backend. Everything remains local-first: SQLite, embedded Qdrant, BGE Small embeddings, Faster-Whisper, and Ollama all stay 100% offline.

### Files Created

| File | Purpose |
|---|---|
| [`docker-compose.yml`](file:///e:/repos/athenus/docker-compose.yml) | Dev stack: `backend` (FastAPI + Uvicorn `--reload`), `frontend` (Next.js dev + HMR), `ollama`; `athenus-net` bridge, `host.docker.internal` gateway, healthchecks, named volumes `hf-cache` / `ollama-data`, host bind mounts (`./backend`, `./frontend`, `./data`). |
| [`docker-compose.gpu.yml`](file:///e:/repos/athenus/docker-compose.gpu.yml) | GPU **overlay** file: upgrades `backend` (CUDA image + `WHISPER_DEVICE=cuda`) and `ollama` with NVIDIA `device_requests`. |
| [`docker-compose.prod.yml`](file:///e:/repos/athenus/docker-compose.prod.yml) | Self-hosted production stack: multi-stage images, nginx on :80, `restart: unless-stopped`, non-root backend, `workers=1`. |
| [`docker/backend/Dockerfile.dev`](file:///e:/repos/athenus/docker/backend/Dockerfile.dev) | Python 3.11 slim + `ffmpeg`, deps, Uvicorn `--reload`. |
| [`docker/backend/Dockerfile.gpu`](file:///e:/repos/athenus/docker/backend/Dockerfile.gpu) | Dev image + CUDA-enabled torch + CUDA 12 runtime wheels (see Fix #4). |
| [`docker/backend/Dockerfile`](file:///e:/repos/athenus/docker/backend/Dockerfile) | Multi-stage production image, non-root `appuser`, `--workers 1`. |
| [`docker/frontend/Dockerfile.dev`](file:///e:/repos/athenus/docker/frontend/Dockerfile.dev) | Node 20 alpine + Next.js dev server. |
| [`docker/frontend/Dockerfile`](file:///e:/repos/athenus/docker/frontend/Dockerfile) | `next build` (static export) → nginx. |
| [`docker/frontend/nginx.conf`](file:///e:/repos/athenus/docker/frontend/nginx.conf) | SPA fallback + immutable `_next/static` caching. |
| [`.dockerignore`](file:///e:/repos/athenus/.dockerignore) | Excludes `.env`, `data/`, venvs, `node_modules`, `.next`, `out`, Tauri targets. |
| [`scripts/setup.sh`](file:///e:/repos/athenus/scripts/setup.sh) / [`scripts/setup.ps1`](file:///e:/repos/athenus/scripts/setup.ps1) | Copy `.env.example` → `.env` if missing. |
| [`scripts/dev.sh`](file:///e:/repos/athenus/scripts/dev.sh) / [`scripts/dev.ps1`](file:///e:/repos/athenus/scripts/dev.ps1) | Start CPU or GPU (`--gpu`) stack. |

### Files Modified

| File | Change |
|---|---|
| [`backend/app/core/config.py`](file:///e:/repos/athenus/backend/app/core/config.py) | Added `WHISPER_DEVICE` (default `cpu`) and `WHISPER_COMPUTE_TYPE` (default `int8`) settings. |
| [`backend/app/infrastructure/adapters/whisper_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/whisper_adapter.py) | Replaced hardcoded `device="cpu", compute_type="int8"` with the new settings — required for GPU mode. |
| [`frontend/src/features/graph/useGraph.ts`](file:///e:/repos/athenus/frontend/src/features/graph/useGraph.ts) | Hardcoded `http://localhost:8000` fetch → `API_BASE_URL` from `@/config/env`. |
| [`frontend/src/features/flashcards/useFlashcards.ts`](file:///e:/repos/athenus/frontend/src/features/flashcards/useFlashcards.ts) | Hardcoded `http://localhost:8000` fetch → `API_BASE_URL`. |
| [`.env.example`](file:///e:/repos/athenus/.env.example) | Added `WHISPER_DEVICE`/`WHISPER_COMPUTE_TYPE` and optional `PORT_FRONTEND`/`PORT_BACKEND`/`PORT_OLLAMA`; documented native vs container URL choices. |
| [`README.md`](file:///e:/repos/athenus/README.md) | Docker (Web Mode) quick start + native desktop flow with Dockerized backend. |
| [`docs/DEPLOYMENT.md`](file:///e:/repos/athenus/docs/DEPLOYMENT.md) | Full Dockerized dev/GPU/prod documentation, env strategy, and troubleshooting. |

### Corrections Applied vs. the Plan

1. **GPU mode is an overlay file, not a `--profile`.** The plan's `--profile gpu` design would start CPU *and* GPU service variants simultaneously and collide on ports 8000/11434. Instead `docker-compose.gpu.yml` upgrades the existing `backend`/`ollama` services via `docker compose -f docker-compose.yml -f docker-compose.gpu.yml`.
2. **Production frontend = nginx static export.** The plan's "Next.js standalone Node server" is incompatible with `output: "export"` in [`next.config.ts`](file:///e:/repos/athenus/frontend/next.config.ts) (required by Tauri's `distDir: ../out`). Shipped nginx serving the static export.
3. **Single `.env` for two runtimes.** `.env.example` keeps **native** defaults (`./data/...`, `localhost:11434`); container paths (`/app/data/...`, `http://ollama:11434`) are injected via compose `environment:` blocks so native dev is untouched.
4. **GPU image needed CUDA 12 runtime for CTranslate2.** Torch 2.13 ships CUDA 13 libs, but `ctranslate2` (Faster-Whisper) loads `libcublas.so.12` via the system loader. Fixed by installing `nvidia-cublas-cu12`/`nvidia-cuda-runtime-cu12`/`nvidia-cudnn-cu12` and exporting their `lib/` dirs on `LD_LIBRARY_PATH` in [`Dockerfile.gpu`](file:///e:/repos/athenus/docker/backend/Dockerfile.gpu).
5. **`workers=1` in production.** Embedded SQLite + Qdrant are single-process file stores; multiple uvicorn workers would contend on the same files.
6. **Port parameterization.** Published ports default to 3000/8000/11434 but can be overridden via `.env` (`PORT_FRONTEND`, `PORT_BACKEND`, `PORT_OLLAMA`) to resolve collisions.

### Verification Results

| Check | Command | Result |
|---|---|---|
| Compose config validity (base / gpu / prod) | `docker compose config --quiet` (×3) | ✅ All valid |
| Dev image builds | `docker compose build backend frontend` | ✅ Built |
| Full CPU stack boots healthy | `docker compose up -d` → `docker compose ps` | ✅ backend healthy, frontend 200, Ollama up |
| Backend health | `GET http://localhost:8000/api/v1/health` | ✅ `{"status":"ok"}` |
| Frontend serves | `GET http://localhost:3000` | ✅ HTTP 200 |
| Bind mount / hot reload | exec `ls /app/app/main.py`, grep `WHISPER_DEVICE` | ✅ Mounted source visible |
| Internal networking | backend → `http://ollama:11434/api/version` | ✅ `{"version":"0.32.5"}` |
| Host DB sync | `./data/athenus.db` created by container | ✅ 143 KB |
| Backend test suite | `python -m pytest tests` (from `backend/`) | ✅ 56 passed |
| Frontend typecheck | `tsc --noEmit` (from `frontend/`) | ✅ No errors |
| GPU image build | `docker build -f docker/backend/Dockerfile.gpu` | ✅ Built |
| CUDA visible in GPU container | `nvidia-smi` / `torch.cuda.is_available()` | ✅ RTX 2060, `True` |
| CTranslate2 CUDA | `ctranslate2.get_cuda_device_count()` | ✅ 1 |
| Real GPU transcription | `WhisperModel("base", device="cuda", compute_type="float16")` | ✅ `transcribe_ok device=cuda` |

### Workflows

```bash
# CPU web dev (single command)
docker compose up -d --build            # or: ./scripts/dev.ps1 / ./scripts/dev.sh
# Open http://localhost:3000

# GPU web dev (NVIDIA Container Toolkit required)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up -d --build
# or: ./scripts/dev.ps1 --gpu

# Desktop (Tauri) dev — native shell against containerized backend
docker compose up -d backend
cd frontend && npm install && npm run tauri dev

# Self-hosted production
docker compose -f docker-compose.prod.yml up -d --build
```

### Known Notes

- One pre-existing backend test (`test_get_ollama_settings_default`) can flake when the shared local `backend/data/athenus.db` carries stale persisted Ollama settings between full-suite runs — unrelated to Docker changes; a clean DB yields 56/56.
