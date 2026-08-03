# Implementation Plan: Settings Persistence via SQLite Database

Fix settings persistence across application restarts by storing all system settings in the application's existing SQLite database (`./data/athenus.db`) as the single source of truth, removing in-memory state volatility, explicitly initializing settings during application startup, and rehydrating settings in the frontend on launch.

---

## Technical Architecture & Core Principles

### 1. Single Source of Truth (SQLite Database)
- **Zero Duplicate Storage**: Store all user and system settings inside the application's canonical SQLite database (`./data/athenus.db`).
- **SQLite Table (`SystemSettings`)**:
  ```python
  class SystemSettings(SQLModel, table=True):
      __tablename__ = "system_settings"
      id: str = Field(default="global", primary_key=True)
      default_llm: str = "ollama"
      selected_ollama_model: Optional[str] = None
      ollama_models_dir: Optional[str] = None
      default_stt: str = "faster-whisper"
      default_embedding: str = "BAAI/bge-small-en-v1.5"
      gpu_acceleration: bool = True
      updated_at: datetime = Field(default_factory=datetime.utcnow)
  ```
- **Clean Schema**: Focuses strictly on typed, validated application settings (omitting redundant dumping fields or coupled API keys).

### 2. Dedicated `SettingsService` & Explicit Startup Initialization
- **`SettingsService` (`backend/app/domain/settings/settings_service.py`)**:
  - `get_settings()`: Fetches global settings from SQLite. Initializes default record if none exists.
  - `update_settings(updates: dict)`: Updates settings record and commits transaction to SQLite.
- **Explicit Startup**: Server startup (`app/main.py`) explicitly initializes `SettingsService` and configures router policy / providers during backend startup.

### 3. Edge Case Handling
- **Missing/Invalid Directory**: If the saved `ollama_models_dir` path no longer exists on disk upon restart, the saved path string remains intact in SQLite. `OllamaModelScanner` returns `valid: False` with descriptive error details instead of clearing the user's saved path.
- **Provider Integrity**: Provider preferences (`default_llm`, `selected_ollama_model`, `default_stt`, `gpu_acceleration`) remain 100% functional even if the configured models directory is temporarily invalid.

### 4. Frontend Startup Rehydration (`DesktopShell.tsx`)
- Call `getProviderSettings()` and `getOllamaSettings()` during app initialization in `DesktopShell.tsx` so all components receive persisted settings immediately upon application launch.

---

## Proposed Code Changes

### Backend Subsystem (`backend/app/`)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- Add `SystemSettings` schema.

#### [NEW] [settings_service.py](file:///e:/repos/athenus/backend/app/domain/settings/settings_service.py)
- Implement `SettingsService` for reading and writing `SystemSettings` in SQLite.

#### [MODIFY] [settings.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py)
- Replace ephemeral `current_settings` dict with calls to `SettingsService`.

#### [MODIFY] [main.py](file:///e:/repos/athenus/backend/app/main.py)
- Explicitly load settings from `SettingsService` on backend boot.

---

### Frontend Subsystem (`frontend/src/`)

#### [MODIFY] [useAppStore.ts](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts)
- Extend `rehydrateStoredState()` to fetch provider and Ollama settings on application boot.

#### [MODIFY] [DesktopShell.tsx](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx)
- Trigger `rehydrateStoredState()` on mount.

---

## Verification Plan

### Automated Tests
- Create test file [`backend/tests/test_settings_persistence.py`](file:///e:/repos/athenus/backend/tests/test_settings_persistence.py):
  - Save settings via `PUT /settings/providers` and `PUT /settings/ollama`.
  - Re-instantiate `SettingsService` (simulating process restart).
  - Assert all settings (`default_llm`, `selected_ollama_model`, `ollama_models_dir`) persist accurately in SQLite.
- Run backend pytest: `python -m pytest`
- Run frontend type check: `npx tsc --noEmit` (in `frontend/`)

### Manual Verification Matrix

| Scenario | Test Action | Expected Behavior |
|---|---|---|
| **Save Settings** | Configure Ollama directory, select provider (`groq`/`ollama`), select model. | Settings save to SQLite successfully without errors. |
| **Restart Backend & Frontend** | Stop python server & tauri app $\rightarrow$ Restart both. | Settings (directory, provider, model) are restored automatically from SQLite. |
| **Multiple Restarts** | Restart server 3 times in succession. | Settings remain 100% consistent across every restart. |
| **Invalid Directory Graceful Handling** | Save invalid directory $\rightarrow$ Restart. | Preserves saved path in SQLite; badge displays `✕ Invalid Directory` while provider & model settings remain intact. |
