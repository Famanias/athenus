# ADR 0018: Version-Seeded Variation Engine & Physical Card Studio UX

## Status
Approved

## Context
During testing of Learning Studio (Flashcards & Quizzes), two issues were identified:
1. **Regeneration Duplication**: Clicking "Regenerate" created a new database version record (`vN+1`), but its cards/questions were identical to `vN` because heuristic extraction engines were 100% deterministic and ignored `version`.
2. **UI Clutter & Stale State**: Generating a deck/quiz required manual tab switching to see the new version, while flashcard backs were overcrowded with SM-2 numbers (`Ease`, `Ivl`) and 4 rating buttons.

## Decision
1. **Version-Seeded Variation Engine**:
   - Updated `generate_flashcards_heuristic` and `generate_quiz_heuristic` to accept `version: int = 1`.
   - Seeded pseudo-randomness (`random.Random(version * 37 + 101)`) in heuristic extractors to vary question templates, concept ordering, cloze sentence structures, and distractor shuffles across consecutive regenerations (`v1`, `v2`, `vN`).
2. **Studio UX & Physical Card Experience**:
   - Updated `useFlashcards.ts` and `useQuiz.ts` to invoke `selectVersion(deck.version)` and `loadQuiz(quiz)` immediately upon request completion, displaying a 4-second completion toast (`✅ Flashcards regenerated (Version X)`).
   - Redesigned card backs in `FlashcardGrid.tsx` to render clean physical card text (Front = Question, Back = Answer ONLY). Removed SM-2 numbers and rating buttons from primary grid view while preserving backend review API capabilities for future review session modes.
   - Simplified button label text to `'Regenerate'` and density dropdown labels to `Compact`, `Standard`, `Deep`. Removed misleading `⚡ Auto-Evolve` header checkboxes and set `auto_evolve_flashcards` / `auto_evolve_quizzes` backend defaults to `False`.

## Consequences
- **Positive**: Consecutive deck and quiz regenerations produce genuinely new, distinct content; UI updates automatically upon generation; physical card back is clean, readable, and free of metrics clutter.
- **Negative**: Spaced-repetition recall ratings are decoupled from the main grid view and deferred to dedicated study session modes.
