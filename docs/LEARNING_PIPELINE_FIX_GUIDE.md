# LEARNING_PIPELINE_FIX_GUIDE.md — Developer Step-by-Step Implementation Guide

This guide provides explicit, step-by-step developer instructions for fixing the three learning pipeline issues in **Athenus**:
1. Removing unwanted automatic Flashcard and Quiz generation upon video ingestion.
2. Implementing independent stage-based artifact progress tracking in SQLite and UI components.
3. Fixing version regeneration (`vN+1`) using concept & transcript chunk rotation instead of cloning previous version items.

---

## 📁 Key File Locations & Responsibilities

| Subsystem / Layer | File Path | Responsibilities |
|---|---|---|
| **Event Workers** | [`backend/app/services/workers/learning_evolution_worker.py`](file:///e:/repos/athenus/backend/app/services/workers/learning_evolution_worker.py) | Background worker listening to pipeline events (`ConceptGraphUpdatedEvent`). |
| **Database Schema** | [`backend/app/infrastructure/db/models.py`](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py) | SQLModel table definitions (`ArtifactJobTable`, `FlashcardDeckTable`, `QuizContainerTable`). |
| **Graph Service** | [`backend/app/domain/knowledge/knowledge_graph_service.py`](file:///e:/repos/athenus/backend/app/domain/knowledge/knowledge_graph_service.py) | Manages concept graph CRUD, triples, and `upsert_artifact_job` / `get_artifact_job` methods. |
| **Flashcard Engine** | [`backend/app/domain/learning/flashcard_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py) | Flashcard generation, SM-2 scheduling, card persistence, and deck versioning. |
| **Quiz Engine** | [`backend/app/domain/learning/quiz_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py) | Diagnostic quiz generation, distractor sampling, grading attempts, and quiz versioning. |
| **REST Router** | [`backend/app/presentation/api/v1/learning.py`](file:///e:/repos/athenus/backend/app/presentation/api/v1/learning.py) | FastAPI endpoints for flashcards, quizzes, and learning settings. |
| **Blueprint UI** | [`frontend/src/features/graph/KnowledgeGraphCanvas.tsx`](file:///e:/repos/athenus/frontend/src/features/graph/KnowledgeGraphCanvas.tsx) & [`useGraph.ts`](file:///e:/repos/athenus/frontend/src/features/graph/useGraph.ts) | Knowledge Graph canvas rendering and lifecycle status bar. |
| **Flashcards UI** | [`frontend/src/features/flashcards/FlashcardGrid.tsx`](file:///e:/repos/athenus/frontend/src/features/flashcards/FlashcardGrid.tsx) & [`useFlashcards.ts`](file:///e:/repos/athenus/frontend/src/features/flashcards/useFlashcards.ts) | Spaced repetition flashcard studio. |
| **Quiz Studio UI** | [`frontend/src/features/quiz/QuizStudio.tsx`](file:///e:/repos/athenus/frontend/src/features/quiz/QuizStudio.tsx) & [`useQuiz.ts`](file:///e:/repos/athenus/frontend/src/features/quiz/useQuiz.ts) | Comprehension quiz studio. |

---

## 🛠️ Step-by-Step Implementation Instructions

### Phase 1: Disable Unwanted Auto-Generation on Ingestion

#### 1. Edit `learning_evolution_worker.py`
Open [`backend/app/services/workers/learning_evolution_worker.py`](file:///e:/repos/athenus/backend/app/services/workers/learning_evolution_worker.py).
- In `handle_concept_graph_updated(self, event)`:
  - Remove or bypass the automatic calls to `self.flashcard_service.evolve_workspace_deck` and `self.quiz_service.evolve_workspace_quiz`.
  - When `ConceptGraphUpdatedEvent` arrives, the worker should update graph metrics and trigger `AnalyticsService` precomputation **ONLY**.
  - Flashcards and Quizzes must remain ungenerated until the user explicitly clicks the **Generate** button in their respective tab studios.

---

### Phase 2: Independent Stage-Based Lifecycle & Progress Tracking

#### 1. Verify `ArtifactJobTable` Schema in `models.py`
Open [`backend/app/infrastructure/db/models.py`](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py).
- Ensure `ArtifactJobTable` contains:
  ```python
  artifact_type: str = Field(index=True)  # "graph" | "flashcards" | "quiz"
  target_key: str = Field(index=True)     # media_id or workspace_id/deck_id/quiz_id
  status: str = "pending"                 # "pending" | "generating" | "ready" | "failed"
  stage: Optional[str] = "queued"         # "queued" | "collect_context" | "llm_generation" | "validation" | "persist" | "ready"
  progress: int = 0                       # 0 to 100 derived from stage
  message: Optional[str] = None
  error_message: Optional[str] = None
  ```

#### 2. Update `FlashcardService` Stage Telemetry
Open [`backend/app/domain/learning/flashcard_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py).
- In `generate_deck(workspace_id, ...)`:
  - At start: `graph_service.upsert_artifact_job(job_id=f"flashcards_{workspace_id}", workspace_id=workspace_id, artifact_type="flashcards", target_key=workspace_id, status="generating", stage="collect_context", progress=20, message="Collecting concepts and transcript chunks...")`
  - Before LLM call: update `stage="llm_generation"`, `progress=50`, `message="Generating cards with AI model..."`
  - Before persistence: update `stage="persist"`, `progress=85`, `message="Saving cards to database..."`
  - On completion: update `status="ready"`, `stage="ready"`, `progress=100`, `message="Deck ready."`

#### 3. Update `QuizService` Stage Telemetry
Open [`backend/app/domain/learning/quiz_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py).
- In `generate_quiz(workspace_id, ...)`:
  - Add stage progress updates to `ArtifactJobTable` for `artifact_type="quiz"` (`collect_context` $\rightarrow$ `llm_generation` $\rightarrow$ `persist` $\rightarrow$ `ready`).

#### 4. Update Frontend UI Hooks to Display Independent Artifact Jobs
- **Blueprint UI** ([`useGraph.ts`](file:///e:/repos/athenus/frontend/src/features/graph/useGraph.ts)): Reads `artifact` for `artifact_type="graph"` from `GET /api/v1/graph/workspace/{workspace_id}`.
- **Flashcards UI** ([`useFlashcards.ts`](file:///e:/repos/athenus/frontend/src/features/flashcards/useFlashcards.ts)): Add status query `GET /api/v1/learning/decks/{workspace_id}/status` to fetch the `"flashcards"` job state independently.
- **Quiz Studio UI** ([`useQuiz.ts`](file:///e:/repos/athenus/frontend/src/features/quiz/useQuiz.ts)): Add status query `GET /api/v1/learning/quizzes/workspace/{workspace_id}/status` to fetch the `"quiz"` job state independently.

---

### Phase 3: Version Regeneration with Concept & Chunk Rotation

#### 1. Fix Flashcard Version Regeneration in `flashcard_service.py`
Open [`backend/app/domain/learning/flashcard_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/flashcard_service.py).
- **Remove Card Copying**: In `evolve_workspace_deck` (lines 298–326), delete the loop copying `prev_cards` into `new_deck`.
- **Implement Concept & Chunk Rotation in `generate_deck`**:
  - When `force_new_version=True` is passed:
    1. Calculate `new_version = latest_version + 1`.
    2. Query all existing cards in `workspace_id` across prior deck versions (`v1`, `v2`, etc.).
    3. Count how many times each concept ID has been featured in existing cards.
    4. **Sort workspace concepts by lowest card coverage count first**.
    5. Sample transcript chunks starting from offset chunk indices to provide fresh transcript context to the LLM prompt.
    6. Pass the rotated concept subset and offset chunks to `_generate_with_llm`.
    7. Persist newly generated cards under `deck_id = f"deck_{workspace_id}_v{new_version}"`.
    8. Previous versions (`v1`, `v2`, etc.) remain preserved in SQLite untouched.

#### 2. Fix Quiz Version Regeneration in `quiz_service.py`
Open [`backend/app/domain/learning/quiz_service.py`](file:///e:/repos/athenus/backend/app/domain/learning/quiz_service.py).
- **Remove Question Copying**: In `evolve_workspace_quiz` (lines 274–300), delete the loop copying `prev_questions` into `new_quiz`.
- **Implement Concept Rotation in `generate_quiz`**:
  - When `force_new_version=True` is passed:
    1. Calculate `new_version = latest_version + 1`.
    2. Query existing quiz questions in `workspace_id` to count concept frequency in prior versions.
    3. **Select concept subset prioritizing concepts with lowest question coverage**.
    4. Pass rotated concepts and chunks to `_generate_with_llm`.
    5. Persist newly generated questions under `quiz_id = f"quiz_{workspace_id}_v{new_version}"`.
    6. Previous quiz versions remain preserved in SQLite untouched.

---

## 🧪 Verification Commands

After completing the code modifications, run the following test commands to verify your implementation:

```bash
# 1. Test Learning Evolution Worker boundaries
python -m pytest tests/test_learning_evolution.py

# 2. Test Knowledge Graph extraction and job state
python -m pytest tests/test_knowledge_graph.py

# 3. Test Flashcard generation, SM-2, and versioning
python -m pytest tests/test_flashcards.py

# 4. Test Quiz generation and versioning
python -m pytest tests/test_quiz.py

# 5. Test full backend suite
python -m pytest tests/

# 6. Verify Frontend Typecheck & Build
cd frontend
npm run build
```
