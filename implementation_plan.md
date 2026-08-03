# Implementation Plan — Phase 1: Establish a True Persistent Workspace

Establish full application data persistence using **SQLite as the canonical metadata database**, ensuring workspaces, uploaded videos, transcripts, status, and chat conversations survive backend restarts and application re-opens.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions for Phase 1:**
> 1. **SQLite as Canonical Metadata Store**: Replace `InMemoryMediaRepository` and `InMemory WorkspaceService` dictionary maps with `SqliteMediaRepository` and SQLModel database models stored in `./data/athenus.db`.
> 2. **Persistent Chat Session Models**: Introduce `ChatSessionTable` and `ChatMessageTable` in SQLite so chat conversations survive application restarts.
> 3. **Automatic Startup Restoration**: On backend initialization (`lifespan`), `init_db()` automatically migrates SQLite tables, ensures the default workspace exists, reconnects to Embedded Qdrant vector storage, and loads persisted asset metadata.
> 4. **Incremental Phase Execution**: Focus strictly on Phase 1 persistence. Stop and request user review before moving to Phase 2 (Workspace Isolation).

---

## Proposed Changes

### Database Layer (`backend/app/infrastructure/db/`)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- Expand `WorkspaceTable`, `MediaItemTable`, and `TranscriptChunkTable` fields.
- **[NEW]** Add `ChatSessionTable` and `ChatMessageTable` SQLModel classes for chat persistence.
  - `ChatSessionTable`: `id` (PK), `workspace_id` (Indexed), `title`, `created_at`, `updated_at`
  - `ChatMessageTable`: `id` (PK), `session_id` (Indexed), `sender`, `content`, `citations_json`, `created_at`

---

### Application Repositories & Domain Services (`backend/app/application/repositories/`)

#### [NEW] [sqlite_media_repository.py](file:///e:/repos/athenus/backend/app/application/repositories/sqlite_media_repository.py)
- Implement `SqliteMediaRepository(MediaRepository)` using SQLModel sessions (`get_session()` / `engine` from `session.py`).
- Implement methods:
  - `upsert(item: MediaItem)`
  - `get(media_id: str) -> Optional[MediaItem]`
  - `update_status(media_id: str, status: ProcessingStatus, error_message: Optional[str])`
  - `save_transcript(media_id: str, segments: List[Dict[str, Any]])`
  - `get_transcript(media_id: str) -> List[Dict[str, Any]]`
  - `list_by_workspace(workspace_id: str) -> List[MediaItem]`

#### [MODIFY] [workspace_service.py](file:///e:/repos/athenus/backend/app/domain/workspace/workspace_service.py)
- Update `WorkspaceService` to query and persist workspaces and media associations directly to `WorkspaceTable` in SQLite rather than an in-memory dictionary.

---

### Presentation & API Layer (`backend/app/presentation/api/v1/`)

#### [MODIFY] [media.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py)
- Instantiate `media_repository = SqliteMediaRepository()` instead of `InMemoryMediaRepository()`.

#### [MODIFY] [chat.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/chat.py)
- Save query turns and citations to `ChatMessageTable` in SQLite during `POST /chat/query`.
- Add endpoint `GET /chat/history` to load past conversation messages for a workspace on startup/re-open.

#### [MODIFY] [main.py](file:///e:/repos/athenus/backend/app/main.py)
- Ensure `init_db()` is invoked during `lifespan` startup to create all tables.
- Ensure `WorkspaceService.ensure_default_workspace()` runs against SQLite.

---

### Frontend Chat Persistence (`frontend/src/`)

#### [MODIFY] [chatSlice.ts](file:///e:/repos/athenus/frontend/src/store/chatSlice.ts) & [useChat.ts](file:///e:/repos/athenus/frontend/src/features/chat/useChat.ts)
- Load past chat history from `GET /api/v1/chat/history` when mounting `ChatWorkspace`, keeping previous discussions intact across restarts.

---

## Verification Plan

### Automated Tests
1. **Backend Test Suite**:
   ```bash
   cd backend
   python -m pytest
   ```
   - Add test cases in `tests/test_sqlite_repository.py` verifying that `MediaItem`, transcripts, and chat turns written to SQLite persist across session closing/re-opening.
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Verification
1. Start FastAPI backend (`python app/main.py`) & Tauri frontend (`npx tauri dev`).
2. Upload a video file into a workspace.
3. Submit a chat query in the Chat tab and receive a grounded response.
4. Stop the backend server and restart `main.py`.
5. Verify in the UI and via REST endpoints (`GET /api/v1/workspaces`, `GET /api/v1/media`, `GET /api/v1/chat/history`) that the workspace, video metadata, transcript, and chat messages are fully restored.
