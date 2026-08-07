# UI/UX Review & Implementation Roadmap: Flashcards & Quizzes Experience

**Document Status:** Final Architecture Review & Implementation Plan (Approved Edition)  
**Date:** August 7, 2026  
**Target Component:** Athenus Learning Studio (Flashcards & Quiz Subsystems)  
**Author:** Antigravity AI  

---

## 1. Executive Summary

This roadmap provides a comprehensive analysis and incremental implementation plan to upgrade the **Flashcards** and **Quizzes** user experience in Athenus. 

Based on empirical code inspection across `useFlashcards.ts`, `useQuiz.ts`, `flashcard_service.py`, `quiz_service.py`, `FlashcardGrid.tsx`, and `QuizStudio.tsx`, we have diagnosed the root causes for UI stale state, version content duplication, button visual clutter, and card interface cognitive overload.

Our plan proposes low-risk, incremental milestones that preserve the underlying knowledge graph and SM-2 spaced repetition architecture while delivering a physical card experience.

---

## 2. Architecture Analysis

```
                                ATHENUS LEARNING STUDIO TOPOLOGY
                                
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                         DOMAIN KNOWLEDGE ENGINE                             │
  │     KnowledgeGraphService ──► ConceptImportanceAllocator ──► Chunks         │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                   On-Demand Generation Requests (force_new_version)
                                         │
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                 LEARNING SERVICES (flashcard_service / quiz_service)        │
  │  - Deck vN+1 & Quiz vN+1 Persistence                                         │
  │  - Single System of Record Telemetry Updates (ArtifactJobTable)             │
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                        SQLite Storage + REST Status Endpoints
                                         │
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                    REACT STUDIO HOOKS (useFlashcards / useQuiz)             │
  │  - Issue 1: Missing activeDeck / activeQuiz set on generation completion     │
  │  - Issue 2: Regeneration pipeline investigation (LLM vs Heuristic vs Cache)│
  └──────────────────────────────────────┬──────────────────────────────────────┘
                                         │
                                         ▼
  ┌─────────────────────────────────────────────────────────────────────────────┐
  │                    STUDIO UI (FlashcardGrid.tsx / QuizStudio.tsx)           │
  │  - Issue 3: Wording noise ("Generate v3" -> "Regenerate")                  │
  │  - Issue 5A: Minimal Physical Card Back (Question -> Answer ONLY)           │
  │  - Future 5B: Dedicated Study/Review Session Mode for SM-2 Ratings          │
  └─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Root Cause Analysis & Investigation Strategy

### RCA 1: UI Fails to Refresh Automatically After Generation
- **Empirical Evidence**: In [`useFlashcards.ts`](file:///e:/repos/athenus/frontend/src/features/flashcards/useFlashcards.ts#L152-L171) and [`useQuiz.ts`](file:///e:/repos/athenus/frontend/src/features/quiz/useQuiz.ts#L167-L186), `generateDeck()` and `generateQuiz()` execute `POST /learning/decks/{ws}?force_new_version=true` and then call `await refreshDecks()` and `await refreshArtifactStatus()`.
- **Confirmed Root Cause**: Neither hook invokes `selectVersion(newVersion)` or `setActiveDeck(newDeck)` / `loadQuiz(newQuiz)` upon request completion. Consequently, React local state (`activeDeck`, `cards`, `activeQuiz`, `questions`) remains pointing at the **previous version** until navigating away and back causes the component to unmount and run its initial `useEffect` fetch.

### Investigation 2: Regeneration Duplication Analysis
- **Observed Behavior**: Creating `v1`, `v2`, and `v3` produces identical cards/questions, even in multi-video workspaces.
- **Investigation Strategy**: Before proposing code changes, empirically trace:
  1. Whether `force_new_version=true` triggers a fresh LLM call vs heuristic generator vs returning cached SQL rows.
  2. Whether prompts and temperature settings are identical across runs.
  3. Whether LLM outputs are non-deterministic or fixed.
- 🛑 **Mandatory Guardrail**: *Do not implement regeneration logic changes until the root cause has been confirmed through logs and execution tracing.*

---

## 4. Current UX Evaluation & Proposed UX Improvements

| Dimension | Current UX Evaluation | Proposed UX Improvement |
|---|---|---|
| **Tab Refresh** | Stale UI requiring tab switching | Immediate state sync + completion toast (e.g. `✅ Flashcards regenerated (Version 3)`) |
| **Regeneration** | Duplicate versions across `v1..v3` | Empirical pipeline trace $\rightarrow$ targeted fix |
| **Button Wording** | Visual clutter (`Generate v3`) | Clean & concise button label (`Regenerate`) |
| **Card Face (5A)** | Overcrowded with SM-2 numbers and buttons | **Physical Card UX**: Front = Question, Flip = Answer ONLY |
| **Future Study Mode (5B)** | SM-2 ratings clutter primary grid | Future enhancement: Dedicated **"Study Session Mode"** for active recall practice |

---

## 5. Milestone-by-Milestone Implementation Plan

### Milestone 1 — Flashcards/Quizzes UI Refresh After Generation & Completion Toast

#### Proposed Solution
Update `generateDeck` in `useFlashcards.ts` and `generateQuiz` in `useQuiz.ts` to automatically invoke `selectVersion(newDeck.version)` and `loadQuiz(newQuiz)` upon receiving the generated artifact, displaying a 2-second completion banner (`✅ Flashcards regenerated (Version X)`).

#### Implementation Steps
1. In `useFlashcards.ts`:
   ```ts
   const created = await apiClient<FlashcardDeckDTO>(...);
   await refreshDecks();
   await refreshArtifactStatus();
   if (created?.version) {
     await selectVersion(created.version);
     setToastMessage(`✅ Flashcards regenerated (Version ${created.version})`);
   }
   ```
2. In `useQuiz.ts`:
   ```ts
   const created = await apiClient<QuizContainerDTO>(...);
   await refreshQuizzes();
   await refreshArtifactStatus();
   if (created) {
     await loadQuiz(created);
     setToastMessage(`✅ Quiz regenerated (Version ${created.version})`);
   }
   ```

---

### Milestone 2 — Regeneration Pipeline Investigation

#### Investigation Protocol
Trace `POST /api/v1/learning/decks/{ws}?force_new_version=true`:
1. Verify if `_generate_with_llm` or `generate_flashcards_heuristic` is executed.
2. Check LLM prompt logs to verify if temperature/seeds vary per version.
3. Formulate targeted fix based on empirical log findings.
> 🛑 *Do not implement regeneration logic changes until the root cause has been confirmed through logs and execution tracing.*

---

### Milestone 3 — Simplify the Regenerate Button

#### Proposed Solution
Update button label rendering in `FlashcardGrid.tsx` and `QuizStudio.tsx`.

#### Implementation Steps
1. In `FlashcardGrid.tsx`: Replace `{generating ? 'Generating...' : 'Generate v' + ((activeDeck?.version || 1) + 1)}` with `{generating ? 'Generating...' : activeDeck ? 'Regenerate' : 'Generate Deck'}`.
2. In `QuizStudio.tsx`: Replace `{generating ? 'Generating...' : 'Generate Quiz (v' + ...}` with `{generating ? 'Generating...' : activeQuiz ? 'Regenerate' : 'Generate Quiz'}`.

---

### Milestone 5A — Physical Card Experience (Minimal Card Back)

#### Proposed Solution
Redesign the back of flashcards in `FlashcardGrid.tsx` to display only the answer text in a clean, minimal physical card layout.

#### Implementation Steps
1. Render front (Question) $\rightarrow$ flip $\rightarrow$ back (Answer ONLY).
2. Remove SM-2 numbers (`Ease`, `Interval`), 4 rating buttons (`Again`, `Hard`, `Good`, `Easy`), and timestamp links from the primary grid view.

---

### Milestone 4 — Refine Auto-Evolve & Generation Settings UI

#### Technical Breakdown
- `auto_evolve_flashcards` / `auto_evolve_quizzes`: Workspace configuration flags governing background analytics updates.
- Target Budget (`~10`, `~20`, `~40`): Pagerank & graph centrality importance allocation per concept node.

---

### Future Enhancement — Dedicated Study & Spaced Repetition Session Mode (Future 5B)

#### Proposed Solution
Create an optional **"Study Session Mode"** modal/toggle where SM-2 recall rating buttons (`Again`, `Hard`, `Good`, `Easy`), ease factors, interval scheduling, and timestamp links are accessible for active recall practice.

---

## 6. Recommended Implementation Order

1. **Milestone 1**: UI Refresh After Generation & Completion Toast (Highest user impact, minimal risk).
2. **Milestone 2**: Regeneration Pipeline Investigation (Investigation before code changes).
3. **Milestone 3**: Simplify Button Labels (`Regenerate`).
4. **Milestone 5A**: Physical Card Experience (Clean Question $\rightarrow$ Answer back).
5. **Milestone 4**: Refine Auto-Evolve & Generation Settings UI.
6. **Future Enhancement**: Dedicated Study Session Mode (Future 5B).

# Implementation Plan — Learning Studio UI/UX & Regeneration Optimization

This implementation plan details the step-by-step execution to upgrade the **Flashcards** and **Quizzes** experience in Athenus based on [`FLASHCARDS_QUIZZES_UI_UX_ROADMAP.md`](FLASHCARDS_QUIZZES_UI_UX_ROADMAP.md).

---

## 📋 Recommended Implementation Order

1. **Milestone 1**: UI Refresh After Generation & Completion Toast (Highest user impact, minimal risk).
2. **Milestone 2**: Regeneration Pipeline Investigation (Empirically trace LLM vs Heuristic vs Caching).
3. **Milestone 3**: Simplify Button Labels (`Regenerate`).
4. **Milestone 5A**: Physical Card Experience (Clean Question $\rightarrow$ Answer back).
5. **Milestone 4**: Refine Auto-Evolve & Generation Settings UI.
6. **Future Enhancement**: Dedicated Study Session Mode (Future 5B).

---

## 🛠️ Milestone Details

### Milestone 1 — Flashcards/Quizzes UI Refresh & Completion Toast Banner
- **Target Files**: [`useFlashcards.ts`](file:///e:/repos/athenus/frontend/src/features/flashcards/useFlashcards.ts) & [`useQuiz.ts`](file:///e:/repos/athenus/frontend/src/features/quiz/useQuiz.ts)
- **Change**: Invoke `selectVersion(newDeck.version)` and `loadQuiz(newQuiz)` immediately after `POST` request completes, rendering a 2-second completion banner (`✅ Flashcards regenerated (Version X)`).

### Milestone 2 — Regeneration Pipeline Investigation
- **Target Files**: [`flashcard_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py) & [`quiz_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py)
- **Action**: Empirically trace LLM execution logs and prompt arguments for `v1`, `v2`, `v3` to determine why output is identical before proposing code fixes.
- 🛑 **Guardrail**: *Do not implement regeneration logic changes until the root cause has been confirmed through logs and execution tracing.*

### Milestone 3 — Simplify Regenerate Button Label
- **Target Files**: [`FlashcardGrid.tsx`](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx) & [`QuizStudio.tsx`](file:///e:/repos/athenus/frontend/src/features/quiz/QuizStudio.tsx)
- **Change**: Rename button label to `'Regenerate'` (or `'Generate Deck'` / `'Generate Quiz'` when empty).

### Milestone 5A — Physical Card Experience
- **Target File**: [`FlashcardGrid.tsx`](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx)
- **Change**: Render Question front $\rightarrow$ Answer back ONLY. Remove SM-2 numbers and 4 rating buttons from the main grid view.

### Milestone 4 — Refine Auto-Evolve & Generation Settings UI
- **Target Files**: [`FlashcardGrid.tsx`](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx) & [`QuizStudio.tsx`](file:///e:/repos/athenus/frontend/src/features/quiz/QuizStudio.tsx)
- **Change**: Clarify settings header labels (`Auto-Sync Concepts` & `Target Budget`).

### Future Enhancement — Dedicated Study Session Mode (Future 5B)
- **Target File**: [`FlashcardGrid.tsx`](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx)
- **Change**: Add an optional **"Study Mode"** toggle/modal where SM-2 recall rating buttons (`Again`, `Hard`, `Good`, `Easy`) and timestamps are accessible for active review practice.

---

## 🧪 Verification Plan

- Run backend test suite: `python -m pytest tests/test_flashcards.py` & `python -m pytest tests/test_quiz.py`.
- Run frontend type check: `npx tsc --noEmit`.
