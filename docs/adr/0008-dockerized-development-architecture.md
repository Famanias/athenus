# ADR 0008: Dockerized Development Architecture

## Context
Athenus ships as both a **Web Application (Next.js)** and a **Desktop Application (Tauri)**, both powered by a single **FastAPI Python backend**. Onboarding a web developer required manually installing Python 3.11, ffmpeg, Node.js, PyTorch/CTranslate2 model dependencies, and an Ollama service before the stack could run. There was no reproducible way to stand up the backend, frontend, and local LLM with a single command, and GPU-accelerated local inference (Faster-Whisper via CTranslate2, Ollama GGUF) lacked a documented enablement path.

## Decision
Adopt a **Dockerized Development Architecture** that is a superset of the existing native workflow:

1. **Containerize the web stack** (`docker-compose.yml`):
   - `backend` — FastAPI (Uvicorn `--reload`) with ffmpeg; bind-mounted `./backend` for hot reload.
   - `frontend` — Next.js dev server (HMR); bind-mounted `./frontend` with anonymous `node_modules`/`.next` volumes.
   - `ollama` — containerized local LLM on `:11434`.
   - Shared bridge network `athenus-net`, `extra_hosts: host-gateway` for `host.docker.internal`, and healthchecks.
2. **Keep the Tauri desktop shell native on the host** and let it talk to the containerized backend over `http://localhost:8000`, sharing `./data/` (SQLite + Qdrant + uploads) via host bind mount.
3. **GPU acceleration via an overlay compose file** (`docker-compose.gpu.yml`) instead of the `--profile gpu` design in the original plan, which would have started CPU and GPU service variants simultaneously and collided on published ports (8000/11434). The overlay upgrades the existing `backend`/`ollama` services with a CUDA-enabled image and NVIDIA `device_requests`.
4. **Single `.env` for two runtimes**: `.env.example` keeps **native** defaults (`./data/...`, `http://localhost:11434`); container-specific paths (`/app/data/...`, `OLLAMA_BASE_URL=http://ollama:11434`) are injected via compose `environment:` blocks so native development keeps working unchanged.
5. **GPU-capable backend configuration**: added `WHISPER_DEVICE` and `WHISPER_COMPUTE_TYPE` settings consumed by `FasterWhisperSTTAdapter` (previously hardcoded to `cpu`/`int8`).
6. **Production**: `docker-compose.prod.yml` builds multi-stage images — backend (non-root, `--workers 1` because embedded SQLite/Qdrant are single-process file stores) and frontend static export served by nginx (the static export is required by Tauri's `distDir: ../out`).

## Status
Accepted and Implemented.

## Rationale
- **Single-Command Onboarding**: `docker compose up -d --build` → `http://localhost:3000` with zero manual Python/Node/ffmpeg installs.
- **Parity & Efficiency**: Development containers mirror production runtimes while source bind mounts preserve hot reloading.
- **Hardware Flexibility**: CPU by default, GPU via one extra flag/overlay, no duplicated services.
- **Non-Breaking**: Existing native commands (`python app/main.py`, `npm run tauri dev`, `python -m pytest tests`) remain fully functional.

## Trade-offs
- The GPU overlay file is required (a bare `--profile gpu` flag does not activate GPU mode) — a deliberate deviation from the plan's original CLI shape.
- CUDA image size is large (CUDA-enabled torch + CUDA 12 runtime wheels for CTranslate2); mitigated by Docker layer caching and the `hf-cache`/`ollama-data` named volumes.
- `host.docker.internal` requires `extra_hosts: host-gateway` on Linux for host-Ollama passthrough.
- SQLite shared-file access between the desktop shell and containers relies on WAL mode and single-writer usage.

## References
- [`docker-compose.yml`](../../docker-compose.yml), [`docker-compose.gpu.yml`](../../docker-compose.gpu.yml), [`docker-compose.prod.yml`](../../docker-compose.prod.yml)
- [`docker/backend/`](../../docker/backend/), [`docker/frontend/`](../../docker/frontend/)
- [`docs/DEPLOYMENT.md`](../DEPLOYMENT.md), [`docs/ONBOARDING.md`](../ONBOARDING.md)
