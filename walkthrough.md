# Walkthrough — Ollama Containerization Fixes

## Purpose

Two follow-up fixes to the Dockerized development architecture, addressing
recommendations from `docker review.md`:

1. **Portability** — removed the hardcoded `E:\ollama\models` host path from the
   base `docker-compose.yml` so the default stack works on any OS, and moved
   host-model reuse behind an optional, platform-neutral overlay.
2. **Default model pull** — documented and scripted the first-time
   `ollama pull` for the containerized Ollama, which previously started with an
   empty model store.

No application runtime code was changed. All edits are Docker/Compose
configuration, helper scripts, and documentation.

---

## Implementation Summary

### Fix #1 — Portability of the host Ollama bind mount

| File | Change |
| :--- | :--- |
| `docker-compose.yml` | Removed `- E:\ollama\models:/root/.ollama/models` from the `ollama` service. The base file is now fully portable; the `ollama-data` named volume is the canonical model store. |
| `docker-compose.host-models.yml` | **New** overlay that adds an optional bind mount `${OLLAMA_MODELS_DIR:-E:\ollama\models}:/root/.ollama/models` to the `ollama` service. Platform-neutral (Windows/macOS/Linux), combines with the GPU overlay via multiple `-f` flags. |
| `.env.example` | Documented `OLLAMA_MODELS_DIR` (commented out) under the host-ports section. |

**Why an overlay and not a compose variable in the base file**: the base file
must start cleanly with no host-specific state. Keeping the bind in an
opt-in overlay means `docker compose up` works out of the box on any OS, and
users who want to share a host models directory opt in explicitly. This matches
the existing `docker-compose.gpu.yml` overlay pattern.

### Fix #2 — First-time default model pull

| File | Change |
| :--- | :--- |
| `scripts/ollama-pull.sh` | **New** bash helper. Resolves the model as `$1` > `.env` `DEFAULT_LLM_MODEL` > `llama3:8b`; supports `--prod` (targets `athenus-prod-ollama`); errors with guidance if the container isn't running; runs `docker exec -it <container> ollama pull <model>`. |
| `scripts/ollama-pull.ps1` | **New** PowerShell equivalent with identical behavior. |
| `README.md` | Added an "Ollama models (first-time setup)" section after the Quick Start, covering the helper and the host-models overlay. |
| `docs/DEPLOYMENT.md` | Rewrote the "Local Model Storage & Docker Bind Mounts" section; added the pull helper to Common commands and to the Self-Hosted section (`--prod`). |
| `docs/ONBOARDING.md` | Added containerized model-pull to the Web Mode "First-use model downloads" section, an environment-config note for the overlay, and updated the troubleshooting row for offline chat fallback. |

**Design decision — opt-in, not auto-pull**: a multi-GB model download is never
kicked off implicitly. The helper gives a one-liner but the user controls when
the download happens (consistent with the project's local-first philosophy and
with the review's own "optional startup pull helper" recommendation).

---

## Manual Testing & Validation Checklist

Run these in order. Mark each **PASS** / **FAIL** and record failures below.

### 0. Preflight (no running stack)

- [ ] **0.1** `docker compose config --quiet` exits `0` with no warnings.
      (Validates the base file parses without the removed host path.)
- [ ] **0.2** `docker compose -f docker-compose.yml -f docker-compose.host-models.yml config` shows the `ollama` service volume `E:\ollama\models:/root/.ollama/models` (or your `OLLAMA_MODELS_DIR`).
- [ ] **0.3** `docker compose -f docker-compose.prod.yml config --quiet` exits `0`.

### 1. Portable base stack boots cleanly (no host path)

- [ ] **1.1** `./scripts/dev.ps1` (or `./scripts/dev.sh`) brings up all three
      services without errors.
- [ ] **1.2** `docker inspect athenus-ollama --format '{{json .Mounts}}'` shows
      **only** the `ollama-data` volume mounted at `/root/.ollama` (no host
      `models` bind).
- [ ] **1.3** `curl http://localhost:8000/api/v1/health` returns `{"status":"ok",...}`.

### 2. Default model pull (containerized Ollama)

- [ ] **2.1** `docker exec -it athenus-ollama ollama list` shows **no** models
      yet (or a pre-existing set if you've used it before).
- [ ] **2.2** Run `./scripts/ollama-pull.ps1` (or `.sh`). It reports pulling
      `llama3:8b` (or your `DEFAULT_LLM_MODEL`).
- [ ] **2.3** After completion, `docker exec -it athenus-ollama ollama list`
      shows `llama3:8b`.
- [ ] **2.4** `curl http://localhost:11434/api/tags` lists the model in JSON.
- [ ] **2.5** In the Web UI → Settings → AI System Settings, the Ollama provider
      shows `🟢` connected and the model appears in the dropdown (live REST
      discovery via `/api/tags`).
- [ ] **2.6** Send a chat message in a workspace — it should stream a real
      (non-offline-fallback) response.

### 3. Persistence & lifecycle

- [ ] **3.1** `docker compose restart ollama` — model still listed after
      restart (`docker exec ... ollama list`).
- [ ] **3.2** `docker compose down` (NOT `-v`), then `./scripts/dev.ps1` again —
      model still present (survives `down`, only `down -v` deletes it).
- [ ] **3.3** Explicit model arg: `./scripts/ollama-pull.ps1 phi3:mini` pulls a
      different model into the same container.

### 4. Host-models overlay (optional reuse of host Ollama)

- [ ] **4.1** With a host Ollama running and models present, run:
      `docker compose -f docker-compose.yml -f docker-compose.host-models.yml up -d --build`.
- [ ] **4.2** `docker exec -it athenus-ollama ollama list` shows the **host's**
      models (bind mount active).
- [ ] **4.3** Override the dir: set `OLLAMA_MODELS_DIR=<another path>` in `.env`,
      re-run `docker compose -f docker-compose.yml -f docker-compose.host-models.yml up -d`,
      and confirm the new path appears in `docker inspect athenus-ollama`.
- [ ] **4.4** GPU + host-models combined compose (if you have an NVIDIA GPU):
      `docker compose -f docker-compose.yml -f docker-compose.gpu.yml -f docker-compose.host-models.yml config --quiet` exits `0`.

### 5. Production stack

- [ ] **5.1** `docker compose -f docker-compose.prod.yml up -d --build` starts
      cleanly.
- [ ] **5.2** `./scripts/ollama-pull.sh --prod` pulls the model into
      `athenus-prod-ollama` (`docker exec -it athenus-prod-ollama ollama list`).
- [ ] **5.3** `docker compose -f docker-compose.prod.yml down` when finished.

### 6. Negative cases

- [ ] **6.1** `./scripts/ollama-pull.ps1` with the stack stopped prints the
      "not running" error and exits non-zero (no crash / partial pull).
- [ ] **6.2** `docker compose -f docker-compose.yml -f docker-compose.host-models.yml config`
      with `OLLAMA_MODELS_DIR` unset still renders the default `E:\ollama\models`
      bind without a compose error.

---

## Result Log

| Check | Result (PASS/FAIL) | Notes |
| :--- | :---: | :--- |
| 0.1 | | |
| 0.2 | | |
| 0.3 | | |
| 1.1 | | |
| 1.2 | | |
| 1.3 | | |
| 2.1 | | |
| 2.2 | | |
| 2.3 | | |
| 2.4 | | |
| 2.5 | | |
| 2.6 | | |
| 3.1 | | |
| 3.2 | | |
| 3.3 | | |
| 4.1 | | |
| 4.2 | | |
| 4.3 | | |
| 4.4 | | |
| 5.1 | | |
| 5.2 | | |
| 5.3 | | |
| 6.1 | | |
| 6.2 | | |
