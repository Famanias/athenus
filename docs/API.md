# API.md — Athenus Complete REST API Reference (v1.0)

Complete specification for all REST API endpoints exposed by the FastAPI backend engine.

---

## Base URL & Desktop IPC Security
* **Base URL**: `http://localhost:8000/api/v1`
* **Port**: `8000` (FastAPI / Uvicorn server)
* **Configurable**: The browser/desktop base URL is resolved via `NEXT_PUBLIC_API_URL` (fallback `http://localhost:8000`) through [`src/config/env.ts`](file:///e:/repos/athenus/frontend/src/config/env.ts). When running the containerized web stack (`docker compose up -d --build`), the backend remains reachable at `http://localhost:8000` and the frontend at `http://localhost:3000` — no code changes required.

---

## 1. Health & System Diagnostics
* **GET** `/api/v1/health`
  - Returns backend operational status, active LLM/ASR providers, and SQLite DB connectivity.
* **GET** `/api/v1/health/providers`
  - Returns health details for registered AI capabilities (Text Gen, Whisper ASR, SentenceTransformers Embeddings, Vector Store).

---

## 2. Media Ingestion & Processing Pipeline
* **POST** `/api/v1/media/upload`
  - Upload local video/audio file for background ingestion.
  - **Form Parameters**: `file` (UploadFile), `title` (str), `workspace_id` (str, default: `"default"`).
  - **Response**: `MediaItem` DTO with status `uploaded`.
* **GET** `/api/v1/media/{media_id}/status`
  - Returns live processing status and current stage snapshot for a media item.
* **GET** `/api/v1/media/{media_id}/transcript`
  - Returns timestamped transcript segments loaded from SQLite `transcript_segments` table.
* **GET** `/api/v1/media/{media_id}/file`
  - Serves the raw uploaded media file for video player playback.
* **GET** `/api/v1/media/{media_id}/stream`
  - Server-Sent Events (SSE) streaming endpoint emitting real-time stage progress updates (`0%` $\rightarrow$ `100%`).
* **GET** `/api/v1/media/{media_id}/history`
  - Returns complete chronological ingestion audit log history from SQLite `processing_logs` table.

---

## 3. RAG Retrieval & Multi-Session Workspace Chat
* **POST** `/api/v1/chat/query`
  - Executes 8-stage RAG retrieval pipeline and returns assistant answer with timestamp citations. Automatically lazy-creates `ChatSession` if `session_id` is omitted and persists query turn and citations to SQLite `chat_messages` table.
  - **Body**: `{ "query": "string", "workspace_id": "default", "session_id": "optional", "media_id": "optional", "current_timestamp": optional, "selected_text": optional }`
* **GET** `/api/v1/chat/history?workspace_id={workspace_id}&session_id={session_id}`
  - Fetches conversation history for a specific session or active workspace session from SQLite `chat_messages` table.
* **DELETE** `/api/v1/chat/history?workspace_id={workspace_id}&session_id={session_id}`
  - Deletes chat session messages for a specific session or workspace in SQLite.

---

## 4. Multi-Workspace Management
* **GET** `/api/v1/workspaces?include_archived=true`
  - Lists all learning workspaces loaded from SQLite `workspaces` table (sorted by pinned status and `last_accessed_at`).
* **POST** `/api/v1/workspaces`
  - Creates a new workspace and saves it to SQLite database.
* **GET** `/api/v1/workspaces/active`
  - Returns current active workspace context (`active_workspace_id`).
* **POST** `/api/v1/workspaces/{workspace_id}/activate`
  - Sets active workspace context and updates `last_accessed_at` timestamp.
* **GET** `/api/v1/workspaces/{workspace_id}`
  - Returns workspace details, metadata (`is_pinned`, `is_archived`, `last_accessed_at`), and associated media item IDs.
* **PATCH** `/api/v1/workspaces/{workspace_id}`
  - Updates workspace metadata (name, description, icon, `is_pinned`, `is_archived`).
* **DELETE** `/api/v1/workspaces/{workspace_id}`
  - Deletes a workspace with cascading removal of SQLite records and vector payloads. Safely switches active workspace context if target workspace is currently active.

---

## 5. Multi-Session Management
* **GET** `/api/v1/workspaces/{workspace_id}/sessions?include_archived=true`
  - Lists chat sessions for a workspace with preview metadata (`preview_text`, `message_count`, `last_message_at`).
* **POST** `/api/v1/workspaces/{workspace_id}/sessions`
  - Manually creates a new chat session under a workspace.
* **GET** `/api/v1/sessions/{session_id}`
  - Returns details for a specific chat session.
* **PATCH** `/api/v1/sessions/{session_id}`
  - Updates session metadata (title, `is_pinned`, `is_archived`).
* **DELETE** `/api/v1/sessions/{session_id}`
  - Deletes a chat session and its associated chat messages.

---

## 6. Knowledge Graph
* **GET** `/api/v1/graph/prerequisites/{concept_id}`
  - Queries prerequisite hierarchy for a concept node.

---

## 7. System Settings & Local Model Sources
* **GET** `/api/v1/settings/providers`
  - Fetches persistent system settings from SQLite `system_settings` table (`default_llm`, `selected_ollama_model`, `default_stt`, `default_embedding`, `gpu_acceleration`).
* **PUT** `/api/v1/settings/providers`
  - Updates provider selections and selected local model, persisting updates directly to SQLite.
* **GET** `/api/v1/settings/ollama`
  - Returns configured Ollama models directory path, resolved path, directory validation status, and discovered model list.
* **PUT** `/api/v1/settings/ollama`
  - Updates and persists configured Ollama models directory path in SQLite `system_settings` table, performing path normalization (`.ollama` $\rightarrow$ `.ollama/models`) and filesystem validation.
* **POST** `/api/v1/settings/ollama/scan`
  - Triggers on-demand filesystem scan of the configured Ollama models directory to discover installed models.

