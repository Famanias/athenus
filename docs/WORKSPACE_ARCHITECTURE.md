# WORKSPACE_ARCHITECTURE.md — Multi-Workspace & Multi-Session Architecture

Comprehensive architectural specification for Workspaces and Multi-Session chat lifecycles in Athenus Knowledge OS.

---

## 1. Multi-Workspace & Multi-Session Domain Hierarchy

Workspaces serve as the primary organizational, retrieval, and storage boundary within Athenus Knowledge OS. Each workspace represents a subject, course, or knowledge domain.

Within a workspace, users can launch **multiple chat sessions** to explore different questions without mixing conversation histories or corrupting vector context.

```text
Workspace Container (Primary Domain Boundary)
 ├── Media Library (Videos / Audio / Transcripts)
 ├── Vector Index (Qdrant payload filter: workspace_id)
 ├── Knowledge Graph (Concepts & Relationship Triples)
 ├── Active Recall Tools (Flashcards & Adaptive Quizzes)
 └── Multi-Session Chat Threads
      ├── Session A ("Exam Review") -> [Message 1, Message 2, ...]
      ├── Session B ("Gradient Descent") -> [Message 1, ...]
      └── Unsaved Draft ("New Chat")
```

---

## 2. Core Architectural Principles & Lifecycles

### 2.1 Backend Single Source of Truth
- The SQLite database (`athenus.db`) manages active workspace state and last-accessed session records.
- On app launch, frontend context hydrators fetch `GET /api/v1/workspaces/active` to set `activeWorkspaceId` and `activeSessionId` without relying on fragmented local storage heuristics.

### 2.2 Lazy Chat Session Creation
- Clicking **"New Chat"** places the UI into an in-memory draft state (`activeSessionId: null`, `isDraftSession: true`).
- A `ChatSessionTable` record is generated on the backend **only when the user submits their first query turn**.

### 2.3 Deterministic 9-Step Workspace Switching Lifecycle
Switching workspaces triggers an explicit, ordered execution sequence:
1. Save pending draft note or query input.
2. Cancel in-flight streaming LLM generation.
3. Clear transient UI state (input field, active evidence, agent logs).
4. Update global `WorkspaceContext` (`workspaceId`, `sessionId: null`, `mediaId: null`).
5. Fetch target workspace metadata and latest session.
6. Swap in-memory messages strictly to target active session (memory-efficient).
7. Refresh workspace media items in library.
8. Refresh concept graph and active recall flashcards/quizzes.
9. Preserve hidden video DOM node state without re-parenting (ADR 0005).

### 2.4 Active Workspace Safe Deletion
Deleting an active workspace triggers a fail-safe fallback:
1. Identify remaining workspace (or re-create default workspace if none exist).
2. Activate remaining workspace context FIRST.
3. Perform cascading SQLite deletion (`media_items`, `transcript_chunks`, `chat_sessions`, `chat_messages`, `knowledge_concepts`, `knowledge_relations`, `processing_logs`) and Qdrant payload vector removal.

---

## 3. Workspace REST API Reference

### Workspace Operations
* **Create Workspace**: `POST /api/v1/workspaces`
* **List Workspaces**: `GET /api/v1/workspaces?include_archived=true`
* **Get Active Workspace**: `GET /api/v1/workspaces/active`
* **Activate Workspace**: `POST /api/v1/workspaces/{workspace_id}/activate`
* **Get Workspace Details**: `GET /api/v1/workspaces/{workspace_id}`
* **Update Workspace**: `PATCH /api/v1/workspaces/{workspace_id}`
* **Delete Workspace**: `DELETE /api/v1/workspaces/{workspace_id}`

### Session Operations
* **List Sessions**: `GET /api/v1/workspaces/{workspace_id}/sessions?include_archived=true`
* **Create Session**: `POST /api/v1/workspaces/{workspace_id}/sessions`
* **Get Session**: `GET /api/v1/sessions/{session_id}`
* **Update Session**: `PATCH /api/v1/sessions/{session_id}`
* **Delete Session**: `DELETE /api/v1/sessions/{session_id}`
