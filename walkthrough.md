# Quiz Submission Fix — WALKTHROUGH

## Overview

Fixed the "Failed to submit quiz results." error in the Quizzes tab. The root cause was an
API contract mismatch introduced in commit `a0fb981`: the frontend began POSTing quiz
submissions to a non-existent endpoint (`/learning/quizzes/container/{quiz_id}/attempts`)
with a mismatched payload and response shape, while the backend only exposes the tested
grading endpoint `POST /learning/quizzes/{quiz_id}/grade`. The frontend now calls the
existing backend endpoint and consumes the backend's response shape exactly.

## Files Modified

- `frontend/src/features/quiz/useQuiz.ts`
  - Restored `QuizAttemptDTO` to match the backend `QuizAttemptResponse` schema
    (`quiz_id`, `version`, `total_questions`, `correct_count`, `time_taken`, and the
    detailed per-question `answers` record).
  - `submitQuiz` now POSTs to `/api/v1/learning/quizzes/{quiz_id}/grade` (instead of the
    non-existent `/container/{quiz_id}/attempts`) and sends `time_taken` (instead of the
    never-supported `time_seconds`) in the request body.
- `frontend/src/features/quiz/QuizStudio.tsx`
  - Results panel updated to render the backend fields: `correct_count` of
    `total_questions` correct, elapsed time from `time_taken`, and progress bar width from
    `score` (already a 0–100 percentage).

## Implementation Details

- **Endpoint alignment:** The frontend now hits the only submission route the backend
  exposes, `POST /api/v1/learning/quizzes/{quiz_id}/grade` (learning.py:357), which calls
  `QuizService.grade_attempt` (quiz_service.py:491) and returns a 404-free 200 on success.
- **Payload alignment:** The body now uses `time_taken`, matching `GradeAttemptRequest`
  (learning.py:118-121); previously the backend would have silently defaulted elapsed time
  to `0.0`.
- **Response alignment:** The frontend DTO matches `QuizAttemptResponse` (learning.py:105-115),
  so the results panel renders real values instead of `undefined`/`NaN`.
- **Restored downstream effects:** Because submissions now succeed, attempts are persisted to
  `quiz_attempts` and `QuizAttemptEvent` is published, which `AnalyticsService` consumes to
  update `total_quiz_attempts`, `quiz_correct/quiz_attempts`, and `avg_quiz_score`.
- No backend changes were required; the existing grading contract and its tests are unchanged.

## Manual Testing Guide

Prerequisites: backend running, a workspace with extracted concepts, and a generated quiz
with at least one question loaded in the Quizzes tab.

1. **Open the Quizzes tab and load a quiz.**
   - Expected: Questions render with options; no error banner.

2. **Answer all questions** (click an option for each; use Next Question → to advance).
   - Expected: Each selection shows immediate correct/incorrect feedback and an explanation.

3. **On the last question, click Submit Quiz.**
   - Expected: No error banner. A results panel appears with a percentage score heading
     (e.g., "Quiz Complete — 67%"), a "X of Y correct" line, elapsed time, and a progress
     bar filled to the score percentage.

4. **Verify the score math.**
   - Expected: `X` equals the number of correct answers, `Y` equals total questions, and the
     displayed percentage equals `round(X / Y * 100)`.

5. **Verify elapsed time is recorded.**
   - Expected: The results panel shows the actual time spent (tens of seconds), not 0:00.

6. **Verify analytics updated.**
   - Go to the Analytics tab and check the mastery/quiz stats.
   - Expected: `Quiz attempts` increased by 1 and the workspace quiz score reflects the
     completed attempt. (Requires analytics refresh.)

7. **Regression: regenerate a quiz.**
   - Click Regenerate in the Quizzes tab.
   - Expected: A new version is generated, loads, and is submittable via the same flow.

8. **Edge case: empty answers.**
   - Submit a quiz without selecting options (or skip some) to confirm it still submits
     (ungraded questions count as incorrect).
   - Expected: Submission succeeds; correct count reflects only answered-correctly questions.

9. **Edge case: network/backend down.**
   - Stop the backend, then submit.
   - Expected: The existing "Failed to submit quiz results." error banner appears — this is
     the expected failure path, not the bug.

## Notes

- Assumption: `score` returned by the backend is the 0–100 percentage (set in
  `grade_attempt`), which the results panel already treats as a percentage.
- The frontend `next lint` script exists but no ESLint config is present in the repo, so
  lint cannot run; TypeScript `tsc --noEmit` passes for the modified files.
- Out of scope (not changed): adding a separate `/container/{quiz_id}/attempts` route,
  refactoring the results panel UI, or adding `passed`/`percentage` convenience fields to the
  backend response. The frontend contract is now fully aligned with the existing backend API.
