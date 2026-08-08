# Quiz Prompt Version Threading — WALKTHROUGH

## Summary

### Root cause
The `{version}` placeholder in the quiz generation prompt was dead in production.
`build_quiz_prompt()` accepts and correctly renders a `version` argument, but the
intermediate caller `QuizService._generate_with_llm()` never received or forwarded
the version computed upstream, so **every LLM generation prompt rendered "Quiz
Version 1"**, even on the 5th regeneration. A default argument (`version=1`) on
`build_quiz_prompt` masked the omission instead of failing loudly, so no test
caught it.

### What changed and why
- `_generate_with_llm()` now takes a required `version: int` parameter and forwards
  it to `build_quiz_prompt(..., version=version)`. Making it **required** (no
  default) means a future caller that forgets to pass version gets an immediate
  `TypeError` instead of silently regressing to "Quiz Version 1".
- `generate_quiz()` passes its already-computed `version` into
  `_generate_with_llm()`.
- `evolve_workspace_quiz()` now computes `new_version` **before** the LLM call and
  passes it through — the same dead-version bug existed on the auto-evolution path.
- Added an automated regression test asserting the rendered prompt carries the
  real version number.

This was a pure parameter-threading fix. No prompt text, schema, API contract, or
frontend behavior changed. Initial generation still renders "Quiz Version 1"
(unchanged), and the JSON output contract in the prompt is untouched.

### Files / lines touched
- `backend/app/domain/learning/quiz_service.py`
  - `_generate_with_llm()` signature — line 155 (now `version: int` required)
  - `build_quiz_prompt(..., version=version)` call — line 171
  - `generate_quiz()` → `_generate_with_llm(..., version=version)` — line 241
  - `evolve_workspace_quiz()` — `new_version` computed before call, passed through —
    lines 339-340 (removed duplicate `latest_version`/`new_version` computation at
    former lines 337-338)
- `backend/tests/test_quiz.py`
  - Added `FakeQuizCapability` / `FakeQuizBus` test doubles (lines 16-43)
  - Added `test_generation_prompt_carries_version` (lines 168-180)

## Manual testing steps

These steps exercise the real backend endpoint. Use a workspace that already has
concepts extracted (e.g. after processing a lecture), or seed one via the tests.

1. **Start the backend.**
   ```
   cd backend
   python -m uvicorn main:app --port 8000
   ```

2. **Capture prompts.** Add a temporary debug log inside
   `_generate_with_llm()` right after the prompt is built:
   ```python
   import logging
   logging.getLogger(__name__).debug("QUIZ_PROMPT_VERSION>>> %s", build_quiz_prompt(concepts, chunks, max_questions, version=version))
   ```
   Ensure debug logging is enabled for the module. (Remove this before merging.)

3. **Initial generation.** Trigger it for a workspace `WS`:
   ```
   curl -X POST "http://127.0.0.1:8000/api/v1/learning/quizzes/WS/generate"
   ```
   **Expected:** the logged prompt contains `Quiz Version 1`; the response JSON has
   `"version": 1` and `"status": "ready"`.

4. **First regeneration.** Force a new version:
   ```
   curl -X POST "http://127.0.0.1:8000/api/v1/learning/quizzes/WS/generate?force_new_version=true"
   ```
   **Expected:** the logged prompt contains `Quiz Version 2`; the response has
   `"version": 2`.

5. **Second regeneration.** Repeat the force-new-version call.
   **Expected:** the logged prompt contains `Quiz Version 3`; the response has
   `"version": 3`.

6. **Backward-compat check.** Start with a fresh workspace and run only the initial
   generation (step 3) — confirm the prompt still says `Quiz Version 1`.

7. **Remove the temporary debug logging** added in step 2 before merging.

## Validation checklist

- [ ] `cd backend && python -m pytest tests/test_quiz.py -q` — all pass, including
      the new `test_generation_prompt_carries_version`.
- [ ] `cd backend && python -m pytest tests/test_learning_evolution.py tests/test_flashcards.py tests/test_analytics.py -q` — pass (auto-evolution /
      `evolve_workspace_quiz` path not regressed).
- [ ] No other callers of `_generate_with_llm()` exist in `quiz_service.py` that
      omit `version` (grep: only lines 241 and 340, both pass it).
- [ ] `flashcard_service.py::_generate_with_llm` is a **separate** method (different
      signature, no `version`) — untouched, flashcards unaffected.
- [ ] `build_quiz_prompt()` unchanged; its `version=1` default remains (used by
      `tests/test_quiz.py::test_quiz_prompt_contains_concepts_and_chunks`).
- [ ] Heuristic fallback path unchanged — `generate_quiz_heuristic` still fires when
      the LLM returns no questions (it already received `version`).
- [ ] Initial generation behavior unchanged (renders "Quiz Version 1").

### Known pre-existing failure (unrelated)
`tests/test_learning_evolution.py::test_workspace_learning_settings_api` fails when
the full suite is run against the persistent SQLite DB. This is a pre-existing
test-isolation issue: the test PATCHes `auto_evolve_flashcards=True` into the
persistent `data/athenus.db`, and that state leaks into later runs, breaking the
"GET default settings is False" assertion. It fails identically with these changes
**stashed** (i.e. on clean `main`), confirming it is not caused by this work. It is
out of scope for this fix.

---

# Heuristic Fallback Notification — WALKTHROUGH

## Summary

### Root cause (context)
Quiz generation is LLM-first with a rule-based fallback. When
`_generate_with_llm()` yields no questions (no AI bus configured, offline LLM, or
unparseable response), `generate_quiz_heuristic()` silently takes over
(quiz_service.py:242-244). Previously nothing told the user that the fallback
engine was used — the artifact job just reported "Quiz ready."

### What changed and why
`generate_quiz()` now tracks whether the heuristic fallback executed and records
it in the artifact job's final message:

- `used_fallback = not questions` captures the fallback condition (line 242).
- The final `update_job("ready", ...)` message becomes
  `"Quiz ready — generated with local fallback engine (LLM unavailable)."` when
  the fallback ran, otherwise the unchanged `"Quiz ready."` (lines 253-257).

The frontend already polls `GET /learning/quizzes/workspace/{ws}/status` every 5s
and renders `artifact.message` in the always-visible artifact status bar
(`QuizStudio.tsx:111-113`), so the notice appears there automatically and
persists until the next generation. **No frontend, schema, or API changes.**

This is a backend-only, single-location change consistent with the existing
artifact-lifecycle design.

### Files / lines touched
- `backend/app/domain/learning/quiz_service.py`
  - `generate_quiz()` — `used_fallback` capture (line 242) and conditional
    "ready" message (lines 253-257)

## Manual testing steps

1. **Start the backend with the LLM unavailable** (e.g. Ollama daemon stopped):
   ```
   cd backend
   python -m uvicorn main:app --port 8000
   ```
2. **Trigger quiz generation** for a workspace `WS` with concepts extracted:
   ```
   curl -X POST "http://127.0.0.1:8000/api/v1/learning/quizzes/WS/generate"
   ```
3. **Check the artifact status:**
   ```
   curl "http://127.0.0.1:8000/api/v1/learning/quizzes/workspace/WS/status"
   ```
   **Expected:** `"status": "ready"` and `"message"` contains
   `generated with local fallback engine (LLM unavailable)`.
4. **Confirm the UI notice.** Open the Quizzes tab; the artifact status bar shows
   the fallback message.
5. **Regression — normal LLM path.** Restart the backend with the LLM available
   and regenerate (or generate on a fresh workspace).
   **Expected:** the status bar message is plain `Quiz ready.` — no fallback
   notice.

## Validation checklist

- [ ] `cd backend && python -m pytest tests/test_quiz.py -q` — all pass (incl.
      `test_generation_prompt_carries_version`).
- [ ] LLM-success path message unchanged (`Quiz ready.`).
- [ ] Fallback path message set only when `generate_quiz_heuristic` runs.
- [ ] No frontend files changed; the existing status-bar rendering surfaces the
      message.
- [ ] `evolve_workspace_quiz()` untouched (that auto-evolution path does not write
      artifact-job progress; out of scope).
