# Implementation Plan — Fix Learning Pipeline Artifact Generation, Lifecycle Isolation & Version Regeneration

This document provides the architectural plan to fix three critical issues in the **Athenus Learning Pipeline**:
1. Stopping unwanted automatic generation of Flashcards and Quizzes upon video ingestion.
2. Isolating artifact status/progress tracking so each artifact (Blueprint, Flashcards, Quizzes, Analytics) owns an independent, stage-based lifecycle.
3. Fixing "Regenerate New Version" so it executes a fresh AI generation request with concept & chunk rotation instead of cloning existing output or relying on temperature tweaks.

---

## 🔍 Root Cause Analysis & Architectural Principles

### Issue 1: Incorrect Automatic Artifact Generation
- **Root Cause**: `LearningEvolutionWorker` ([`learning_evolution_worker.py`](file:///e:/repos/athenus/backend/app/services/workers/learning_evolution_worker.py)) subscribes to `ConceptGraphUpdatedEvent`. When concept graph extraction finishes after a video upload, `LearningEvolutionWorker` automatically triggers `flashcard_service.evolve_workspace_deck` and `quiz_service.evolve_workspace_quiz`.
- **Expected Behavior**: Video ingestion should automatically generate **ONLY**:
  - Blueprint (Knowledge Graph)
  - Analytics
  Flashcards and Quizzes must **NOT** be generated automatically. Users must explicitly trigger generation from their respective tabs.

### Issue 2: Stage-Based Independent Artifact Progress
- **Root Cause**: `ArtifactJobTable` in SQLite was only used for `"graph"` jobs by `GraphExtractionWorker`. `FlashcardService` and `QuizService` did not maintain dedicated `ArtifactJobTable` progress records.
- **Stage-Based Progress Metric**: Rather than hardcoding raw numbers (`10%`, `50%`, `90%`), progress will be driven by explicit semantic pipeline stages:
  - `QUEUED` / `PENDING` (Stage 1)
  - `COLLECT_CONTEXT` (Stage 2: concepts & chunks retrieval)
  - `LLM_GENERATION` (Stage 3: AI prompt execution)
  - `VALIDATION` (Stage 4: JSON schema & grounding verification)
  - `PERSIST` (Stage 5: SQLite write transaction)
  - `COMPLETED` / `READY` (Stage 6: 100%)

### Issue 3: Diversity via Concept & Chunk Rotation for Version Regeneration
- **Root Cause**: In `FlashcardService.evolve_workspace_deck` ([`flashcard_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py#L298-L326)) and `QuizService.evolve_workspace_quiz` ([`quiz_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py#L274-L300)), creating a new version `vN+1` explicitly iterated through previous cards/questions from `v1` and **cloned/copied all stored output from `v1` into `v2`**.
- **Educational Diversity Strategy**: When regenerating `vN+1`:
  - Keep LLM temperature stable for high quality.
  - Rotate concept selection (prioritize concepts with lower card/question coverage in prior versions).
  - Vary concept ordering & sample different transcript chunks across the workspace.
  - Never copy or clone previous version cards/questions into the new version.

---

## 🏗️ Proposed Changes

### Milestone 1: Fix Automatic Generation Boundaries (Problem 1)

#### [MODIFY] [learning_evolution_worker.py](file:///e:/repos/athenus/backend/app/services/workers/learning_evolution_worker.py)
- Remove automatic `ConceptGraphUpdatedEvent` auto-generation triggers for Flashcards and Quizzes during video ingestion.
- Ensure `ConceptGraphUpdatedEvent` updates Knowledge Graph topology and triggers `AnalyticsService` precomputation only.

---

### Milestone 2: Stage-Based Independent Artifact Progress (Problem 2)

#### [MODIFY] [models.py](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py)
- Ensure `ArtifactJobTable` tracks `stage` (`queued`, `collect_context`, `llm_generation`, `validation`, `persist`, `ready`, `failed`) for each `artifact_type` (`graph`, `flashcards`, `quiz`).

#### [MODIFY] [flashcard_service.py](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py) & [quiz_service.py](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py)
- Update `ArtifactJobTable` at each semantic stage (`collect_context` $\rightarrow$ `llm_generation` $\rightarrow$ `validation` $\rightarrow$ `persist` $\rightarrow$ `ready`).

#### [MODIFY] [graph.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/graph.py) & [learning.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/learning.py)
- Expose independent artifact lifecycle status endpoints for Blueprint (`/api/v1/graph/workspace/{id}`), Flashcards (`/api/v1/learning/decks/{workspace_id}/status`), and Quizzes (`/api/v1/learning/quizzes/workspace/{workspace_id}/status`).

#### [MODIFY] [KnowledgeGraphCanvas.tsx](file:///e:/repos/athenus/frontend/src/features/graph/KnowledgeGraphCanvas.tsx), [FlashcardGrid.tsx](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx), and [QuizStudio.tsx](file:///e:/repos/athenus/frontend/src/features/quiz/QuizStudio.tsx)
- Ensure each UI studio displays ONLY its own independent status, current stage name, and progress bar.

---

### Milestone 3: Fix Version Regeneration Engine (Problem 3)

#### [MODIFY] [flashcard_service.py](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py)
- Remove code block in `evolve_workspace_deck` / `generate_deck` that copies previous version cards into new versions.
- Implement concept & chunk rotation: select concepts with lowest prior coverage and vary chunk sampling for `vN+1`.

#### [MODIFY] [quiz_service.py](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py)
- Remove code block in `evolve_workspace_quiz` / `generate_quiz` that copies previous version questions into new versions.
- Implement fresh question concept rotation and chunk sampling for `vN+1`.

---

## 🧪 Verification Plan

### Automated Tests
- Run `pytest tests/test_knowledge_graph.py` to verify Knowledge Graph extraction and job progress.
- Run `pytest tests/test_flashcards.py` to verify on-demand deck generation and versioning without copying prior cards.
- Run `pytest tests/test_quiz.py` to verify on-demand quiz generation and versioning.
- Run `pytest tests/test_learning_evolution.py` to verify ingestion boundaries.
- Run frontend build `npm run build` to verify zero TypeScript errors.

### Manual Verification
1. Upload a new video in **Pipelines**: confirm that video ingestion automatically generates **only Blueprint and Analytics** (Flashcards & Quizzes remain ungenerated until requested).
2. Check **Blueprint tab**: confirm that artifact status displays Blueprint generation progress and stages independently without waiting for Flashcards/Quizzes.
3. Open **Flashcards tab**: click **Generate Deck** $\rightarrow$ verify fresh `v1` generation. Click **Regenerate New Version** $\rightarrow$ verify `v2` contains freshly generated cards via concept rotation rather than identical copies of `v1`.
4. Open **Quiz Studio**: click **Generate Quiz** $\rightarrow$ verify fresh `v1`. Click **Regenerate New Version** $\rightarrow$ verify `v2` contains freshly generated questions.
