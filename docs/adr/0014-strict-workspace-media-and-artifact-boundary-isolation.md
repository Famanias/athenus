# ADR 0014: Strict Workspace Media & Artifact Boundary Isolation

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: When users switched active workspaces in the UI, transient selection state (`activeMediaId`) was retained in Zustand store and localStorage. As a result, lecture videos and transcripts from Workspace 1 could inadvertently render inside Workspace 2.
* **Decision**: Enforce **Strict Workspace Boundary Isolation** across all application layers:
  1. Store Layer: `switchWorkspace()` sets `activeMediaId: null` and purges transient media keys from `localStorage`.
  2. Hook Layer: `useVideo` passes `activeWorkspaceId` to transcript and media URL requests. If a requested media ID does not belong to the active workspace, state is cleared.
  3. API Layer: `/api/v1/media/{id}/transcript`, `/file`, and `/status` validate `workspace_id` and return `404 Not Found` on cross-workspace requests. Added `GET /api/v1/media/workspace/{id}` to list workspace-only assets.
* **Alternatives Considered**:
  - *Frontend-Only Filtering*: Allowed unauthorized API access if media IDs were known.
* **Rationale**: Multi-layer workspace isolation prevents data leaks and guarantees that every workspace remains an isolated learning container.
* **Trade-offs**: Requires passing `workspace_id` parameters across API calls, but ensures complete privacy and data security.
