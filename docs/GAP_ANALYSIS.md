# GAP_ANALYSIS.md — Athenus Implementation vs. Documented Specification

A line-referenced gap audit of what the codebase actually implements versus what the canonical documentation (`docs/CONTEXT.md`, `docs/AI_PIPELINE.md`, `docs/ROADMAP.md`, `docs/ARCHITECTURE.md`) claims is complete.

> **Bottom line**: `docs/CONTEXT.md` declares "Version 1.0 Final Release Complete (Phases 1 through 5 fully implemented and verified)." The code does not support that claim. The **4-stage video ingestion pipeline** is genuinely finished. The **8-Stage Layered Retrieval pipeline** is roughly **55–65%** complete: stages 4, 5, and 8 are real; stage 3 is partial; stages 1, 2, 6, and 7 are missing or simplified. Several Phase 4/5 worker & agent surfaces are **hard-coded stubs**, not functional AI.

---

## 1. Legend

| Symbol | Meaning |
|---|---|
| ✅ | Implemented and wired into the live path |
| 🟡 | Partially implemented (thin/simplified or heuristic version of the spec) |
| ❌ | Not implemented (missing) or a hard-coded stub that does no real work |

---

## 2. The 8-Stage Layered Retrieval Pipeline (`MultiStageRetriever`)

Canonical spec: `docs/AI_PIPELINE.md:74-92`, `docs/ARCHITECTURE.md:69`.
Implementation: `backend/app/infrastructure/retrieval/multi_stage_retriever.py`

| # | Stage | Status | Evidence (file:line) | Gap Detail |
|---|-------|--------|----------------------|------------|
| 1 | Query Rewrite & HyDE | 🟡 / ❌ | `multi_stage_retriever.py:63-64` | **Stub.** `ctx.rewritten_query = f"{query} (Context: educational video breakdown)"`. No LLM rewrite, no HyDE document generation. Spec (`AI_PIPELINE.md:85`) calls for reformulation for "higher semantic recall." |
| 2 | Intent Detection | ❌ | (grep: no intent/detect code under `backend/`) | **Not implemented at all.** No detection of timestamp-lookup vs. explanation vs. quiz vs. summary intent. Spec: `AI_PIPELINE.md:86`. |
| 3 | Workspace / Context Injection | 🟡 | `multi_stage_retriever.py:67`, `:78-82`, `:104-166` | **Partial.** Playback timestamp context, `media_id`/`workspace_id` filters, and selected-text injection work well. But the full "attach active workspace & media ID parameters" is not applied to graph traversal scoping. |
| 4 | Knowledge Graph Traversal | ✅ | `multi_stage_retriever.py:71` → `knowledge_graph_service.py` | Real `get_workspace_triples(workspace_id)` returned and injected into the prompt. |
| 5 | Hybrid Search (Vector + BM25) | ✅ | `multi_stage_retriever.py:74-89`; `qdrant_adapter.py`; `bm25_retriever.py:15-58` | Genuine dense Qdrant cosine search merged with real BM25 scoring. |
| 6 | Cross-Encoder Re-Ranking | 🟡 / ❌ | `reranker.py:6-30` | **Not a cross-encoder.** It is a keyword-overlap + weighted-frequency heuristic (`overlap * 0.3`, `base_score * 0.4`, `bm25_score * 0.3`). No neural cross-encoder model. Spec: `AI_PIPELINE.md:91`. |
| 7 | Context Compression | 🟡 / ❌ | `multi_stage_retriever.py:170-179` | Only formats `[MM:SS - MM:SS]` badges. Spec says "removes redundant sentences while retaining exact timestamp bounds" (`AI_PIPELINE.md:92`). No redundancy removal. |
| 8 | Grounded Prompt Assembly | ✅ | `multi_stage_retriever.py:181-193` | Grounded prompt with timestamp citations + KG triples + playback context. |
| — | Streaming LLM response (spec `IMPLEMENTATION_PLAN.md:92`) | ❌ | `chat.py:135-176` (`@router.post("/chat/query")`) | **Non-streaming.** Single `await text_capability.generate(...)`; no `stream` path. Spec explicitly requires "streaming LLM responses." |

**Retrieval readiness estimate: Stage 4 ✅, Stage 5 ✅, Stage 8 ✅, Stage 3 🟡, Stage 6 🟡, Stage 7 🟡, Stage 1 🟡, Stage 2 ❌. → ~55–65% complete.**

---

## 3. Video Ingestion Pipeline (4 stages) — VERIFIED COMPLETE ✅

Spec: `docs/AI_PIPELINE.md:15-70`, `docs/FRONTEND_SUMMARY.md:64`.
Frontend mapping: `frontend/src/features/ingestion/useIngestion.ts:20-25`.

| Stage | Status | Evidence |
|-------|--------|----------|
| Audio Extraction (FFmpeg 16kHz) | ✅ | `infrastructure/media/ffmpeg_extractor.py` |
| Speech-to-Text (Faster-Whisper) | ✅ | `transcript_worker.py`, `adapters/whisper_adapter.py` |
| Semantic Chunking | ✅ | `domain/knowledge/chunker.py` |
| Vector Indexing (Qdrant) | ✅ | `embedding_worker.py`, `adapters/qdrant_adapter.py` |
| SSE real-time progress | ✅ | `useIngestion.ts:52-124`, `progress_store.py` |

**Verdict:** Fully baked and wired into the live `/api/v1/media/upload` → SSE path.

---

## 4. Workspace & Multi-Session (Phase 2) — VERIFIED COMPLETE ✅

| Capability | Status | Evidence |
|-----------|--------|----------|
| Workspace CRUD + active | ✅ | `application/services/workspace_service.py`; `api/v1/workspaces.py` |
| Multi-session lazy chat | ✅ | `chat.py:77-133`, `session_service.py` |
| Vector workspace isolation | ✅ | `qdrant_adapter.py` (Qdrant `Filter must` + in-memory list fallback) |

---

## 5. Knowledge Graph (Phase 3) — BACKEND ✅ / FRONTEND PLACEHOLDER

| Area | Status | Evidence | Gap |
|------|--------|----------|-----|
| KG service + SQLite persistence | ✅ | `knowledge_graph_service.py` | — |
| Keyframe sampling (FrameExtractor) | 🟡 | `infrastructure/media/frame_extractor.py` | Exists as infrastructure; **not wired into ingestion** nor to OCR. |
| Slide OCR / multimodal embedding | ❌ | (no OCR adapter in `infrastructure/adapters/`) | Spec (`ROADMAP.md:74-76`) calls for PaddleOCR / Florence-2. **Absent.** |
| Graph visualizer UI | 🟡 | `frontend/features/graph/KnowledgeGraphCanvas.tsx:7-134` | Is a **static SVG-like mock grid**, not a real interactive graph canvas. Docs `ROADMAP.md: Phase B` mark this unimplemented. |

**Note:** `frontend/src/features/graph/useGraph.ts`, `flashcards/useFlashcards.ts:17-39`, `quiz/useQuiz.ts` call mock/hardcoded endpoints (e.g. `useFlashcards.ts:21` fetches `FLASH/learning/flashcards` — a route that does not exist; the real route is `/learning/flashcards/{media_id}` with hard-coded data).

---

## 6. Active Recall / Learning Tools (Phase 4) — ❌ HARD-CODED STUBS

| Surface | Status | Evidence | Gap Detail |
|---------|--------|----------|------------|
| QuizWorker | ❌ | `quiz_worker.py:13-36` | **Hard-codes a single static question** ("What is the core principle of Local-First AI architectures?") regardless of media content (`quiz_worker.py:24-27`). No AI generation. |
| FlashcardWorker | ❌ | `flashcard_worker.py:13-28` | **Hard-codes one static Q&A card** ("What distance metric..."). No content-derived cards. |
| SummaryWorker | ❌ | `summary_worker.py:13-26` | Prompts the LLM but **does not persist/ingest the result**; event `SummaryGeneratedEvent` has no subscriber. |
| `GET /learning/quizzes/{media_id}` | ❌ | `learning.py:25-39` | **Stub route** returns a hardcoded quiz, ignoring media content. |
| `GET /learning/flashcards/{media_id}` | ❌ | `learning.py:41-50` | **Stub route** returns a hardcoded single flashcard. |
| Anki SM-2 export | ❌ | `entities.py` (learning) only defines models | No `.apkg` generation exists. Docs `ROADMAP.md: Phase C` mark unimplemented. |
| Flashcards UI | 🟡 | `FlashcardGrid.tsx:8-98` | Render exists but data layer is a placeholder. |

---

## 7. Agentic AI Suite (Phase 5) — ❌ HARD-CODED STUBS

| Agent | Status | Evidence | Gap |
|-------|--------|----------|-----|
| PlannerAgent | ❌ | `specialized_agents.py:4-19` | Returns a **static 3-item plan list**; never calls retriever or quiz tools (`required_tools()` declared at :10-11 but never exercised). |
| RetrieverAgent | ❌ | `specialized_agents.py:21-31` | Returns **hardcoded** "Context retrieved successfully"; never invokes `MultiStageRetriever`. |
| CitationValidatorAgent | ❌ | `specialized_agents.py:33-43` | Returns **hardcoded** `{"citations_valid": True, "confidence": 0.98}` constant; never validates anything. |
| `POST /agents/coordinate` | 🟡 | `agents.py:28-43` | Wires the coordinator but the underlying agents are stubs above; produces no real output. |
| AgentCoordinator loop | ❌ | `agent_coordinator.py` | Docs (`architecture-review-842026.md:155-174`) require an **iterative** `while task_not_complete and steps < max_steps` loop; **not present** — single-pass only. |

---

## 8. Evaluation Subsystem — 🟡 PARTIAL

| Capability | Status | Evidence | Gap |
|-----------|--------|----------|-----|
| RAGEvaluator | ✅ | `evaluator.py:7-38` | Precision@5 / Recall@5 / groundedness implemented. |
| Citation groundedness | 🟡 | `evaluator.py:40-49` | **Phrase-overlap heuristic**, not citation-accuracy validation. |
| `@k=10` benchmark support | ❌ | `evaluator.py:18` | Hard-codes `k = min(5, ...)`; docs `IMPLEMENTATION_PLAN.md:117` require Retrieval P/R at `k=5,10`. |
| Generate real measurements on live pipeline | ❌ | (no harness) | No end-to-end benchmark that runs real queries against the live stack. |

---

## 9. Frontend "Unimplemented / Placeholder" Tabs

From `frontend/src/config/navigation.ts` and `components/layout/DesktopShell.tsx`.

| View | Nav badge | Status | Evidence |
|------|-----------|--------|----------|
| `view-video` | Active | ✅ Real | `VideoWorkspace.tsx`, `PersistentMediaPlayer.tsx` |
| `view-chat` | Active | ✅ Real | `ChatWorkspace.tsx` |
| `view-ingestion` (Pipelines) | Active | ✅ Real | `UploadDropzone.tsx` |
| `view-dashboard` (Library) | — | ✅ Real | `LibraryGrid.tsx` |
| `view-graph` (Blueprint) | `v0.3` (soon) | 🟡 Placeholder | `KnowledgeGraphCanvas.tsx` (mock grid, see §5) |
| `view-flashcards` | `v0.4` (soon) | 🟡 Placeholder | `FlashcardGrid.tsx` (data stub) |
| `view-quiz` (Quizzes) | `v0.4` (soon) | 🟡 Placeholder | `QuizStudio.tsx` (data stub) |
| `view-analytics` | — | ❌ **Fallback "Under Construction"** | Not handled in `DesktopShell.tsx:57` → renders the generic placeholder. |

Frontend `/analytics`, flashcards-quiz ↔ real/contract mismatch: the frontend hosts dovetail with **hard-coded stub endpoints**, so these tabs will render empty/mock data even with a running backend.

---

## 10. Summary of Gaps Requiring Work

Ordered by impact (highest first):

1. **Intent Detection (retrieval Stage 2)** — ❌ missing entirely.
2. **Query Rewrite / HyDE (retrieval Stage 1)** — current_implementation is a string-templating stub.
3. **Cross-Encoder re-ranking (Stage 6)** — ✓ Heuristic only; no cross-encoder model.
4. **Context compression (Stage 7)** — ✓ Formatting only; not too semantic redundancy removal.
5. **Streaming chat response** — ❌ non-streaming single request/response (`chat.py`).
6. **Learning OS (Phase 4)**: Quiz/Flashcard/Summary workers & `/learning/*` endpoints are **hard-coded stubs**; no real AI generation, no Anki `.apkg` export.
7. **Agentic suite (Phase 5)**: Planner/Retriever/Citation agents are **stubs**; no iterative coordinator loop.
8. **OCR / slide multimodal ingestion (Phase 3)**: FrameExtractor exists but is detached; no OCR adapter; no multimodal embeddings.
9. **Analytics dashboard (Phase E)** — view-analytics renders "Under Construction"; no backend.
10. **Frontend/Contract drift** — `useFlashcards.ts:21` calls non-existent route; quiz/flashcard/graph UI wired to modular stub data.
11. **Evaluation subsystem** — supports `k`=5 only, no live-benchmark integration, citation check is heuristic.

---

## 9. Repo documentation that overstates actual completeness
- `docs/CONTEXT.md:39` ("Version 1.0 Final Release Complete... fully implemented and verified") — **not accurate** per the audit above.
- `docs/ROADMAP.md:18-47` marks many features ✅ that are actually stub/placeholder.
- `docs/FRONTEND_SUMMARY.md` describes modules as "complete" while several are `-"soon"` placeholders.

> Suggested next action: update `CONTEXT.md` to reflect the true state (ingestion complete, retrieval partial, learning/agentic/eval in-progress), then treat retrieval stages 1, 2, 6, 7 and the learning/agentic stubs as def-refinable "MVP-complete → MVP-> full" backlog.
</parameter>
</invoke>