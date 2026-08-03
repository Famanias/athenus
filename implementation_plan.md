# Implementation Plan: Configure Local Ollama Models Directory

Allow users to configure their local Ollama models directory, auto-normalize parent or subfolder paths (`.ollama`, `.ollama/models`, `manifests`), scan installed models using a 100% filesystem-based scanner, display both configured and resolved paths, and render models under a **Model Sources → Available Local Models** settings UI.

---

## Technical Architecture & Refinement Summary

### 1. Pure Filesystem Model Scanner (`backend/app/services/ollama_scanner.py`)
- **Decoupled Domain Service**: Operates strictly on local filesystem paths with zero daemon or HTTP network calls.
- **Forgiving Path Normalization**:
  - Automatically resolves selected directory if user selects `.ollama`, `.ollama/models`, or `.ollama/models/manifests`.
- **Domain Exceptions**:
  - `DirectoryNotFoundError`: Path does not exist on disk.
  - `InvalidOllamaDirectoryError`: Directory is missing standard `manifests` or `blobs` structure.
- **Discovered Model Metadata**:
  - `full_id`: e.g. `"llama3:8b"`
  - `model_name`: e.g. `"llama3"`
  - `tag`: e.g. `"8b"`
  - `provider`: `"ollama"`
  - `size_bytes`: Optional[int]
  - *(Note: `manifest_path` is kept strictly backend-internal and omitted from API DTOs)*

---

### 2. Streamlined API & Persistence (`backend/app/presentation/api/v1/settings.py`)
- **Existing Settings Persistence**: Configured `ollama_models_dir` is saved using the application's existing provider settings state in `settings.py`.
- **API Endpoints**:
  - `GET /api/v1/settings/ollama`: Returns `{ configured_dir: str, resolved_dir: str, valid: bool, models_count: int, models: List[DiscoveredModelDTO] }`.
  - `PUT /api/v1/settings/ollama`: Accepts `{ models_dir: str }`. Normalizes path, validates, persists, and **automatically rescans** model inventory.
  - `POST /api/v1/settings/ollama/scan`: Rescans the currently configured directory on demand (for the **Refresh** button).

---

### 3. Frontend Settings UI (`frontend/src/`)
- Add DTOs to `settingsService.ts`:
  - `DiscoveredModelDTO`: `{ full_id: str, model_name: str, tag: str, provider: string, size_bytes?: number }`
  - `OllamaSettingsResponse`: `{ configured_dir: string, resolved_dir: string, valid: boolean, models_count: number, models: DiscoveredModelDTO[] }`
- **Model Sources UI in `SystemSettings.tsx`**:
  - Section title: **Model Sources**
  - Card: **Local Ollama Models**
    - Path input field for manual path pasting.
    - **Browse** button (integrating Tauri folder picker with text paste fallback).
    - **Save** button (validates, persists, rescans, and updates UI).
    - **Refresh** button (rescans configured directory on demand).
    - Status badge: `✓ Valid (12 models discovered)` or `✕ Invalid Directory`.
    - Path metadata: Shows both **Configured Directory** and **Resolved Directory** paths.
  - **Available Local Models**: Displays discovered models grid with model name, tag badges, and a clean empty state when no models exist in directory.

---

## Proposed Code Changes

### [NEW] [ollama_scanner.py](file:///e:/repos/athenus/backend/app/services/ollama_scanner.py)
- Domain exceptions `DirectoryNotFoundError`, `InvalidOllamaDirectoryError`.
- `DiscoveredModel` domain class.
- `OllamaModelScanner` with path normalization (`.ollama`, `models`, `manifests`) and `scan()`.

### [MODIFY] [settings.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py)
- Integrate `OllamaModelScanner` and expose `GET`, `PUT`, `POST` `/settings/ollama` endpoints.
- Map domain exceptions to clean HTTP 400 / 404 responses.

### [MODIFY] [settingsService.ts](file:///e:/repos/athenus/frontend/src/services/settingsService.ts)
- Add `getOllamaSettings()`, `updateOllamaDirectory()`, and `scanOllamaModels()`.

### [MODIFY] [SystemSettings.tsx](file:///e:/repos/athenus/frontend/src/features/settings/SystemSettings.tsx)
- Render **Model Sources → Local Ollama Models** and **Available Local Models** section.

---

## Verification Plan

### Automated Tests
- Create unit test [`backend/tests/test_ollama_scanner.py`](file:///e:/repos/athenus/backend/tests/test_ollama_scanner.py):
  - Non-existent path $\rightarrow$ raises `DirectoryNotFoundError`.
  - Invalid path missing `manifests/blobs` $\rightarrow$ raises `InvalidOllamaDirectoryError`.
  - Path normalization: `.ollama` or `.ollama/models` or `.ollama/models/manifests` $\rightarrow$ resolves cleanly to `models` folder.
  - Manifest scanning $\rightarrow$ extracts `llama3:8b`, `mistral:latest` without exposing raw filesystem paths.
- Create API integration test [`backend/tests/test_ollama_settings_api.py`](file:///e:/repos/athenus/backend/tests/test_ollama_settings_api.py):
  - Test `GET /settings/ollama`, `PUT /settings/ollama`, and `POST /settings/ollama/scan`.
- Run backend pytest: `python -m pytest`
- Run frontend type check: `npx tsc --noEmit` (in `frontend/`)

### Manual Verification
1. Open **Settings** $\rightarrow$ scroll to **Model Sources → Local Ollama Models**.
2. Enter an invalid path (e.g. `C:\FakePath`) $\rightarrow$ Click **Save** $\rightarrow$ Verify clear error message.
3. Enter `.ollama` directory path $\rightarrow$ Click **Save** $\rightarrow$ Verify path normalization (Configured: `.ollama` vs Resolved: `.ollama/models`), status badge (`✓ Valid (X models)`), and auto-populated **Available Local Models** list.
4. Click **Refresh** $\rightarrow$ Verify model list rescans cleanly.
