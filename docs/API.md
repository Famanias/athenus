# API.md — Athenus Knowledge OS Complete REST API Reference (v1.0)

Complete specification for all REST API endpoints exposed by the FastAPI backend engine.

---

## Base URL & Desktop IPC Security
* **Base URL**: `http://localhost:8000/api/v1`
* **Port**: `8000` (FastAPI / Uvicorn server)

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

## 3. RAG Retrieval & Persistent Workspace Chat
* **POST** `/api/v1/chat/query`
  - Executes 8-stage RAG retrieval pipeline and returns assistant answer with timestamp citations. Automatically persists query turn and citations to SQLite `chat_messages` table.
  - **Body**: `{ "query": "string", "workspace_id": "default", "media_id": optional }`
* **GET** `/api/v1/chat/history?workspace_id={workspace_id}`
  - Fetches past conversation messages for a workspace from SQLite `chat_messages` table across app restarts.
* **DELETE** `/api/v1/chat/history?workspace_id={workspace_id}`
  - Deletes all chat session messages for a workspace in SQLite upon user action.

---

## 4. Workspace Management
* **GET** `/api/v1/workspaces`
  - Lists all learning workspaces loaded from SQLite `workspaces` table.
* **POST** `/api/v1/workspaces`
  - Creates a new workspace and saves it to SQLite database.
* **GET** `/api/v1/workspaces/{workspace_id}`
  - Returns workspace details and associated media item IDs.

---

## 5. Knowledge Graph
* **GET** `/api/v1/graph/prerequisites/{concept_id}`
  - Queries prerequisite hierarchy for a concept node.
