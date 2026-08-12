# Athenus CI Pipeline Implementation

Implement `.github/workflows/ci.yml` with three independent jobs (frontend, backend, tauri), stabilize the backend test baseline to 146/146, and add a `typecheck` script to `frontend/package.json`. No CD, no application behavior changes.

## User Review Required

> [!IMPORTANT]
> **Decisions confirmed:**
> - **Frontend lint:** Omit from Phase 1 (Option A). Typecheck + build only.
> - **Backend test stabilization:** Approved. Fix 3 failing tests + mock HuggingFace embedding. All test-only changes.
> - **MOUNTAIN model thread:** Parked — user will bring it up when ready.

> [!WARNING]
> **Environment limitation:** This Windows machine has no Node/npm installed. Frontend and Tauri validation can only be confirmed by a GitHub Actions run. Backend tests will be validated locally via the existing Python 3.11 venv.

## Proposed Changes

### CI Workflow

#### [NEW] [ci.yml](file:///e:/repos/athenus/.github/workflows/ci.yml)

Three independent jobs on `ubuntu-latest`, triggered on `push`/`pull_request` to `main`+`v1` plus `workflow_dispatch`:

| Job | Working Dir | Steps |
|---|---|---|
| **frontend** | `frontend/` | Checkout → Node 22 (npm cache) → `npm ci` → `npm run typecheck` → `npm run build` |
| **backend** | `backend/` | Checkout → Python 3.11 (pip cache) → pip install → `mkdir -p data` → `python -m pytest tests` |
| **tauri** | `frontend/` | Checkout → Node 22 → Rust stable + cargo cache → Tauri v1 apt deps (`libwebkit2gtk-4.0-dev`) → `npm ci` → `npm run tauri build -- --bundles deb` |

Concurrency: `ci-${{ github.workflow }}-${{ github.ref }}` with `cancel-in-progress: true`.

No `continue-on-error`, no `|| true`, no secrets.

---

### Frontend Infrastructure

#### [MODIFY] [package.json](file:///e:/repos/athenus/frontend/package.json)

Add `"typecheck": "tsc --noEmit"` to the `scripts` block. This matches the existing repo convention (`walkthrough.md` uses `npx tsc --noEmit` throughout). No dependency changes — `typescript` is already in `devDependencies`.

The broken `"lint": "next lint"` script is left as-is (lint is deferred to Phase 2).

---

### Backend Test Stabilization (test-only changes)

#### [MODIFY] [test_ollama_provider_adapter.py](file:///e:/repos/athenus/backend/tests/test_ollama_provider_adapter.py)

**Fix `test_ollama_text_gen_adapter_raises_on_failure`:** Currently only mocks `httpx.AsyncClient.post` but the adapter's `generate()` method iterates over multiple base URLs and makes real HTTP `POST` calls to each. The mock needs to cover all `httpx.AsyncClient` network calls. Since `generate()` uses `client.post()` (which already raises `ConnectError` via the mock), the real issue is that the test expects `RuntimeError` but the adapter raises `ValueError`. Fix: update the assertion to match the actual exception type (`ValueError`), or also mock `get` to prevent any unmocked network call.

After re-reading the adapter code more carefully: `generate()` at line 136-192 only uses `client.post()` — there is no `GET` call inside `generate()`. The `post` mock already raises `ConnectError`. The adapter catches `Exception` at line 183, sets `last_err_msg`, and continues. After exhausting all URLs, it raises `ValueError(err_msg)` at line 189. But the test asserts `pytest.raises(RuntimeError)` and checks for `"Ollama generation failed"` — that string isn't in the error message either.

**Corrected fix:** Change the test to expect `ValueError` and match the actual error string pattern.

#### [MODIFY] [test_retrieval_rag.py](file:///e:/repos/athenus/backend/tests/test_retrieval_rag.py)

**Fix `test_chat_query_endpoint`:** This test hits the real `/api/v1/chat/query` endpoint via `TestClient(app)`. The endpoint calls `manager.query_workspace()`, which invokes `retriever.execute_retrieval()` (needs embeddings) and `text_capability.generate()` (needs LLM). Both fail in a bare environment.

**Fix:** Mock the `get_intelligence_manager` dependency to return a `WorkspaceIntelligenceManager` wired with `MockOllamaAdapter` (already defined in the file) and a mock embedding adapter. Use FastAPI's `app.dependency_overrides`.

**Fix `test_workspace_intelligence_manager`:** Currently instantiates real `SentenceTransformersEmbeddingAdapter()` which downloads `BAAI/bge-small-en-v1.5` (~100 MB) on a clean runner. Mock it by using a simple mock embedding adapter that returns 384-dim vectors.

#### [MODIFY] [test_sessions.py](file:///e:/repos/athenus/backend/tests/test_sessions.py)

**Fix `test_session_lifecycle_and_lazy_creation`:** Steps 4 and 6 call `/api/v1/chat/query` which hits the real LLM. Same root cause as `test_chat_query_endpoint`.

**Fix:** Override `get_intelligence_manager` with a mocked manager using `app.dependency_overrides`, same pattern. Add cleanup (restore overrides) in a fixture or at test end.

---

### Documentation

#### [MODIFY] [walkthrough.md](file:///e:/repos/athenus/walkthrough.md)

Append a new phase section for the CI pipeline following the existing per-phase structure (Phase Summary, What Was Implemented, Files Changed, Implementation Decisions, Automated Tests, Manual QA, Validation Status).

---

## Verification Plan

### Automated Tests

```bash
# Backend (local, from backend/):
cd backend && python -m pytest tests -v
# Expected: 146/146 pass

# CI workflow YAML validation:
# actionlint or yamllint against .github/workflows/ci.yml
```

### Manual Verification

| Check | Method |
|---|---|
| Backend tests: 146/146 pass | Run locally via Python 3.11 venv |
| `ci.yml` valid YAML | Parse with a YAML linter |
| Frontend typecheck/build | Can only verify via GitHub Actions (no Node locally) |
| Tauri build | Can only verify via GitHub Actions (Linux-only apt deps) |
| Workflow triggers | Push to `v1` branch and observe GitHub Actions |
