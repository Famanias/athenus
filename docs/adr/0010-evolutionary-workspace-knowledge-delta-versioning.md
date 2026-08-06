# ADR 0010: Evolutionary Workspace Knowledge Delta Versioning

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: Previously, uploading a new lecture video into a workspace required users to manually trigger a full regeneration of flashcard decks and quizzes. Full regeneration wiped out or orphaned existing SM-2 spaced repetition review histories, resetting user study intervals to zero.
* **Decision**: Implement an **Evolutionary Workspace Knowledge Architecture** (`LearningEvolutionWorker`, `FlashcardService.evolve_workspace_deck`, `QuizService.evolve_workspace_quiz`). When new media is ingested, the system automatically detects newly introduced concepts, generates delta items specifically for those new concepts, and appends them to create an evolved `vN+1` artifact version while preserving 100% of existing SM-2 review histories, intervals, and attempt scores.
* **Alternatives Considered**:
  - *Full Wipe & Regenerate*: Simple to implement, but destroyed user spaced-repetition progress and review streaks.
  - *Separate Deck/Quiz Per Video*: Resulted in fragmented micro-decks rather than a unified workspace deck.
* **Rationale**: Learning is cumulative. Automatically evolving workspace decks and quizzes upon concept graph updates preserves user review momentum while seamlessly integrating newly indexed materials.
* **Trade-offs**: Requires background event listening (`ConceptGraphUpdatedEvent`) and state copying between artifact versions, but eliminates manual user maintenance.
