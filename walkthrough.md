# Athenus Walkthrough & Change Log

This document records implementation summaries and manual verification steps for changes made to the Athenus codebase.

---

## Change: Docker Config Documentation, `.env.example` Cloud Keys, and Ollama Directory Scanner Deprecation Cleanup

### Summary of Implementation

Context: the provider-agnostic LLM architecture (ADR 0019) deprecated the legacy filesystem Ollama model scanner (`ollama_models_dir` / `OllamaModelScanner`) in favor of 100% native Ollama daemon HTTP discovery (`/api/tags`). This change set cleans up the leftover dead code, documents cloud provider keys, and clarifies production secret injection. No Docker topology changes were required.

#### 1. `.env.example` — document cloud provider keys

Added the missing OpenAI / Anthropic / custom-provider entries so cloud/hybrid mode is discoverable:

- `OPENAI_API_KEY=""`
- `ANTHROPIC_API_KEY=""`
- `CUSTOM_LLM_PROVIDERS=""` (documented JSON shape for arbitrary OpenAI-compatible endpoints)

Field names match `backend/app/core/config.py` exactly (Pydantic `case_sensitive=True`).

#### 2. Frontend — remove dead Ollama-directory code

The `/api/v1/settings/ollama` endpoints were already removed from the backend, but the frontend still called them (resulting in 404s).

- `frontend/src/services/settingsService.ts`: deleted `DiscoveredModelDTO`, `OllamaSettingsResponse`, `getOllamaSettings()`, `updateOllamaDirectory()`, `scanOllamaModels()`.
  - Kept `CatalogModelDTO` / `LocalModelCatalogDTO` and `getLocalProviderStatus` / `getLocalProviderModels` (live daemon endpoints still used by the settings UI).
- `frontend/src/features/settings/SystemSettings.tsx`: removed all dead directory UI code:
  - Unused imports (`getOllamaSettings`, `updateOllamaDirectory`, `scanOllamaModels`, `OllamaSettingsResponse`)
  - `DOCKER_MODE_DIR_ERROR` constant
  - `ollamaDir`, `ollamaConfig`, `ollamaDirError`, `isScanningOllama` state
  - `dirSaveRequestIdRef`, `dirDebounceTimerRef` refs and the `dir` field in `lastSavedRef`
  - `executeDirServerSync`, `handleDirChange`, `handleScanOllamaModels`, `simplifyOllamaDirError` handlers
  - `getOllamaSettings()` hydration block and the `ollamaDir` branch in `handleRetrySave`

#### 3. Backend — remove deprecated scanner + fix stale tests

- Deleted `backend/app/services/ollama_scanner.py` (`OllamaModelScanner`, `DiscoveredModel`) — no longer imported by any router.
- Deleted `backend/tests/test_ollama_scanner.py` (tested the dead scanner).
- Rewrote `backend/tests/test_ollama_settings_api.py` to keep only the valid provider-focused test (`test_provider_settings_selected_ollama_model`); dropped the three directory-scan tests that hit removed endpoints.
- Trimmed `backend/tests/test_settings_persistence.py`: removed the Ollama-directory PUT step and `test_invalid_ollama_directory_preserves_saved_path`; kept provider-persistence assertions (verified against `SettingsService` directly).
- Removed the unused `_setup_ollama_dir` helper from `backend/tests/test_provider_patch_and_catalog.py`.
- **Intentionally kept** the `ollama_models_dir` column in `backend/app/infrastructure/db/models.py` to avoid a schema migration (harmless legacy field).

#### 4. `docs/DEPLOYMENT.md` — production secret injection note

Documented that `docker-compose.prod.yml` does not use `env_file`, so cloud LLM keys are not auto-injected in production; added an example for passing keys explicitly or via `environment:` entries.

### Automated Verification Performed

| Check | Command | Result |
|-------|---------|--------|
| Backend tests | `python -m pytest` (from `backend/`) | 116 passed |
| Frontend type check | `npx tsc --noEmit` (from `frontend/`) | clean |
| Frontend build | `npm run build` (from `frontend/`) | compiled successfully |

Note: `npm run lint` (`next lint`) fails at tool startup on the current Next.js 16.2.12 setup ("Invalid project directory provided") — unrelated to this change set; type-check/build are used instead.

---

### Manual Testing Steps (validated by you)

#### 1. Settings page loads cleanly (no 404s from removed endpoints)

1. Start the backend (`python app/main.py` from `backend/`) and frontend (`npm run dev` from `frontend/`).
2. Open the app → **System Settings** (gear icon).
3. Confirm the page renders without errors and the provider catalog loads:
   - Ollama, OpenRouter, Groq, OpenAI, Anthropic appear as selectable providers (with 🟢/⚪ configuration badges).
4. Open your browser's DevTools → **Network** tab and reload the page.
5. Verify there are **no** requests to `/api/v1/settings/ollama` or `/api/v1/settings/ollama/scan`. All requests should hit `/api/v1/settings/providers`, `/api/v1/settings/providers/catalog`, `/api/v1/settings/providers/local/...`.

#### 2. Provider switching still works (regression check)

1. In System Settings, switch the **Text Generation Provider** between Ollama → Groq → OpenRouter → Ollama.
2. Confirm each switch shows the "Saving..." → "✓ All changes saved" indicators.
3. Confirm the **Active Model Selection** dropdown updates with the selected provider's models.
4. Confirm autosave works after switching (reload the page — your provider selection persists).

#### 3. Test Connection still works

1. With a provider selected, click **🧪 Test Connection**.
2. Confirm a success banner appears for a configured/available provider, or an error banner with a message for an unconfigured one (e.g., Groq with no key → "Key missing" / connection error).

#### 4. Cloud provider keys documented and honored (optional, requires keys)

1. Add `OPENAI_API_KEY` (and optionally `ANTHROPIC_API_KEY`) to your `.env` and restart the backend.
2. In System Settings, the corresponding provider badge should turn 🟢 Configured.
3. Select it as the active provider, pick a model, and send a chat message — confirm responses come from the cloud model.

#### 5. Frontend build is clean

1. From `frontend/`: run `npx tsc --noEmit` (clean) and `npm run build` (compiles successfully).

#### 6. Production secrets (documentation only — no code change)

1. Confirm `docker-compose.prod.yml` was **not** modified (per your decision — no `env_file` injection).
2. Read the new note in `docs/DEPLOYMENT.md` §3 confirming how to pass cloud keys to the prod container manually.
3. (Optional) Validate the compose file still parses: `docker compose -f docker-compose.prod.yml config`.

#### 7. Backend test suite (optional re-run)

1. From `backend/`: `python -m pytest -q` → expect 116 passed, 0 failed.

---

## Change: Single Source of Truth for Provider/Model Selection (per-provider `active_models` map)

### Root Cause

When a different model was chosen from the **Chat** tab's dropdown for a **cloud** provider (OpenAI, Groq, OpenRouter, Anthropic), the selection was ignored and requests kept using the provider's first/default model. The Settings tab worked, but only accidentally.

The defect had several layers:

1. **Backend persisted only ONE model column** — `system_settings.selected_ollama_model` (`backend/app/infrastructure/db/models.py`). There was no representation of an "active model" for cloud providers.
2. **Ollama resolves from the DB at request time** (`_resolve_model()` in `ollama_adapter.py`), so it always honored the persisted selection.
3. **Cloud adapters used only an in-memory `default_model`** (construction default from `.env`, or `set_model()`), and never read the DB at request time (`openai_compatible_adapter.py`, `anthropic_adapter.py`).
4. **The Chat tab dropped the model for cloud providers** — `ModelSwitcher.tsx` sent `selected_ollama_model: undefined` for non-Ollama providers, which `JSON.stringify` removed from the PATCH body, so nothing was persisted and `set_model()` was never called.
5. **The Chat dropdown hardcoded the first model** — `modelValue = activeProvider.models[0].id` for cloud, and `res.active.model` from the catalog was discarded.
6. **The Settings tab worked by abusing `selected_ollama_model`** as a generic "active model" column for all providers; the PATCH handler then called `set_model()` on the active adapter. This was not durable across backend restarts for cloud providers (boot restore in `main.py` only covered Ollama).

### Fix — per-provider `active_models` map as the single source of truth

The SQLite `SystemSettings` record now stores `active_models` (JSON `{provider_id: model_id}`) plus the existing `default_llm`. Both tabs read/write the same fields through one PATCH endpoint and one frontend store field, and every adapter resolves its model from the DB at request time (so selections survive restarts).

#### Backend

- **`backend/app/infrastructure/db/models.py`** — added `active_models` (JSON string) column to `SystemSettings` (both SQLModel and SQLAlchemy branches).
- **`backend/app/infrastructure/db/session.py`** — added an `ALTER TABLE system_settings ADD COLUMN active_models TEXT` migration in `_migrate_db_columns()`.
- **`backend/app/domain/settings/settings_service.py`** —
  - `_parse_active_models()` accepts a dict or a JSON string.
  - `_detach()` decodes the map and backfills the legacy `selected_ollama_model` into `active_models["ollama"]`.
  - `update_settings()` merges `active_models` updates, mirrors `selected_ollama_model` ↔ `active_models["ollama"]`, and stores canonical JSON.
- **`backend/app/presentation/api/v1/settings.py`** —
  - DTOs now carry `selected_model` (convenience: active provider's model) and `active_models`.
  - `PATCH`/`PUT` fold `selected_model` into `active_models[active_provider]`, persist, then call `set_model()` on the affected adapter via `_apply_model_to_adapter()`.
  - `GET` and the catalog endpoint report `selected_model`/`active_models`/`active.model` from the map.
- **`backend/app/infrastructure/adapters/openai_compatible_adapter.py`** — added `_resolve_model()` (reads `active_models[provider_id]`, falls back to `default_model`); used in `generate()`/`stream()`. Also fixed a latent bug where `generate()` used `request.stop_sequences[0]` as the model.
- **`backend/app/infrastructure/adapters/anthropic_adapter.py`** — added `_resolve_model()` and used it in `generate()`/`stream()`.
- **`backend/app/domain/ai/provider_interface.py`** — `BaseLLMProvider.check_health()` now prefers `_resolve_model()` so the catalog's `active.model` reflects DB truth.
- **`backend/app/main.py`** — boot restore now loops over `active_models` and calls `set_model()` on every registered adapter (not just Ollama).

#### Frontend

- **`frontend/src/services/settingsService.ts`** — added `selected_model` / `active_models` to the provider settings DTO/response types.
- **`frontend/src/store/useAppStore.ts`** — renamed `selectedOllamaModel` → `activeModel` (generic active model of the current provider); hydration reads `selected_model ?? selected_ollama_model`; localStorage key is now `athenus_active_model` (legacy key still read for back-compat).
- **`frontend/src/features/chat/ModelSwitcher.tsx`** —
  - `modelValue = activeModel` for **all** providers (no more `models[0]` fallback).
  - Model change PATCHes `{ default_llm, selected_model }` for every provider.
  - Catalog load syncs `activeModel` from `res.active.model`.
- **`frontend/src/features/settings/SystemSettings.tsx`** —
  - Model dropdown reads/writes the generic `activeModel` via `selected_model` (not `selected_ollama_model`).
  - On provider switch the previous provider's model is no longer carried into the new provider (`isProviderChange` guard).
  - Local model state re-syncs from the server response (`patchData.selected_model`) after every autosave.

### Automated Verification Performed

| Check | Command | Result |
|-------|---------|--------|
| Backend tests | `python -m pytest` (from `backend/`) | 120 passed |
| Frontend type check | `npx tsc --noEmit` (from `frontend/`) | clean |
| New regression tests | `backend/tests/test_active_models.py` | 4 passed |

Notes:

- `npm run lint` (`next lint`) remains broken at tool startup on Next.js 16.2.12 — pre-existing, unrelated to this change; `tsc --noEmit` is used instead.
- The `active_models` column is nullable and backfills from `selected_ollama_model`, so existing databases upgrade without a destructive migration.

### Manual Testing Instructions

#### 1. Verify the Chat-tab cloud model bug is fixed (primary scenario)

1. Start the backend (`python app/main.py` from `backend/`) and frontend (`npm run dev` from `frontend/`).
2. Open the app → **Chat** tab. Confirm the top-right **Provider** dropdown and **Model** dropdown appear.
3. Set up a cloud provider (add e.g. `OPENAI_API_KEY` or `GROQ_API_KEY` to `.env` and restart the backend), or use a provider with a large model list such as OpenRouter.
4. From the **Chat** tab, switch **Provider** to the cloud provider, then select a model **that is NOT the first entry** in the Model dropdown.
5. Wait for the "Saved" indicator (Chat tab shows a `⚠` only on error), then send a chat message.
6. **Expected:** the response is generated by the model you selected. Confirm via the provider's dashboard, or by checking the Network request body in DevTools → `chat/completions` (the `model` field must equal your selection).
7. Reload the page (or restart the backend) and verify the Chat-tab Model dropdown **still shows your selection** (previously it reset to the first model).

#### 2. Settings tab ↔ Chat tab synchronization

1. In **System Settings**, switch the Text Generation Provider to a cloud provider and pick a specific model.
2. Go to the **Chat** tab — the Provider and Model dropdowns should show the same provider + model.
3. In the **Chat** tab, change the model again.
4. Return to **System Settings** — the Active Model Selection dropdown should show the same model you picked in Chat.
5. Repeat with **Ollama** as the provider (both directions) to confirm local models still work.

#### 3. Persistence across restart (regression)

1. Select a non-default model for a cloud provider from either tab.
2. Restart the backend process.
3. Open the app — the same provider/model should still be active (previously cloud model selections reverted to the `.env` default after restart).

#### 4. Provider switching does not leak models

1. With Ollama active and model `A` selected, switch the provider to Groq.
2. Confirm Groq's active model is **not** set to `A` (it should stay at its own default or previously saved model).
3. Switch back to Ollama and confirm `A` is still selected (per-provider persistence).
