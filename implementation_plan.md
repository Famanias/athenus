# Implementation Plan — "Clear my Data" System Reset Service & Safety Pipeline

Implement a robust, atomic, and safe "Clear my Data" (Factory Reset) system using a dedicated `SystemResetService`. This orchestrates active worker cancellation, locking, resource purging (SQLite, Qdrant, disk files), default workspace re-creation, and frontend hard-reloads while preserving user provider configurations.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions & Enhancements Incorporated:**
> 1. **Dedicated Service Architecture (`SystemResetService`)**:
>    - Encapsulates reset logic inside `backend/app/application/services/system_reset_service.py`, keeping the FastAPI router in `system.py` thin and reusable.
> 2. **Worker Cancellation & Synchronization Lock**:
>    - Uses a thread-safe `asyncio.Lock()` (`_reset_lock`) to prevent concurrent reset calls.
>    - Cancels active background ingestion workers first before touching storage, preventing write collisions or orphaned vectors/files.
> 3. **Strict Order of Operations**:
>    ```text
>    Acquire Lock -> Cancel Active Ingestion Workers -> Delete Qdrant Vectors -> Delete SQLite Records -> Delete Uploaded Disk Files -> Re-create Default Workspace -> Clear Progress Caches -> Release Lock
>    ```
> 4. **Explicit Resource Lifecycle Matrix**:
>    - **Purged**: Media Items, Transcripts, Chunks, Chat Sessions, Chat Messages, Ingestion Logs, Knowledge Graph Concepts & Relations, Qdrant Embeddings, Disk Upload Files.
>    - **Recreated**: Default Workspace (`Machine Learning & Deep Learning`).
>    - **Preserved (Not Wiped)**: System Settings (LLM/STT provider selections, CUDA GPU toggle, OpenRouter/Groq API keys) so model configuration remains intact.
> 5. **High-Security Confirmation**:
>    - Confirmation modal requires typing the exact text: `"CLEAR MY DATA"` before enabling the destructive reset button.
> 6. **Frontend Hard Refresh**:
>    - On success, the UI triggers `window.location.reload()` to purge all stale React/Zustand state from RAM.

---

## Resource Lifecycle Matrix

| Resource | Action | Recreated? | Notes |
|---|---|---|---|
| **Workspaces** | Deleted | **Yes** (Default Workspace) | Restores clean "Machine Learning & Deep Learning" workspace |
| **Media Items** | Deleted | No | All uploaded lecture videos removed from SQLite |
| **Transcript Chunks & Segments** | Deleted | No | All Whisper ASR text and RAG chunks purged |
| **Chat Sessions & Messages** | Deleted | No | All user prompts and assistant answers purged |
| **Ingestion Telemetry Logs** | Deleted | No | `processing_logs` table purged |
| **Knowledge Graph (Nodes & Triples)** | Deleted | No | `knowledge_concepts` and `knowledge_relations` purged |
| **Vector Embeddings (Qdrant)** | Deleted | No | All Qdrant collection points cleared |
| **Uploaded Video Files (`./data/uploads`)** | Deleted | No | Physical files deleted from disk |
| **System Settings & API Keys** | **Preserved** | N/A | Theme, LLM choice, API keys remain intact for instant reuse |

---

## Proposed Changes

### Application Core & Service Layer (`backend/app/application/services/`)

#### [NEW] [system_reset_service.py](file:///e:/repos/athenus/backend/app/application/services/system_reset_service.py)
- Create `SystemResetService` containing:
  - `_reset_lock = asyncio.Lock()`
  - `perform_factory_reset()` executing the ordered workflow:
    1. Acquire `_reset_lock` (raises 409 if reset already in progress).
    2. Cancel background ingestion workers / progress store active tasks.
    3. Clear Qdrant collection points via `EmbeddedQdrantVectorStoreAdapter`.
    4. Truncate/delete all SQLite records except settings.
    5. Delete physical video files from `./data/uploads/`.
    6. Re-create default workspace in SQLite.
    7. Clear `ProgressStore` in-memory snapshot map.
    8. Release `_reset_lock`.

---

### Presentation & API Layer (`backend/app/presentation/api/v1/`)

#### [NEW] [system.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/system.py)
- Expose `POST /api/v1/system/clear-data` routing directly to `SystemResetService.perform_factory_reset()`.

#### [MODIFY] [main.py](file:///e:/repos/athenus/backend/app/main.py)
- Register `system.router` with `/api/v1` prefix.

---

### Frontend Services & Danger Zone UI (`frontend/src/`)

#### [MODIFY] [settingsService.ts](file:///e:/repos/athenus/frontend/src/services/settingsService.ts)
- Add `clearAllData(): Promise<{ status: string; message: string }>` function.

#### [MODIFY] [SystemSettings.tsx](file:///e:/repos/athenus/frontend/src/features/settings/SystemSettings.tsx)
- Add red-bordered **Danger Zone** section at bottom of settings.
- Add confirmation modal requiring the user to type `"CLEAR MY DATA"`.
- On API success, display success toast and execute `window.location.reload()`.

---

### Verification & Test Suite (`backend/tests/`)

#### [NEW] [test_system_clear_data.py](file:///e:/repos/athenus/backend/tests/test_system_clear_data.py)
- Add comprehensive test cases:
  1. `test_full_factory_reset()`: Populate database, vectors, and disk files $\rightarrow$ trigger reset $\rightarrow$ assert zero orphaned records or files remain.
  2. `test_system_settings_preserved()`: Verify LLM provider settings and API keys survive reset.
  3. `test_concurrent_reset_lock()`: Assert overlapping reset calls return lock conflict.

---

## Verification Plan

### Automated Tests
1. **System Reset Pytest Suite**:
   ```bash
   cd backend
   python -m pytest tests/test_system_clear_data.py
   python -m pytest
   ```
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Verification
1. Upload a video in **Pipelines** (`view-ingestion`) and ask a question in **Chat** (`view-chat`).
2. Navigate to **Settings** (`view-settings`) $\rightarrow$ scroll to **Danger Zone**.
3. Click **Clear All Application Data** $\rightarrow$ type `"CLEAR MY DATA"` $\rightarrow$ click **Confirm Reset**.
4. Observe successful reset toast, hard reload (`window.location.reload()`), and clean default state with saved API keys intact.
