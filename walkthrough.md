# Walkthrough — Learning Pipeline Fix (Artifact Generation, Lifecycle Isolation & Version Regeneration)

This walkthrough documents the implementation of the plan in [`implementation_plan.md`](implementation_plan.md),
following the step-by-step guide in [`docs/LEARNING_PIPELINE_FIX_GUIDE.md`](docs/LEARNING_PIPELINE_FIX_GUIDE.md).

It covers: (1) what changed and why, (2) the edge cases handled, and (3) a manual testing table
so the fix can be verified end-to-end in the running app.

---

## 1. Implementation Summary

Three issues were fixed in the learning pipeline:

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | Flashcards & Quizzes were auto-generated on every video ingestion | `LearningEvolutionWorker` subscribed to `ConceptGraphUpdatedEvent` and called `evolve_workspace_deck` / `evolve_workspace_quiz` | Worker now refreshes **Analytics only**; artifact generation is strictly on-demand from each studio tab |
| 2 | Only the graph artifact tracked progress; flashcards/quizzes had no lifecycle | `ArtifactJobTable` was only written by `GraphExtractionWorker`; `FlashcardService` / `QuizService` never maintained job records | Added a `stage` column and independent `status` endpoints + UI bars per artifact |
| 3 | "Regenerate New Version" cloned `v1` output into `v2` | `evolve_*` copied every previous card/question into the new version | `force_new_version` now runs a **fresh generation** with concept & transcript-chunk rotation |

---

## 2. Changes by File

### Phase 1 — Disable unwanted auto-generation

| File | Change |
|------|--------|
| `backend/app/services/workers/learning_evolution_worker.py` | Rewritten. `handle_concept_graph_updated` now calls `analytics_service.handle_graph_updated(event)` **only**. Removed `flashcard_service` / `quiz_service` wiring, the `DeckEvolvedEvent` / `QuizEvolvedEvent` publishing, and the settings-driven evolve branches. Skips work when `new_concept_ids` is empty (e.g. duplicate upload). |

### Phase 2 — Independent stage-based lifecycle & progress

| File | Change |
|------|--------|
| `backend/app/infrastructure/db/models.py` | `ArtifactJobTable` gained `stage: Optional[str] = "queued"` (`queued \| collect_context \| llm_generation \| validation \| persist \| ready`) in both the SQLModel and SQLAlchemy fallback definitions. |
| `backend/app/infrastructure/db/session.py` | Added migration: `ALTER TABLE artifact_jobs ADD COLUMN stage VARCHAR DEFAULT 'queued'` for existing SQLite DBs. |
| `backend/app/domain/knowledge/knowledge_graph_service.py` | `upsert_artifact_job(..., stage=None, ...)` now persists `stage` (keyword arg inserted after `status`). |
| `backend/app/domain/learning/flashcard_service.py` | `generate_deck` reports job stages via `flashcards_{workspace_id}`: `collect_context`(20) → `llm_generation`(50) → `persist`(85) → `ready`(100). See Phase 3 for the rotation logic. |
| `backend/app/domain/learning/quiz_service.py` | `generate_quiz` reports job stages via `quiz_{workspace_id}`: `collect_context`(20) → `llm_generation`(50) → `persist`(85) → `ready`(100). See Phase 3. |
| `backend/app/services/workers/graph_extraction_worker.py` | `_update_job` now sets `stage` (`collect_context` → `llm_generation` → `validation` → `ready` / `failed`). |
| `backend/app/presentation/api/v1/learning.py` | New independent status endpoints returning `ArtifactJobStatusResponse` (status, stage, progress, message, error_message, updated_at): `GET /api/v1/learning/decks/{workspace_id}/status` and `GET /api/v1/learning/quizzes/workspace/{workspace_id}/status`. Returns `null` when no job exists. |
| `backend/app/presentation/api/v1/graph.py` | `ArtifactLifecycleDTO` now includes `stage`. |
| `frontend/src/features/flashcards/useFlashcards.ts` | New `artifact` state + `refreshArtifactStatus()` polling `GET /api/v1/learning/decks/{workspace_id}/status` every 5s; `autoGenerate` default flipped to `false`. |
| `frontend/src/features/quiz/useQuiz.ts` | New `artifact` state + `refreshArtifactStatus()` polling `GET /api/v1/learning/quizzes/workspace/{workspace_id}/status` every 5s; `autoGenerate` default flipped to `false`. |
| `frontend/src/features/graph/useGraph.ts` | `ArtifactLifecycle` interface now includes `stage`. |
| `frontend/src/features/flashcards/FlashcardGrid.tsx` | Renders an independent Flashcards artifact status bar (status, stage, progress, message + progress fill). |
| `frontend/src/features/quiz/QuizStudio.tsx` | Renders an independent Quiz artifact status bar (status, stage, progress, message + progress fill). |
| `frontend/src/features/graph/KnowledgeGraphCanvas.tsx` | Blueprint status bar now also displays the current `stage`. |

### Phase 3 — Version regeneration with concept & chunk rotation

| File | Change |
|------|--------|
| `backend/app/domain/learning/flashcard_service.py` | Removed the loop in `evolve_workspace_deck` that cloned `prev_cards` into the new deck (previous versions stay untouched). In `generate_deck`, when `force_new_version=True` and `version > 1`, `_rotate_concepts_and_chunks()` is used: prior cards are counted per concept (`_concept_coverage`), concepts are sorted **lowest-coverage first** and the top 12 selected, and transcript chunks are rotated by a version-based offset (`chunks[offset:] + chunks[:offset]`). |
| `backend/app/domain/learning/quiz_service.py` | Same treatment for quizzes: removed the question-cloning loop in `evolve_workspace_quiz`; `generate_quiz` rotates toward least-covered concepts and version-offset chunks when `force_new_version=True`. |
| `backend/tests/test_learning_evolution.py` | Added `test_learning_evolution_worker_analytics_only` — asserts `ConceptGraphUpdatedEvent` triggers analytics precomputation and that the worker no longer owns `flashcard_service` / `quiz_service`. |

---

## 3. Edge Cases Handled

| Edge Case | Behaviour |
|-----------|-----------|
| **Duplicate video upload / no new concepts** | `ConceptGraphUpdatedEvent` with empty `new_concept_ids` → worker returns early, no analytics churn. |
| **No concepts indexed** | `generate_deck` / `generate_quiz` raise `ValueError` → API returns `404` with message; frontend shows "Failed to generate... Ensure concepts have been extracted." |
| **No transcript chunks** | `load_chunks` returns `[]`; rotation `offset` guards on `len(chunks)` so no crash, heuristic generation still runs from concepts only. |
| **Fewer concepts than the rotation cap** | `ranked[:12] or ranked` keeps all concepts rather than emitting an empty subset. |
| **Single version / first generation** | `force_new_version` with `version == 1` uses the standard `concept_dicts[:12]` + full chunk list (rotation only kicks in for `vN+1`). |
| **LLM unavailable** | `_generate_with_llm` returns `[]` → deterministic heuristic fallback produces cards/questions so generation never fails hard. |
| **Cached deck/quiz** | Calling without `force_new_version` returns the existing ready `vN` (immutable), no new rows, no job churn. |
| **Prior versions** | `v1..vN` rows and their cards/questions are never mutated or deleted; only the new `vN+1` is written. |
| **Existing SQLite DBs** | Auto-migration adds the `stage` column on boot (`session.py`); fresh DBs get it from `create_all`. |
| **Status endpoint with no job yet** | Returns `null`; frontend renders `Artifact: idle` at `progress 0%`. |
| **Graph vs Flashcards/Quiz job keys** | Graph jobs use `target_key = media_id` (per-media, existing contract); flashcard/quiz jobs use `target_key = workspace_id` (per-workspace). `get_artifact_job(workspace_id, artifact_type, target_key=...)` disambiguates correctly. |
| **Flashcard/Quiz job id collisions** | Job ids are namespaced (`flashcards_{workspace_id}`, `quiz_{workspace_id}`), so they never collide with graph jobs (`graph_{media_id}`). |
| **Route ordering** | New `/learning/decks/{workspace_id}/status` and `/learning/quizzes/workspace/{workspace_id}/status` routes use distinct literal segments and do not shadow existing `.../version/{v}` or `.../cards` routes. |
| **Frontend auto-generation** | `autoGenerate` defaults flipped to `false`; opening the Flashcards/Quiz tabs with no artifact shows the empty state with a **Generate** button instead of auto-creating `v1`. |
| **Known pre-existing test flakiness** | `test_workspace_learning_settings_api` PATCHes a fixed workspace id into the shared `data/athenus.db`, so a **second** consecutive suite run may see `flashcard_target_budget_per_media == 30` instead of `20`. Unrelated to this change; passes on a clean DB. |

---

## 4. Automated Verification

Run from `backend/` using the project venv (`sqlmodel` is required — the system Python falls back to the pure-SQLAlchemy models):

```bash
venv\Scripts\python.exe -m pytest tests/test_learning_evolution.py     # ingestion boundaries
venv\Scripts\python.exe -m pytest tests/test_knowledge_graph.py        # graph extraction + job state
venv\Scripts\python.exe -m pytest tests/test_flashcards.py             # deck gen, SM-2, versioning
venv\Scripts\python.exe -m pytest tests/test_quiz.py                   # quiz gen + versioning
venv\Scripts\python.exe -m pytest tests/ -q                            # full backend suite (115 passed)
```

Frontend typecheck & build:

```bash
cd frontend
npm run build
```

> Note: run the suite from a clean DB state (`test_ws_evolution_1.settings_json = NULL`) to avoid the
> pre-existing settings-state pollution described above.

---

## 5. Manual Testing Table

Prerequisites: backend running (`python app/main.py`), frontend running (`npm run dev` or `npm run build` + Tauri),
one workspace created, and at least one video ingested so the Blueprint is generated.

| # | Task | How to Do It | Expected Behaviour |
|---|------|--------------|--------------------|
| 1 | Upload a new video in **Pipelines** | Open Pipelines → upload a lecture video → wait for ingestion to finish | Only **Blueprint (Knowledge Graph)** and **Analytics** are produced automatically. **No** flashcards or quizzes are generated. |
| 2 | Blueprint artifact lifecycle | Open the **Blueprint** tab during ingestion, then after it completes | Status bar shows `generating` → `collect_context`/`llm_generation`/`validation` stages and progress %, finishing at `ready · 100%`. Works independently of flashcards/quizzes. |
| 3 | Flashcards remain ungenerated | Open the **Flashcards** tab with no deck present | Empty state is shown ("No Flashcards in Active Deck") with a **Generate Deck** button. No `deck_v1` row is auto-created. |
| 4 | Generate flashcard deck `v1` | Click **Generate Deck** | Fresh `v1` is created: status bar goes `collect_context → llm_generation → persist → ready`, card grid populates, header shows `Deck v1 · N cards`. |
| 5 | Regenerate new flashcard version | Click **Generate v2** | A new `deck_v2` row is created via a **fresh generation with concept/chunk rotation** — not a copy of `v1`. Previous `v1` remains in the version selector untouched. |
| 6 | Verify `v2` is not a clone | Select `v1` then `v2` in the version selector and compare cards | Card fronts/backs and concept coverage differ (least-covered concepts are prioritized); deck ids differ. |
| 7 | Flashcards artifact status isolation | While a deck is generating, watch the Flashcards tab status bar | Only the Flashcards job progresses; the Blueprint and Quiz bars are unaffected. |
| 8 | Generate quiz `v1` | Open **Quiz Studio** → click **Generate Quiz** | Fresh `v1` is created; status bar reaches `ready`; quiz runner loads questions with instant feedback. |
| 9 | Regenerate new quiz version | Click **Generate v2** | A new `quiz_v2` is created with concept rotation (lowest prior coverage first). `v1` remains preserved. |
| 10 | Quiz artifact status isolation | Watch the Quiz Studio status bar during generation | Only the Quiz job progresses; other artifact bars are unaffected. |
| 11 | Cache reuse (no forced regen) | Re-open the Flashcards tab / reload Quiz Studio without clicking Generate | The existing ready `vN` is returned — no duplicate versions, no new generation job. |
| 12 | No-concepts guard | Delete all concepts for a workspace (or use an empty workspace), then click **Generate Deck / Generate Quiz** | Request fails with `404 No concepts indexed for workspace ...` and the UI shows the failure error message. |
| 13 | LLM unavailable fallback | Turn off the local Ollama model, then generate a deck/quiz | Heuristic generation takes over — a valid deck/quiz is still produced. |
| 14 | Status endpoint with no job | Open network tab and call `GET /api/v1/learning/decks/{ws}/status` on a fresh workspace | Response is `null`; the UI renders `Artifact: idle · progress 0%`. |
| 15 | Prior versions preserved | Generate `v1`, `v2`, then select `v1` | `v1` still shows all original cards; review history is untouched. |

---

## 6. Verification Notes

- **Backend suite:** 115/115 passing (114 pre-existing + 1 new worker-boundary test).
- **Frontend build:** `next build` compiles cleanly with zero TypeScript errors.
- The `frontend/next-env.d.ts` file is a build artifact and was restored to HEAD after building; it may be rewritten by `next build` locally.
