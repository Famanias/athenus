# Final Plan: Model Switcher in Chat Header

## Backend

**B1. PATCH `/api/v1/settings/providers`** — `backend/app/presentation/api/v1/settings.py`
*   All-optional DTO; merge with existing record via `payload.model_dump(exclude_unset=True)`.
*   Never touches `_transient_api_key` unless `api_key` is explicitly sent.
*   Returns full merged `ProviderSettingsResponse`. `PUT` stays for full saves.

**B2. GET `/api/v1/settings/providers/catalog`** — `settings.py`
*   Returns `{ active: {provider, model}, providers: [{id, label, models:[{id}]}] }`.
*   Ollama models from existing scanner; cloud model defaults centralized in `app/core/config.py` (`GROQ_DEFAULT_MODEL`, `OPENROUTER_DEFAULT_MODEL`) and reused by `main.py` (single source of truth).
*   `active.model` enables stale-model detection.

**B3. Adapter resolution** — `backend/app/infrastructure/adapters/ollama_adapter.py`
*   Constructor takes `settings_service: SettingsService = None` (defaults to the existing singleton; injected once, test-swappable).
*   `generate()`/`stream()` resolve `selected_ollama_model` or `default_model`, keeping the fallback loop.
*   Provider routing stays dynamic via `service_bus.py:26`.

**B4. Tests** — `backend/tests/`
*   `PATCH` preserves `api_key` and merges partial fields.
*   Catalog returns active + per-provider models.
*   Adapter uses `selected_ollama_model` from an injected fake settings service.

---

## Frontend

**F1. Store** — `frontend/src/store/useAppStore.ts`
*   Add `selectedOllamaModel: string`; extend `setProviderSettings(llm, stt, gpu, ollamaModel?)`; hydrate from `getProviderSettings()` in `rehydrateStoredState()`. No model lists in global state.

**F2. Services** — `frontend/src/services/settingsService.ts`
*   Add `patchProviderSettings(payload)` and `getProviderCatalog()` + DTO types.

**F3. `frontend/src/features/chat/ModelSwitcher.tsx` (new)**
*   Two compact dropdowns (provider + model) in the header, styled like the current badge.
*   Data-driven from `getProviderCatalog()` (local state).
*   Provider change → `patchProviderSettings({ default_llm })`; model change → `patchProviderSettings({ default_llm, selected_ollama_model })`.
*   Ollama model auto-restores on return to Ollama (backend persists it); stale model → warning + prompt to re-select; loading/empty/error states.

**F4. `frontend/src/features/chat/ChatWorkspace.tsx`**
*   Replace the hardcoded `Local LLM: llama3:8b` badge (lines 53-55) with `<ModelSwitcher/>`.

**F5. `frontend/src/features/settings/SystemSettings.tsx` (migrate)**
*   Provider options and the "Active Ollama Local Model" dropdown come from the catalog instead of hardcoded values/`getOllamaSettings()`.
*   Save uses `PATCH` (all fields incl. `api_key`, intentionally edited here); syncs store with `selectedOllamaModel` after save.
*   "Model Sources" directory/scan/refresh section stays on `/settings/ollama` endpoints (unchanged).

---

## Verification

**Backend:**
```bash
cd backend
python -m pytest tests
```

**Frontend:**
```bash
npm run lint
npm run build # in frontend/
```

**Manual Matrix:**

| Scenario | Expected |
| :--- | :--- |
| Switch Ollama model | Next answer uses new model |
| Groq → Ollama | Prior Ollama model auto-restored |
| Ollama → Groq → Ollama | Selection persists |
| Restart app | Provider + model restored from SQLite |
| Selected model removed from disk | UI warns, prompts valid selection |
| Multiple workspaces/chats | Global switch applies everywhere |
| `PATCH` without `api_key` | API key preserved server-side |

> **Note:** No new dependencies; native `<select>` elements matching the existing design system.