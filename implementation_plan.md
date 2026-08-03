# Implementation Plan — Context-Aware Chat Widget in Video Workspace

Implement an embedded AI Chat Widget directly within the Video Workspace (`view-video`), providing instant, context-aware AI assistance grounded in the current playback timestamp, video asset, and surrounding transcript speech without breaking the user's learning flow.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions & Enhancements Incorporated:**
> 1. **Backend-Owned Context Extraction (Single Source of Truth)**:
>    - *Redesign*: The frontend passes ONLY `{ workspace_id, media_id, current_timestamp: 754 }` to the backend.
>    - The backend (`chat.py` & `multi_stage_retriever.py`) queries SQLite (`TranscriptSegmentTable`), retrieves transcript segments within a ±30–45 second window around `current_timestamp`, and injects them into RAG Stage 8 prompt assembly.
>    - *Rationale*: Keeps request payloads lightweight, prevents client spoofing, centralizes context window logic on the server, and eliminates duplicated frontend transcript slicing code.
> 2. **Learning-State Aware Prompting**:
>    - Prepend rich learning state metadata into RAG Stage 8 prompt assembly:
>      ```text
>      [Active Playback Context]
>      Workspace ID: default
>      Media Asset: Lecture 3
>      Playback Timestamp: 12:34 (754s)
>      Surrounding Spoken Transcript (12:04 - 13:04):
>      "[12:04] ...spoken segment... [12:34] ...active line..."
>      ```
> 3. **Explicit Context Provenance Badge**:
>    - The backend returns `context_provenance` metadata in `ChatQueryResponse` (`media_title`, `timestamp_range: "12:04–13:04"`, `segment_count: 4`).
>    - Embedded Chat renders a sleek pill badge above AI responses: `📹 Lecture 3 | ⏱ 12:04–13:04 | 📝 4 Segments`.
> 4. **Selected Transcript Text Q&A ("Ask About Selection")**:
>    - Support optional `selected_text` parameter in `ChatQueryRequest`.
>    - In transcript card UI, add a **"💬 Ask AI About Selection"** button when hovering/selecting text.
> 5. **Unified Conversation Store (Shared Memory)**:
>    - Embedded Chat and Main Chat share the active workspace's conversation session in `chatSlice` and SQLite.
>    - Includes **"Full Chat View ↗"** button to transition to `ChatWorkspace` (`view-chat`) with full conversation state intact.

---

## Backend-Owned Data & Context Flow

```text
 ┌────────────────────────────────────────────────────────────────────────────────┐
 │                              FRONTEND                                          │
 │  Video Workspace                                                               │
 │  Active Media: "med_123" | Current Time: 754s (12:34)                          │
 └──────────────────────────────────────┬─────────────────────────────────────────┘
                                        │
             POST /api/v1/chat/query {
               query: "Can you explain this concept?",
               workspace_id: "default",
               media_id: "med_123",
               current_timestamp: 754.0,
               selected_text: null
             }
                                        │
                                        ▼
 ┌────────────────────────────────────────────────────────────────────────────────┐
 │                               BACKEND                                          │
 │  1. Query SQLite `transcript_segments` where `media_id == med_123`             │
 │     and `start_time` between (754 - 30s) and (754 + 30s)                       │
 │  2. MultiStageRetriever Stage 8: Prepend Active Playback Context into Prompt   │
 │  3. Execute LLM Text Generation -> Formulate Answer & Provenance Metadata      │
 └──────────────────────────────────────┬─────────────────────────────────────────┘
                                        │
             Returns ChatQueryResponse {
               answer: "...",
               citations: [...],
               context_provenance: {
                 media_title: "Lecture 3",
                 timestamp_range: "12:04 - 13:04",
                 segment_count: 4
               }
             }
```

---

## Proposed Changes

### Backend Infrastructure (`backend/app/`)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- Ensure indexed query lookup on `TranscriptSegmentTable.media_id` and `start_time`.

#### [MODIFY] [chat.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/chat.py)
- Update `ChatQueryRequest`:
  - `current_timestamp: Optional[float] = None`
  - `selected_text: Optional[str] = None`
- Update `ChatQueryResponse` to include `context_provenance: Optional[Dict[str, Any]] = None`.

#### [MODIFY] [workspace_intelligence.py](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py)
- Update `query_workspace()` signature to accept `current_timestamp` and `selected_text`.

#### [MODIFY] [multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py)
- Implement `_extract_timestamp_context(media_id, current_timestamp, window_seconds=30)` querying SQLite for active spoken segments.
- Prepend extracted timestamp context into Stage 8 RAG prompt assembly:
  `[Active Playback Context (Timestamp MM:SS): ...]`

---

### Frontend Services & Components (`frontend/src/`)

#### [MODIFY] [chatService.ts](file:///e:/repos/athenus/frontend/src/services/chatService.ts)
- Update `sendChatQuery()` to pass `current_timestamp` and `selected_text`.

#### [NEW] [EmbeddedChatWidget.tsx](file:///e:/repos/athenus/frontend/src/features/video/EmbeddedChatWidget.tsx)
- Create embedded chat widget:
  - Header: Active context badge (`📍 Context: 12:34`), expand button (`Full Chat View ↗`), clear chat.
  - Context Provenance badge above assistant responses (`📹 Lecture 3 | ⏱ 12:04–13:04`).
  - One-click prompt chips (`💡 Explain this`, `📝 Summarize last 2 min`, `❓ Quiz me`).
  - Input box with target seek citation handlers.

#### [MODIFY] [VideoWorkspace.tsx](file:///e:/repos/athenus/frontend/src/features/video/VideoWorkspace.tsx)
- Render right panel tabs: `[📝 Transcript]` vs `[💬 AI Assistant]` (with side-by-side pin option on wide screens).
- Pass `videoRef.current.currentTime` as `current_timestamp` when sending query.
- Add **"💬 Ask AI About Selection"** action button to transcript cards when text is selected.

---

### Automated Tests & Verification (`backend/tests/`)

#### [NEW] [test_context_chat.py](file:///e:/repos/athenus/backend/tests/test_context_chat.py)
- Add integration tests verifying:
  - Backend extracts ±30s transcript segments matching `current_timestamp`.
  - Response contains `context_provenance` and grounded citations.

---

## Verification Plan

### Automated Tests
1. **Context Chat Pytest Suite**:
   ```bash
   cd backend
   python -m pytest tests/test_context_chat.py
   python -m pytest
   ```
2. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```

### Manual Testing Guide
1. Open **Video** (`view-video`) and play a video to timestamp `12:34`.
2. Click **💬 AI Assistant** tab in Video Workspace.
3. Type *"Can you explain this concept?"* or click prompt chip **💡 Explain what was just said**.
4. *Expected Result*: Backend extracts transcript around 12:34. AI answer includes context provenance badge (`📹 Lecture 3 | ⏱ 12:04–13:04`) and grounded citations.
5. Click **Full Chat View ↗**.
6. *Expected Result*: Main **Chat** (`view-chat`) opens displaying the complete conversation thread intact.
