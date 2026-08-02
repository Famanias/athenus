# Implementation Plan: Fix Integration Issues & Full API Connection

This plan resolves the integration issues identified during manual testing to move the frontend from mock/demo data to full backend integration with our FastAPI server. It preserves Athenus's local-first, offline-capable philosophy.

---

## Scope Classification

The four work items are intentionally separated so each type of change can be reviewed, tested, and merged independently.

| # | Work Item | Type |
|---|-----------|------|
| 1 | RAG Chat Citation field mapping | Bug Fix |
| 2 | Workspace Library & Media Transcript | Integration |
| 3 | Media Upload SSE Stream | Feature Completion |
| 4 | Provider Settings Persistence | New Backend Capability |

**Section layout:**
- [Bug Fixes](#bug-fixes)
- [Integrations](#integrations)
- [New API Endpoints](#new-api-endpoints)
- [Shared Infrastructure](#shared-infrastructure)
- [Error & Offline Behavior](#error-and-offline-behavior)
- [Verification Plan](#verification-plan)

---

## Bug Fixes

### Bug 1: RAG Chat Citation Field Mapping

#### [MODIFY] `frontend/src/features/chat/useChat.ts`
The backend returns `CitationDTO` (`chunk_id`, `start_time: float`, `end_time: float`, `text: str`) but the frontend `Citation` model (`mediaId`, `mediaTitle`, `startTime: string`, `endTime: string`, `score`, `textSnippet`) does not align. The root cause is a DTO field + type mismatch:

```text
Backend CitationDTO                 Frontend Citation
  start_time: float  ──► map ──►    startTime: "MM:SS"
  end_time: float    ──► map ──►    endTime: "MM:SS"
  text: str          ──► map ──►    textSnippet: str
```

Changes:
- Add a mapper (e.g. `mapBackendCitations()`) that converts `start_time`/`end_time` floats (seconds) to `"MM:SS"` strings, sets `textSnippet` from `text`, and defaults `mediaTitle` to `"Lecture Segment"`.
- `score` and `mediaId` may be absent from the backend DTO — default `score` to `0` and `mediaId` to the active media id / empty string.
- Route the fetch response through this mapper instead of assigning `data.citations` directly (line 105).

#### [MODIFY] `frontend/src/features/chat/ChatMessageItem.tsx`
- Update the citation badge to safely handle optional `mediaTitle`, `mediaId`, `startTime`, and `endTime` (render `⏱ 12:40 - 13:10` only when values exist; fall back gracefully otherwise).

#### Tests
- Add a unit test (small helper) verifying float→`MM:SS` conversion, e.g. `840.0 → "14:00"`, `12.6 → "00:12"`, and media title fallback.

---

## Integrations

### Integration 2: Workspace Library & Media Transcript

> **Design note — no default seeding.** If the workspace/library is empty, it stays empty. The frontend shows an empty state ("No workspaces yet. Upload your first lecture.") rather than the backend silently creating a default workspace. This keeps the backend truthful and avoids hidden side effects.

#### [MODIFY] `frontend/src/features/library/useLibrary.ts`
- Replace the hardcoded `GET /workspaces/ws_default` call with a real listing call via `libraryApi.getLibrary()` (see [Shared Infrastructure](#shared-infrastructure)).
- Fetch workspaces + their media assets, then map the backend `MediaItem` shape onto the frontend `MediaAsset` interface.
- If the workspace list is empty: render an empty-state placeholder instead of falling back to the 3 mock assets.
- Only fall back to mock data when the backend is genuinely unreachable (see Offline behavior).

#### [MODIFY] `frontend/src/features/video/useVideo.ts`
- Replace `MOCK_TRANSCRIPT_SEGMENTS` with a call to `GET /api/v1/media/{media_id}/transcript` via `mediaApi.getTranscript(mediaId)`.
- Map backend `segments` (each with a start time / timestamp and text) onto `TranscriptSegment`.
- Guard the lookup: if the media has no transcript yet (e.g. still processing), show an explicit "Transcript not ready" state instead of empty content.

#### [MODIFY] `frontend/src/store/useAppStore.ts`
- The current default `activeWorkspaceId` is `'ws_ml_default'` while the backend serves `'default'` — resolve this mismatch deterministically (e.g. derive active workspace id from the fetched workspace list, or align the default with the backend workspace id).

> Note: The current `WorkspaceService` keeps workspaces in an **in-memory dict** (seed value `default`), not SQLite. Integrations should be built against the real endpoints; persistence hardening is tracked separately (see [Follow-ups](#follow-ups)).

#### Tests
- Backend: workspace list + transcript endpoints covered by existing pytest route tests.
- Frontend: typecheck + build (see Verification).

---

## New API Endpoints

### API 4: Provider Settings Persistence

> **Design note:** Do **not** place a write endpoint under `/health`. Health endpoints are read-only diagnostics (`GET /health`, `/health/providers`). Configuration is not "health." Provider settings live under a dedicated settings resource.

#### [NEW] `backend/app/presentation/api/v1/settings.py`
Add a new router exposing provider configuration:

- `GET /api/v1/settings/providers` — read current provider configuration (reuses `ProviderHealthResponse` shape: `default_llm`, `default_stt`, `default_embedding`, `gpu_acceleration`).
- `PUT /api/v1/settings/providers` — update provider settings from a request body `{ default_llm, default_stt, gpu_acceleration }`, persist, and return the updated config. `PUT` (idempotent) better matches "save configuration" semantics than `POST`.
- Validate provider values against the `ModelRegistry` so an unknown provider is rejected with `422` rather than silently accepted.

Register the router in `backend/app/main.py`:

```python
from app.presentation.api.v1.settings import router as settings_router
app.include_router(settings_router, prefix=settings.API_V1_PREFIX, tags=["Settings"])
```

> The existing `GET /health/providers` stays as a read-only diagnostic. Remove it only if unused.

#### [MODIFY] `frontend/src/store/useAppStore.ts`
- Add settings state: `llmProvider`, `sttProvider`, `gpuAcceleration`, plus actions `setProviderSettings()` and `setProviderAvailability()`.

#### [MODIFY] `frontend/src/features/settings/SystemSettings.tsx`
- On mount, hydrate the form from `GET /settings/providers`.
- "Save Configuration" calls the API client `settingsApi.save()` (`PUT /settings/providers`), updates the Zustand store, and shows a success toast.
- On failure show an error toast and keep the previous state.

#### Tests
- Backend: pytest covering `GET`/`PUT` round-trip and unknown-provider rejection.
- Frontend: typecheck + build.

---

## Shared Infrastructure

### Centralized API Client (architectural improvement)

Rather than every hook calling `fetch('http://localhost:8000/...')` directly (currently duplicated in `useChat`, `useLibrary`, `useIngestion`, `useGraph`, `useFlashcards`), introduce a thin services layer:

```text
Feature hooks
  useChat()      useLibrary()   useIngestion()   useVideo()
      │               │              │               │
      ▼               ▼              ▼               ▼
  chatService    libraryService   mediaService     mediaService
      └──────────────┬───────────────┴───────────────┘
                     ▼
              apiClient (base + fetch + error mapping)
```

- **[NEW] `frontend/src/services/apiClient.ts`** — single fetch wrapper. Exposes the base URL, JSON/error normalization (throw typed `ApiError`), and request logging.
- **[NEW]** `chat.service.ts`, `library.service.ts`, `media.service.ts`, `settings.service.ts` — one service per domain grouping the related endpoints.
- This centralizes retries, auth headers, logging, and test mocking.

#### Avoid hardcoded URLs

Replace every `http://localhost:8000` literal (present in 5 files) with a configured base URL:

- **[NEW] `frontend/src/config/env.ts`** — `export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';`
- The api client uses `API_BASE_URL`, so local, hybrid, and cloud deployments all work without code edits.

```text
useChat.ts            ──►  chatService.ask()
useLibrary.ts         ──►  libraryService.getLibrary()
useVideo.ts           ──►  mediaService.getTranscript()
useIngestion.ts       ──►  mediaService.upload() + subscribeStream()
useGraph.ts           ──►  graphService.getPrerequisites()
useFlashcards.ts      ──►  learningService.getFlashcards()
SystemSettings.tsx    ──►  settingsService.save()
```

> This is a refactor; each hook's public interface stays the same so callers (`ChatWorkspace`, `LibraryGrid`, `VideoWorkspace`, etc.) are unaffected.

---

## Error and Offline Behavior

Local-first Athenus means **graceful fallback is core UX**, not an exception. Standardize handling per hook:

| Condition | Behavior |
|-----------|----------|
| Backend not running / fetch fails | Fall back to mock/offline data **only where a usable fallback exists** (chat demo answer, sample library). Surface a non-blocking "Backend unavailable" notice. No crashes. |
| SSE disconnect / stream error | Mark the pipeline stage `failed` and allow retry. Do not silently show 100% completion. |
| Upload fails | Set `isUploading=false`, mark upload stage `failed`, show error toast with reason. No fake success. |
| Transcript doesn't exist yet | Show explicit "No transcript ready" empty state, not empty content. |
| Provider save returns 500 / 422 | Show error toast, keep button enabled, do **not** mutate store. |

Reusable pieces:
- **[NEW] `frontend/src/services/api/client.ts`** distinguishes "network down" (`TypeError`/fail) from an API error response (has status), so hooks can render the right fallback.
- **[NEW] `frontend/src/components/ui/BackendUnavailableNotice.tsx`** (or similar) — a dismissible banner that any hook-driven screen can render when the backend is unreachable.

**Empty states** (not silent defaults): render "No workspaces yet — upload your first lecture" and "No transcript for this video yet." The user data stays authoritative.

---

## Verification Plan

### Automated Verification
1. Backend pytest suite:
   ```bash
   cd backend
   pytest
   ```
   - Includes new settings router tests + existing route tests.
2. Frontend typecheck & build:
   ```bash
   cd frontend
   npm run typecheck   # or: npx tsc --noEmit
   npm run build       # or: npx next build
   ```

### Manual Verification (happy path)
1. Launch backend (`python app/main.py`) and frontend desktop app (`npx tauri dev`).
2. AI Research Assistant chat → confirm citations render as `⏱ 12:40 - 13:10`, never `⏱ - ()`.
3. Upload a media file in Ingestion pipeline → confirm live SSE progress updates.
4. AI Models & Providers tab → change provider settings → Save → success toast + backend persisted (verify via `GET /settings/providers`).
5. Library → upload produces a real workspace/media entry; empty DB shows the empty state.

### Manual Verification (offline / local-first)
Critical scenario for a local-first app:
1. **Stop the backend**.
2. **Launch the frontend**.
3. Verify:
   - Shell loads and navigation works.
   - Mock/fallback data appears where expected (chat demo, sample library).
   - A "Backend unavailable" notice is shown.
   - **No crashes, no unhandled errors**, even when opening the settings tab.
   - Upload attempt fails gracefully (stage marked `failed`, not a fake 100%).

---

## Follow-ups (out of scope for this pass)
- True SQLite persistence for `WorkspaceService` and media status (currently in-memory) so data survives restarts.
- SSE reconnection + exponential backoff in `mediaService.subscribeStream()`.
- Auth header propagation for the Tauri IPC bearer token across the API client.
- Provider availability UI wired to the real backend (`/health/providers`) instead of static select options.