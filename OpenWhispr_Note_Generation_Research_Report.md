# OpenWhispr Note-Taking Architecture — Research Report & Athenus Implementation Plan

**Research target:** `E:\repos\openwhispr` (OpenWhispr v1.8.3, Electron desktop dictation/notes app)
**Our repository:** `E:\repos\athenus` (Athenus, local-first AI learning workspace: FastAPI + Next.js + Tauri)
**Method:** Source-code tracing of both repositories (verified file paths, functions, line numbers). No README-only assumptions. READ-ONLY — no files modified.

---

## 1. Executive Summary

OpenWhispr generates notes through a **user-driven, synchronous AI action** applied to a stored note whose `transcript` field holds the meeting/dictation transcript as a JSON array of segments. The flow is: capture audio → transcribe (local whisper.cpp/Parakeet or cloud) → persist as a note with `transcript` JSON → user clicks an AI **Action** (e.g. "Generate Notes") in the note editor → a single-shot LLM call (`ReasoningService.processText`, inference scope `noteFormatting`) → the LLM's markdown output is written back to the note as `enhanced_content` → the editor shows an "enhanced" view. It is deliberately simple: **no chunking, no jobs, no queue, no structured output schema** — a free-text markdown enhancement of the note content plus its transcript.

Athenus already has the *hard 80%* of this feature and a strictly better pattern to copy: its **flashcard/quiz generation** pipeline (`FlashcardService`/`QuizService` + `artifact_jobs` progress + frontend polling) is a fully-versioned, progress-tracked, structured-output, heuristic-fallback generator over timestamped `transcript_chunks`. The recommended implementation is to **mirror the flashcard pattern exactly** for a new `NoteService`/`notes` table, and to reuse the existing Faster-Whisper transcription pipeline and AI Service Bus. The **only genuinely missing capability** is *computer audio capture* (Athenus has zero capture code today) — and even that is optional depending on whether the product requires live capture vs. generating notes from already-transcribed/uploaded media.

---

## 2. Phase 1 — How OpenWhispr Implements Note Generation (verified)

### 2.1 Overall architecture

| Layer | Location | Role |
|---|---|---|
| Electron main process | `main.js` (~70KB), `src/helpers/ipcHandlers.js` (10,678 lines) | Window lifecycle, IPC, all heavy work |
| Preload bridge | `preload.js` (~63KB) | Exposes `window.electronAPI` (invoke/listen) |
| Renderer | `src/App.jsx`, `src/components/*`, `src/stores/*` | React UI (dictation overlay + control panel), Zustand state |
| Database | `src/helpers/database.js` (5,597 lines), better-sqlite3 | All persistence |
| Local sidecars | whisper.cpp, sherpa-onnx (Parakeet), llama.cpp, Qdrant | Local STT, local LLM, vector search |

Key architectural rule: **the renderer never touches SQLite or audio devices.** Everything flows renderer → `window.electronAPI` → `ipcMain` handler (`ipcHandlers.js`) → `database.js` / audio sidecars.

### 2.2 Audio capture

- **Microphone/system audio:** `src/helpers/audioManager.js` (4,500+ lines). `startRecording` (L1165) uses the `MediaRecorder` API with `RECORDING_TIMESLICE_MS = 250` (L106), combining mic + system audio via `getDisplayMedia`/loopback (`windowsLoopbackAudioManager`, macOS `audioTapManager`, Linux portal).
- **Meeting capture:** two streams (mic + system-audio tap) with echo leak detection (`meetingEchoLeakDetector.js`), mic gating (`meetingMicGate.js`), and duplicate suppression (`meetingMicHoldback.js`).
- **Renderer wrapper:** `src/hooks/useAudioRecording.js`.

### 2.3 Transcription pipeline

- **Routing decision:** `src/helpers/transcriptionRoute.ts` → one of:
  - **Local whisper.cpp:** `processWithLocalWhisper` → `transcribeLocalWhisper` IPC → `whisperServer.js` (ports 8178–8199, `/inference`).
  - **Local NVIDIA Parakeet:** `processWithLocalParakeet` → sherpa-onnx (`parakeetServer.js`, 16kHz float32, 15s segments). Online-runtime models stream via WebSocket (`parakeetWsServer.js`).
  - **Cloud:** `processWithOpenWhisprCloud` → `cloud-transcribe` IPC → `POST {api}/api/transcribe`; BYOK OpenAI via AI SDK.
  - **Meeting streaming:** `src/stores/meetingRecordingStore.ts` state machine + `meetingStreamingProviders.js` (`openai-realtime`, `assemblyai-realtime`, `deepgram-realtime`, `corti-realtime`, `tinfoil-realtime`).
- **Transcript storage:** two paths —
  - Dictation → `transcriptions` table.
  - Meetings/uploads → `notes.transcript` column holding a **JSON array of segments** `{ text, source, timestamp, type, speaker?, speakerName? }`, parsed by `src/utils/parseTranscriptSegments.ts`.

### 2.4 Note generation (the exact implementation)

```
PersonalNotesView.tsx onRunAction (L767-824)
  → collects noteContent (editor HTML) + rawTranscript (JSON from note.transcript)
  → runAction(action, parts, contentHash, { isCloudMode, modelId })
    → actionProcessingStore.runBackgroundAction (src/stores/actionProcessingStore.ts L110)
      → builds systemPrompt = BASE_SYSTEM_PROMPT | MEETING_SYSTEM_PROMPT + "\n\n" + action.prompt (+ dictionary suffix)
      → reasoningService.processText(noteContent, modelId, ..., { inferenceScope: "noteFormatting", systemPrompt, temperature: 0.3 })
        → resolveInferenceProvider → PROVIDER_REGISTRY (src/services/ai/inferenceProviders/index.ts):
            "openwhispr" → cloudReason IPC → POST /api/reason
            "local"      → processLocalReasoning IPC → llama.cpp server
            "lan"        → self-hosted server
            BYOK        → AI SDK chat.completions
      → on success: window.electronAPI.updateNote({ enhanced_content, enhancement_prompt, enhanced_at_content_hash })
  → NoteEditor viewMode "enhanced" renders enhancement.content (src/components/notes/NoteEditor.tsx L1002-1012)
```

Key characteristics:
- **Synchronous single-shot LLM call** — non-streaming, no jobs/queue/SSE. Cancellation is "soft" (HTTP continues, result discarded).
- **Prompt management:** base prompts are hardcoded constants in `actionProcessingStore.ts` (`BASE_SYSTEM_PROMPT` L58, `MEETING_SYSTEM_PROMPT` L68); the user-editable action prompt lives in the SQLite `actions` table. Built-in **"Generate Notes"** action is seeded in `database.js` (L410-436). Per-scope model config resolved via `selectResolvedLLMConfig`/`selectResolvedNoteFormatting` in `src/stores/settingsStore.ts`; scope keys in `src/config/inferenceScopes.ts`.
- **Data sent to the AI:** note content + raw transcript segment text + system prompt (+ custom dictionary).
- **Output schema:** free markdown in `notes.enhanced_content`. **No structured JSON** for the action path (there is a `noteFormattingOutputSchema` setting, but the actions path uses free text).
- **Staleness guard:** `enhanced_at_content_hash` — enhancement is marked stale if the note content changes after generation.

### 2.5 Data models (SQLite, `database.js`)

- `notes` (L194): `id, title, content, note_type ('personal'|'meeting'|'upload'), source_file, audio_duration_seconds, transcript (JSON array), enhanced_content, enhancement_prompt, enhanced_at_content_hash, folder_id, space_id, calendar_event_id, participants, cloud_id, sync_status, deleted_at, created_at, updated_at` + FTS5 virtual table (`notes_fts`).
- `actions` (L331): `id, name, description, prompt, icon, is_builtin, sort_order`.
- `transcriptions` (L113): `id, text, raw_text, has_audio, audio_duration_ms, provider, model, status, route_kind, cloud_id, sync_status, ...`.
- Speaker/diarization tables (`speaker_profiles`, `speaker_mappings`, `note_speaker_embeddings`), calendar tables, `spaces`, `contacts`.

### 2.6 End-to-end flow (verified)

```
System/Mic audio → audioManager (250ms chunks) → [local whisper/parakeet | cloud /api/transcribe | streaming providers]
  → transcript segments → stored as notes.transcript JSON (meeting) or transcriptions table (dictation)
  → user opens note → clicks "Generate Notes" (ActionPicker)
  → runBackgroundAction → ReasoningService.processText (scope: noteFormatting, provider: cloud/local/BYOK)
  → updateNote({ enhanced_content, enhancement_prompt, enhanced_at_content_hash })
  → NoteEditor "enhanced" view renders markdown
```

### 2.7 OpenWhispr weaknesses (worth noting, not copying)

1. **Monolithic `ipcHandlers.js` (10.6K lines)** and `audioManager.js` (4.5K lines) — hard to maintain.
2. **No validation schema** on generated notes — `enhanced_content` is free markdown; nothing guarantees structure or grounding.
3. **No chunking** — very long transcripts are sent whole in a single-shot call (context risk).
4. **No job/queue/progress** — a long generation is a single awaiting HTTP call; the UI shows a spinner with no stage visibility.
5. **No versioning** — regenerating overwrites `enhanced_content` in place (hash-guard only).
6. Cloud server logic is **outside the repo** (hosted API) — the client can't be reasoned about end-to-end locally.

---

## 3. Phase 2 — Our Repository (Athenus) Architecture

### 3.1 What exists (verified)

- **Backend:** Python FastAPI monolith (`backend/app/main.py`), SQLite via SQLModel (`backend/app/infrastructure/db/models.py`). Routers in `backend/app/presentation/api/v1/` (media, chat, workspaces, graph, learning, analytics, agents, settings, system). Mounted in `main.py:194-204`.
- **Transcription:** Faster-Whisper via `FasterWhisperSTTAdapter` (`backend/app/infrastructure/adapters/whisper_adapter.py`), invoked by `TranscriptWorker` (`backend/app/services/workers/transcript_worker.py`) on `MediaUploadedEvent`. Output segments persisted as **timestamped `transcript_chunks`** (written by `embedding_worker.py` L223/L258 and `persistent_ingestion_queue.py` L402). This is the *canonical* chunk store that flashcards/quizzes read from via `load_chunks()`.
- **AI Service Bus:** `AIServiceBus` (`backend/app/domain/ai/service_bus.py`) with `get_text_capability()`, `get_stt_capability()`, `get_embedding_capability()`. Providers registered in `main.py`: ollama, openrouter, groq, openai, anthropic, custom OpenAI-compatible. `TextGenerationRequest` in `backend/app/domain/ai/capabilities.py`.
- **Structured-output generation pattern (THE template):** `FlashcardService.generate_deck()` (`flashcard_service.py:198`) and `QuizService.generate_quiz()` (`quiz_service.py:193`). Both:
  - Read concepts from `KnowledgeGraphService.get_concepts()` + timestamped chunks via `load_chunks()`.
  - Stage progress via `graph_service.upsert_artifact_job(...)` into the **`artifact_jobs`** table (`models.py:140-152`): `collect_context(20) → llm_generation(50) → persist(85) → ready(100)`.
  - Call the LLM with a **structured-output prompt** (`build_flashcard_prompt` in `flashcard_generation.py:27`, `build_quiz_prompt` in `quiz_generation.py`), parse JSON with `re.search(r"\{.*\}", ...) + json.loads` (`parse_llm_flashcards` `flashcard_generation.py:64`), and **fall back to a deterministic heuristic** when parsing fails (`generate_flashcards_heuristic`).
  - Persist immutable, **versioned** artifacts (`deck_{ws}_v{n}`), returning a cached `ready` artifact unless `force_new_version`.
  - Endpoints in `learning.py`: `POST /learning/decks/{ws}` (L195), `GET /learning/decks/{ws}` (L212), `GET /learning/decks/{ws}/status` (L218, returns `ArtifactJobStatusResponse` L133), `GET /learning/decks/{ws}/version/{v}` (L226), `GET /learning/decks/{deck}/cards` (L234). Quiz mirrors at L321-363.
- **Frontend:** Next.js + Zustand. `useAppStore` (`frontend/src/store/useAppStore.ts`) holds `activeView`, `activeWorkspaceId`, `activeMediaId`, `targetSeekSeconds`. `DesktopShell.tsx:54-61` routes views; `Sidebar.tsx` renders `NAVIGATION_CONFIG` (`frontend/src/config/navigation.ts`). **Flashcard UI** = `useFlashcards.ts` hook (`frontend/src/features/flashcards/useFlashcards.ts`) — `generateDeck()` (L176) POSTs with `force_new_version=true`, polls `/status` every 5s (L246-252), and `jumpToSource()` (L273) seeks the video player via `useAppStore.setState({ activeMediaId, targetSeekSeconds, activeView: 'view-video' })`. `formatSecondsToTimestamp` in `frontend/src/services/chatService.ts:45`.
- **Progress infra:** `artifact_jobs` table + `progress_store` + SSE `/media/{id}/stream` (`media.py:275`).
- **DB tables:** `workspaces`, `media_items`, `transcript_chunks`, `transcript_segments`, `chat_sessions/messages`, `knowledge_concepts/relations`, `artifact_jobs`, `flashcard_decks/cards/reviews`, `quizzes/questions/attempts`, analytics tables. **No `notes` table.**

### 3.2 Gaps (verified by grep)

- **No computer/system audio capture anywhere** — grep for `getUserMedia|MediaRecorder|getDisplayMedia|microphone|system audio` across `frontend`, `backend`, `src-tauri`: **zero matches**. `src-tauri/` contains no Rust source (config-only). Capture is only file upload (`POST /media/upload`, `media.py:43`).
- **No "notes" feature** — no `notes` table, no note service, no note UI.
- **No note-generation action** — but the flashcard/quiz generation machinery is a perfect, already-tested template.

---

## 4. Phase 3 — Architectural Comparison

| Area | OpenWhispr | Athenus | Gap / Recommendation |
|---|---|---|---|
| **Audio capture** | MediaRecorder (250ms chunks) + system-audio loopback in Electron main (`audioManager.js`) | **None** (file upload only) | **Create new.** Capture is the only genuinely missing capability. Options A/B/C in §5.1. |
| **Transcription** | whisper.cpp / Parakeet / cloud / realtime streaming, dual-channel meeting | Faster-Whisper via `FasterWhisperSTTAdapter` on upload | **Reuse as-is.** Athenus pipeline is simpler but sufficient; streaming/live not required for the basic flow. |
| **Transcript storage** | `notes.transcript` JSON array; `transcriptions` table | Timestamped `transcript_chunks` + `transcript_segments` (canonical) | **Reuse as-is.** `transcript_chunks` is *better* (timestamped, chunked, chunk-indexed) and feeds notes directly via `load_chunks()`. |
| **Note generation** | Single-shot synchronous LLM call, free-markdown output, in-place overwrite | N/A (flashcards/quizzes exist) | **Mirror the flashcard pattern** — versioned, staged, structured-output, heuristic fallback, cached. |
| **LLM integration** | `ReasoningService` + provider registry (8 providers) + inference scopes | `AIServiceBus` + `LLMProviderRegistry` (ollama/groq/openrouter/openai/anthropic/custom) | **Reuse as-is.** `get_text_capability()` is exactly what flashcard/quiz services use. |
| **Prompt management** | Hardcoded base prompts + user-editable DB `actions` table | Prompt builders in `flashcard_generation.py`/`quiz_generation.py` (Python f-strings) | **Extend.** Add `note_generation.py` prompt builder, same convention. |
| **Data models** | `notes` (content + transcript JSON + enhanced_content) | No notes; rich learning tables | **Create new.** `notes` + `note_sections` tables per §6. |
| **Backend/API** | IPC handlers + hosted cloud API (outside repo) | FastAPI routers | **Extend.** Add endpoints to existing `learning.py` (router already mounted). |
| **Async processing** | None for notes (synchronous await) | `artifact_jobs` + polling (flashcards) + SSE (`media.py:275`) | **Reuse the flashcard pattern** — synchronous generate endpoint + `artifact_jobs` progress + 5s frontend polling. No new infra. |
| **Frontend state** | Zustand stores (`noteStore`, `actionProcessingStore`) | Zustand `useAppStore` + per-feature hooks | **Extend.** New `useNotes.ts` hook + `view-notes` route in `DesktopShell.tsx`/`navigation.ts`. |
| **UI** | NoteEditor with raw/transcript/enhanced tabs; ActionPicker overlay | FlashcardGrid/QuizStudio with progress bars | **Create new.** `NotesView.tsx` rendering timestamped sections; reuse `[MM:SS]` badge + `jumpToSource` pattern. |
| **Error handling** | Per-note error events in `actionProcessingStore`; hash-based staleness guard | LLM-parse-failure → heuristic fallback; artifact status `failed` | **Reuse the flashcard fallback** (stronger). No hash guard needed given immutable versions. |

---

## 5. Phase 4 — Recommended Implementation for Athenus

### 5.1 The one decision that shapes scope: audio capture

Athenus has **no capture capability**. Three options:

- **Option A — "Notes from the library" (recommended baseline).** Generate notes from **already-transcribed media items** (uploaded video/audio/lecture). Zero new capture code; the entire flashcard-pattern backend + frontend works today. Best first milestone.
- **Option B — Browser capture (recommended when live capture is wanted).** Frontend uses `navigator.mediaDevices.getDisplayMedia({ video: true, audio: true })` or `getUserMedia({ audio })` → `MediaRecorder` → webm/opus blob → upload via existing `POST /media/upload` (`media.py:43`) → existing transcription + notes pipeline fully reused. Limitation: capture dies with the browser tab; no background/system-wide capture.
- **Option C — Native Tauri loopback capture.** Add Rust (`src-tauri/` currently has no Rust) with `cpal`/WASAPI loopback. Most robust but requires bootstrapping the entire Rust toolchain — defer until the feature proves valuable.

**Recommendation:** Ship **Option A** (notes from existing transcripts) as Phase 1; add **Option B** (browser capture) as a later phase. Skip C until there is product evidence it is needed.

### 5.2 Recommended architecture & data flow

```
[Uploaded video/audio] → (existing) Faster-Whisper → transcript_chunks (timestamped)
        |                                     |
        |                           (Option B later: browser MediaRecorder → POST /media/upload)
        v
User opens Notes view → clicks "Generate Notes"
  → POST /learning/notes/{workspace_id}?media_id=...&force_new_version=true
    → NoteService.generate_notes(workspace_id, media_id)
      → upsert_artifact_job(collect_context 20)   [artifact_type="notes"]
      → load_chunks(media_id) → build_notes_prompt(chunks) [structured JSON output]
      → AIServiceBus.get_text_capability().generate(TextGenerationRequest)   [LLM]
      → parse_llm_notes()  |  fallback: generate_notes_heuristic(chunks)
      → upsert_artifact_job(llm_generation 50 → persist 85)
      → persist note sections (immutable versioned note_note_{ws}_v{n})
      → upsert_artifact_job(ready 100)
  → GET /learning/notes/{workspace_id}/status   [frontend polls every 5s]
  → GET /learning/notes/{workspace_id}/latest   [full note + sections]
  → NotesView renders sections with [MM:SS] badges → click → jumpToSource()
```

### 5.3 Backend implementation

**New files:**
- `backend/app/domain/learning/note_generation.py` — `build_notes_prompt(chunks)` (mirror `build_flashcard_prompt`, `flashcard_generation.py:27`), `parse_llm_notes(text)` (`re.search(r"\{.*\}", text, re.DOTALL)` + `json.loads`, mirror `parse_llm_flashcards` L64), `generate_notes_heuristic(chunks)` (mirror `generate_flashcards_heuristic` L118). Prompt instructs the LLM to return **only a JSON object**:
  ```json
  { "title": "...", "sections": [ { "heading": "...", "body": "...", "start_time": 0.0, "end_time": 12.3, "source_chunk_ids": ["chunk_0"] } ] }
  ```
  Sections carry `start_time`/`end_time`/`source_chunk_ids` so the UI can render clickable `[MM:SS]` citations — reusing the existing citation UX.
- `backend/app/domain/learning/note_service.py` — `NoteService`, structurally cloned from `FlashcardService`:
  - Reuse `load_chunks(media_id, workspace_id)` (`flashcard_service.py:36`).
  - `_generate_with_llm(chunks)` — `ai_service_bus.get_text_capability()` + `TextGenerationRequest`; heuristic fallback on parse failure (mirror `flashcard_service.py:154-181`).
  - `generate_notes(workspace_id, media_id, force_new_version)` — mirror `generate_deck` (`flashcard_service.py:198-281`): staged `update_job()` via `graph_service.upsert_artifact_job(...)` (`flashcard_service.py:214-224`); cached `ready` note unless `force_new_version`; immutable `note_{ws}_v{n}`.
  - `_persist_note`, `get_note`, `list_notes`, `get_workspace_note`, `get_note_sections` — mirror retrieval `flashcard_service.py:436-482`.
  - Optionally feed `graph_service.get_concepts()` for concept-grounded headings (mirror `_concept_dicts` `flashcard_service.py:183`).

**Schema change:** one new table (`notes` + `note_sections`), see §6. **No schema change for progress** — `artifact_jobs.artifact_type` is a free string (`models.py:144`); reuse with `artifact_type="notes"`, `target_key=media_id`.

**API (extend `backend/app/presentation/api/v1/learning.py`, router already mounted in `main.py:200`):**
- `POST /learning/notes/{workspace_id}?media_id=...&force_new_version=true` → `NoteResponse` (mirror `create_deck`, L195-209).
- `GET /learning/notes/{workspace_id}` → `List[NoteResponse]` (mirror `list_decks`, L212).
- `GET /learning/notes/{workspace_id}/status` → reuses `ArtifactJobStatusResponse` + `_artifact_job_to_response` (L133-156).
- `GET /learning/notes/{workspace_id}/latest` → full note with sections (mirror `get_deck_version` L226 + `get_deck_cards` L234).

**Wiring:** add `note_service` to the module singletons and to `set_ai_service_bus()` (mirror `learning.py:22`, `learning.py:28-33`). `main.py` already calls `set_learning_ai_service_bus(ai_service_bus)` (L117-118) — no `main.py` change needed beyond nothing.

**Async:** none required. The generate endpoint is synchronous (like flashcards/quizzes) and returns immediately; the artifact job records progress that the frontend polls. This matches Athenus's existing "synchronous generate + artifact_jobs + polling" pattern — no Celery/ARQ/RQ, no new SSE/WebSocket needed. (SSE already exists for media ingestion if desired later.)

### 5.4 Frontend implementation

**New files:**
- `frontend/src/features/notes/useNotes.ts` — cloned from `useFlashcards.ts`:
  - DTOs: `NoteDTO` (id, title, version, status, media_ids, created_at), `NoteSectionDTO` (heading, body, start_time, end_time, source_chunk_ids), reuse `ArtifactJobStatusDTO` (`useFlashcards.ts:46-55`).
  - `generateNotes()` mirror of `generateDeck` (`useFlashcards.ts:176-201`): POST `/learning/notes/{ws}?media_id=...&force_new_version=true`, then refresh + select version.
  - `refreshNotes` / `refreshArtifactStatus`; 5s polling interval (`useFlashcards.ts:246-252`).
  - `jumpToSource(mediaId, seconds)` — exact mirror of `useFlashcards.ts:273-283` (`useAppStore.setState({ activeMediaId, targetSeekSeconds, activeView: 'view-video' })`).
- `frontend/src/features/notes/NotesView.tsx` — renders note sections; each section body renders `[MM:SS]` badges via `formatSecondsToTimestamp` (`chatService.ts:45-53`), clickable to seek. "Generate Notes" button + inline progress (stage/progress from artifact status) mirroring the flashcard studio UI.

**View routing / state:**
- `frontend/src/config/navigation.ts` — add `{ id: 'view-notes', label: 'Notes', icon: 'note_alt' }` under Strategy (or Knowledge).
- `frontend/src/components/layout/DesktopShell.tsx:54-61` — add `{activeView === 'view-notes' && <NotesView />}`.
- No new store needed; `useAppStore` already holds workspace/media/seek state.

**User interaction flow:**
1. User opens Notes view in a workspace → sees existing notes (or empty state).
2. Selects a media item (or "Generate Notes" for the active media) → button click.
3. Button enters `generating` state; `artifact_jobs` progress (stage + % from `/status`) shown inline (5s poll).
4. On completion → note version appears; sections render with `[MM:SS]` badges.
5. Clicking a badge seeks the video player to that timestamp.
6. "Regenerate" re-POSTs with `force_new_version=true` → new immutable version `vN+1`.

### 5.5 Data model

New tables (mirror `FlashcardDeckTable`/`FlashcardTable` at `models.py:154-199`):

```
notes                       note_sections
  id        str PK          id            str PK
  workspace_id str (idx)    note_id       str (idx) FK → notes.id
  media_id  str (idx)       workspace_id  str (idx)
  title     str             heading       str
  version   int             body          str
  status    str  (generating|ready|failed)
                            start_time    float
  media_ids str | null      end_time      float
  source_chunk_ids str|null source_chunk_ids str | null
  created_at / updated_at   chunk_index   int
                            created_at
```

Rationale: versioning mirrors the proven immutable-deck model (regenerate = new version, no in-place mutation); `note_sections` with timestamps/chunk provenance gives the `[MM:SS]` citation UX and grounding for future RAG. `artifact_jobs` reused as-is (`artifact_type="notes"`, `target_key=media_id`).

### 5.6 AI pipeline (transcript → notes)

```
Transcript (transcript_chunks, timestamped)
  ↓
Preprocessing: load_chunks(media_id) — canonical, deduped, timestamped
  ↓
No chunking needed for the LLM call itself when transcripts are moderate
  (flashcards/quizzes already send all chunks in one prompt; mirror that).
  For very long transcripts, a later enhancement can window/rotate chunks
  (mirror `_rotate_concepts_and_chunks`, flashcard_service.py:301).
  ↓
LLM Prompt: build_notes_prompt(chunks) → structured JSON contract
  ↓
Structured AI Output: { title, sections: [{ heading, body, start_time, end_time, source_chunk_ids }] }
  ↓
Validation: parse_llm_notes() (regex JSON extraction); heuristic fallback on failure
  ↓
Persistence: immutable note_{ws}_v{n} + note_sections rows
  ↓
UI: NotesView with [MM:SS] citations → click-to-seek
```

Multi-stage processing / summarization / cross-version chunking are **not necessary** for the core feature — the flashcard pattern already proves single-shot structured generation over all chunks works in this stack. Add chunk rotation only if long-media generation degrades.

### 5.7 Reuse vs. new code

| Component | Classification | Note |
|---|---|---|
| `load_chunks()` / `transcript_chunks` store | **Reuse as-is** | `flashcard_service.py:36` |
| `AIServiceBus.get_text_capability()` + `TextGenerationRequest` | **Reuse as-is** | `service_bus.py:37`, `capabilities.py` |
| `KnowledgeGraphService.upsert_artifact_job` / `get_artifact_job` | **Reuse as-is** | `knowledge_graph_service.py:421/463` |
| `ArtifactJobStatusResponse` + `_artifact_job_to_response` | **Reuse as-is** | `learning.py:133-156` |
| FlashcardService pattern (staged job, versioning, caching, rotation) | **Extend** | Clone structure into `NoteService` |
| Prompt/parse/heuristic convention (`flashcard_generation.py`) | **Extend** | New `note_generation.py` following same convention |
| `learning.py` router + `set_ai_service_bus` wiring | **Extend** | Add note endpoints |
| `models.py` SQLModel tables | **Extend** | Add `notes` + `note_sections` |
| `useFlashcards.ts` hook (polling, DTOs, jumpToSource) | **Extend** | Clone into `useNotes.ts` |
| `DesktopShell` / `navigation.ts` / `useAppStore` | **Extend** | Add `view-notes` route + view |
| `formatSecondsToTimestamp` + video seek | **Reuse as-is** | `chatService.ts:45`, `useAppStore` |
| `src-tauri/` Rust capture | **Do not build now** | No Rust exists; defer |
| OpenWhispr `ipcHandlers.js` monolith, `actions` table prompt system, cloud `/api/reason` | **Do not copy** | Athenus's router/service/structured-output pattern is superior for this codebase |

---

## 6. Phase 5 — Implementation Plan

### Phase 1 — Backend domain: note generation (no UI)

- **Objective:** `NoteService` + `note_generation.py`, testable standalone.
- **Files:** `backend/app/domain/learning/note_generation.py` (new), `backend/app/domain/learning/note_service.py` (new), `backend/app/domain/learning/entities.py` (add `Note`, `NoteSection`).
- **Implement:** `build_notes_prompt`, `parse_llm_notes`, `generate_notes_heuristic`, `NoteService.generate_notes` with staged `artifact_jobs`.
- **Dependencies:** existing `load_chunks`, `AIServiceBus`, `KnowledgeGraphService`.
- **Risks:** LLM JSON parse failures → heuristic fallback covers; empty workspace (no concepts) → allow notes to work from chunks alone (unlike flashcards, don't hard-require concepts).
- **Manual test:** `python -c "from app.domain.learning.note_service import NoteService; ..."` after seeding a media + transcript; or pytest.
- **DoD:** `NoteService.generate_notes` returns a versioned `Note` with sections; heuristic path works with no LLM; unit tests pass (`cd backend && python -m pytest tests`).

### Phase 2 — Backend schema + API

- **Objective:** persistence + endpoints.
- **Files:** `backend/app/infrastructure/db/models.py` (add `NoteTable`, `NoteSectionTable`), `backend/app/presentation/api/v1/learning.py` (add 4 endpoints + `note_service` singleton + `set_ai_service_bus` wiring).
- **Implement:** tables, `POST /learning/notes/{ws}`, `GET /learning/notes/{ws}`, `GET /learning/notes/{ws}/status`, `GET /learning/notes/{ws}/latest`.
- **Dependencies:** Phase 1; `init_db()` auto-creates tables (SQLModel).
- **Risks:** schema migration for existing DBs — `init_db()` creates missing tables; existing rows unaffected (new tables only).
- **Manual test:** upload media → wait for transcription → `curl -X POST "http://localhost:8000/api/v1/learning/notes/{ws}?media_id={m}"` → `curl /latest`.
- **DoD:** endpoints return `NoteResponse` with sections and `artifact_jobs` shows 20→50→85→100.

### Phase 3 — Frontend notes view

- **Objective:** "Generate Notes" UX.
- **Files:** `frontend/src/features/notes/useNotes.ts` (new), `frontend/src/features/notes/NotesView.tsx` (new), `frontend/src/config/navigation.ts`, `frontend/src/components/layout/DesktopShell.tsx`.
- **Implement:** DTOs, `generateNotes`, 5s status polling, section rendering with `[MM:SS]` badges + `jumpToSource`, "Regenerate" button.
- **Dependencies:** Phase 2.
- **Risks:** media-item selection UX (media dropdown per workspace); empty-state handling.
- **Manual test:** `cd frontend && npm run dev`, open Notes, generate, click a timestamp badge → video seeks.
- **DoD:** notes generate, show progress, render sections, badge-click seeks video; regenerate yields `v2`.

### Phase 4 — Live capture (optional, browser-first)

- **Objective:** computer/system audio capture → notes.
- **Files:** `frontend/src/features/notes/` or `frontend/src/features/capture/` (new `useAudioCapture.ts`), reuse `POST /media/upload`.
- **Implement:** `getDisplayMedia`/`getUserMedia` + `MediaRecorder` → webm/opus blob → existing upload endpoint → auto-transcribe → user clicks Generate Notes.
- **Dependencies:** Phase 3.
- **Risks:** browser-tab lifetime; system-audio capture requires `getDisplayMedia` (screen-share permission); format/container compatibility with Faster-Whisper (FFmpeg in pipeline handles it).
- **Manual test:** click "Record", speak/system audio, stop → transcript appears → Generate Notes.
- **DoD:** recorded audio produces a transcribed media item and a generated note.

### Phase 5 — Polish & analytics

- **Objective:** production hardening.
- **Implement:** emit `NoteGeneratedEvent` via `event_bus.publish` (mirror `flashcard_service.py:614-635`) so `AnalyticsService` can count note generations; add notes to `WorkspaceAnalyticsTable`; optional chunk-window rotation for very long transcripts.
- **Risks:** event-bus fan-out regressions — keep publish fire-and-forget.
- **DoD:** analytics reflect note generation; no regressions in `backend/tests`.

---

## 7. Key Facts Reference (cite-safe)

| Fact | Source |
|---|---|
| OpenWhispr note generation = synchronous single-shot LLM on note content + transcript JSON | `src/stores/actionProcessingStore.ts:110`, `src/services/ReasoningService.ts`, `src/components/notes/PersonalNotesView.tsx:767-824` |
| OpenWhispr `notes` table with `transcript`/`enhanced_content` | `src/helpers/database.js:194-235` |
| OpenWhispr audio capture = MediaRecorder 250ms chunks | `src/helpers/audioManager.js:106,1165` |
| Athenus canonical timestamped chunks | `backend/app/infrastructure/db/models.py:46`, `load_chunks` `flashcard_service.py:36` |
| Athenus flashcard generation template | `flashcard_service.py:198-281`, `flashcard_generation.py:27-191` |
| Athenus artifact progress infra | `models.py:140-152`, `learning.py:133-156` |
| Athenus frontend flashcard polling pattern | `frontend/src/features/flashcards/useFlashcards.ts:176-252` |
| Athenus has no audio capture | grep `getUserMedia|MediaRecorder|getDisplayMedia` → 0 matches |
| `src-tauri/` has no Rust source | `src-tauri/` directory inspection |