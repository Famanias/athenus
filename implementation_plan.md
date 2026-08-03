# Implementation Plan: Dynamically Populate Discovered Local Ollama Models in LLM Provider Settings

Refactor the **Text Generation Provider (LLM)** settings flow to consume dynamically discovered local Ollama models as the single source of truth, removing static hardcoded model strings, setting `selected_ollama_model` to `Optional[str] = None` by default, maintaining model selection state, and gracefully handling missing models.

---

## Technical Architecture & Core Principles

### 1. Single Source of Truth & Dynamic Defaults
- **Discovered Models API (`GET /api/v1/settings/ollama`)**: Serves as the authoritative source for installed local models.
- **Provider Settings API (`GET/PUT /api/v1/settings/providers`)**: Owns provider persistence (`default_llm` and `selected_ollama_model: Optional[str] = None`).
- **Zero Static Defaults**: Removed all hardcoded `"llama3:8b"` fallbacks. `selected_ollama_model` defaults to `None` until explicitly configured by the user.
- **Zero Redundant Store State**: Read and write directly through `settingsService.ts` and component state without adding state to Zustand.

### 2. Selection, Save & Fallback Rules
- **Clean Provider Label**: Provider dropdown displays `Ollama (Local)` (removing static model text).
- **Model Selection UI**: When **Ollama** is selected as the text provider, render a dynamic model `<select>` populated from `ollamaConfig.models`.
- **Model Preservation**: If the currently selected model exists in the scanned model list, preserve it.
- **Explicit Prompting (No Silent Overwrites)**: If the selected model no longer exists in the directory (or none is selected yet), prompt the user: `"-- Select an Ollama model --"`.
- **Unified Save Behavior**: Clicking **Save Configuration** validates provider, validates the selected Ollama model (when active provider is Ollama), persists both in the backend, and displays a success toast.
- **Seamless Provider Restore**: When switching provider back to Ollama, automatically restore the previously saved `selected_ollama_model` if present in discovered models.

---

## Proposed Code Changes

### Backend Subsystem (`backend/app/presentation/api/v1/`)

#### [MODIFY] [settings.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py)
- Initialize `current_settings["selected_ollama_model"] = None`.
- Update `ProviderSettingsDTO` and `ProviderSettingsResponse` to include `selected_ollama_model: Optional[str] = None`.
- Save and validate `selected_ollama_model` in `update_provider_settings()`.

---

### Frontend Subsystem (`frontend/src/`)

#### [MODIFY] [settingsService.ts](file:///e:/repos/athenus/frontend/src/services/settingsService.ts)
- Update `ProviderSettingsDTO` and `ProviderSettingsResponse` to include `selected_ollama_model?: string`.

#### [MODIFY] [SystemSettings.tsx](file:///e:/repos/athenus/frontend/src/features/settings/SystemSettings.tsx)
- Change provider option label from `Ollama (Local - llama3:8b)` to `Ollama (Local)`.
- Render dynamic model selector for Ollama consuming `ollamaConfig.models`.
- Implement selection preservation and prompt fallback (`-- Select an Ollama model --`).
- Save provider and selected model together on **Save Configuration**.

---

## Verification Plan

### Automated Tests
- Update API integration test [`backend/tests/test_ollama_settings_api.py`](file:///e:/repos/athenus/backend/tests/test_ollama_settings_api.py):
  - Test GET/PUT `selected_ollama_model` persistence with `None` default.
- Run backend pytest: `python -m pytest`
- Run frontend type check: `npx tsc --noEmit` (in `frontend/`)

### Manual Verification
1. Open **Settings → AI Models**.
2. Select **Ollama (Local)** $\rightarrow$ Verify active model dropdown renders all discovered models.
3. Save a valid models directory $\rightarrow$ Verify dropdown populates dynamically.
4. Switch provider from **Groq** $\rightarrow$ **Ollama** $\rightarrow$ **Groq** $\rightarrow$ **Ollama** $\rightarrow$ Verify previously selected Ollama model is restored correctly without reselection.
5. Change models directory $\rightarrow$ Click **Refresh** $\rightarrow$ Verify app prompts user to select a model if the previous one is missing.
