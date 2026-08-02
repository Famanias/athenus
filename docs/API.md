# API.md

# Athenus Knowledge OS — Complete REST API Reference (v1.0)

---

## Base URL & Authentication

* **Base URL**: `http://localhost:8000/api/v1`
* **Desktop IPC Security**: Bearer token injected by Tauri shell on startup (`Authorization: Bearer <IPC_BEARER_TOKEN>`).

---

## 1. Health & System Diagnostics
* **GET** `/api/v1/health` — System status
* **GET** `/api/v1/health/providers` — Provider & capability health status

## 2. Media Ingestion & Processing
* **POST** `/api/v1/media/upload` — Upload video file
* **GET** `/api/v1/media/{media_id}/status` — Processing status
* **GET** `/api/v1/media/{media_id}/transcript` — Timestamped transcript segments
* **GET** `/api/v1/media/{media_id}/stream` — SSE live processing event stream

## 3. RAG Retrieval & Workspace Chat
* **POST** `/api/v1/chat/query` — Streamed RAG response with clickable timestamp citations

## 4. Workspace Management (Phase 2)
* **POST** `/api/v1/workspaces` — Create new workspace
* **GET** `/api/v1/workspaces` — List workspaces
* **GET** `/api/v1/workspaces/{workspace_id}` — Get workspace details

## 5. Knowledge Graph (Phase 3)
* **GET** `/api/v1/graph/prerequisites/{concept_id}` — Get concept prerequisite hierarchy

## 6. Learning Tools & Active Recall (Phase 4)
* **GET** `/api/v1/learning/quizzes/{media_id}` — Generate/retrieve comprehension quiz
* **GET** `/api/v1/learning/flashcards/{media_id}` — Retrieve SM-2 flashcard deck

## 7. Agentic AI Suite (Phase 5)
* **GET** `/api/v1/agents/list` — List registered AI agents
* **POST** `/api/v1/agents/coordinate` — Execute multi-agent coordination workflow
