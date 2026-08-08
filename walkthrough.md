# Phased Implementation Walkthrough — LLM Generation, Provider Routing, and Artifact Regeneration

This document provides a comprehensive, living summary of the phased implementation for resolving LLM provider generation timeouts, error integrity, provider/model routing consistency, and artifact regeneration versioning across Athenus.

---

## Overview & Executive Summary

### Root Cause Summary
1. **Ollama Generation Timeout & Misleading Telemetry**:
   - Provider routing via `AIServiceBus` and `LLMProviderRegistry` correctly routes requests to `OllamaTextGenAdapter` when Ollama is selected.
   - Settings health checks use fast GET endpoints (`/api/version`, `/api/tags`) which respond in `<150ms`, correctly showing Ollama as Connected.
   - `OllamaTextGenAdapter` hardcoded a **10.0-second HTTP timeout** for generation POST requests (`/api/generate`). Local inference (e.g. `llama3:8b`) routinely takes 15–30+ seconds.
   - When the 10s timer expired, `httpx` raised a `ReadTimeout`. `OllamaTextGenAdapter` caught this silently and returned a fake text string: `"Local AI Response (Ollama Offline Fallback): Processed request..."`.
   - `QuizService` and `FlashcardService` failed JSON parsing on this fallback text string, triggering their internal heuristic generators and posting: `"Quiz ready — generated with local fallback engine (LLM unavailable)."`.

2. **Clean Dependency Injection**:
   - `learning.py` previously had a top-level import from `app.main`, creating a circular dependency. Replacing this with clean setter injection (`set_ai_service_bus(ai_bus)`) allows `app.main` to cleanly supply `AIServiceBus` without circular imports.

---

## Completed Phases

### Phase 0 — Baseline & Scope Verification

- **Goal**: Trace execution paths, confirm RCA against source code, and establish baseline unit test results without modifying source code.
- **Trace Findings**:
  - `Athenus Chat`: `query_chat` → `WorkspaceIntelligenceManager` → `AIServiceBus.get_text_capability()` → `OllamaTextGenAdapter.generate()`.
  - `Quiz Generation`: `generate_quiz` → `QuizService._generate_with_llm()` → `AIServiceBus.get_text_capability()` → `OllamaTextGenAdapter.generate()`.
  - `Flashcard Generation`: `generate_deck` → `FlashcardService._generate_with_llm()` → `AIServiceBus.get_text_capability()` → `OllamaTextGenAdapter.generate()`.
- **Baseline Tests Executed**:
  ```bash
  python -m pytest tests/test_quiz.py tests/test_flashcards.py tests/test_knowledge_graph.py
  ```
- **Baseline Results**: 36 passed in 3.06s (100% pass rate).

---

### Phase 1 — Fix LLM Generation Timeout & Error Integrity

- **Goal**: Align local Ollama LLM generation with local-first architectural principles by removing arbitrary generation read timeouts while preserving connection timeouts and eliminating fake fallback text responses.
- **Code Changes Made**:
  1. [`backend/app/infrastructure/adapters/ollama_adapter.py`](file:///e:/repos/athenus/backend/app/infrastructure/adapters/ollama_adapter.py):
     - Separated health check timeouts (`httpx.Timeout(5.0)`) from generation timeouts (`httpx.Timeout(timeout=None, connect=10.0)`).
     - Removed silent exception swallowing and fake fallback strings (`Local AI Response (Ollama Offline Fallback)...`).
     - Logged explicit warnings/errors and raised `RuntimeError` on genuine connection/POST failures.
  2. [`backend/tests/test_ollama_provider_adapter.py`](file:///e:/repos/athenus/backend/tests/test_ollama_provider_adapter.py):
     - Added unit tests (`test_ollama_text_gen_adapter_generate_success` and `test_ollama_text_gen_adapter_raises_on_failure`) verifying that successful generation returns real outputs and genuine failures raise `RuntimeError` rather than returning fake strings.
  3. [`backend/app/main.py`](file:///e:/repos/athenus/backend/app/main.py) & [`backend/app/presentation/api/v1/learning.py`](file:///e:/repos/athenus/backend/app/presentation/api/v1/learning.py):
     - Added `set_ai_service_bus(ai_bus)` setter to cleanly inject process-wide `AIServiceBus` into learning services, eliminating circular import warnings.

- **Automated Tests Executed**:
  ```bash
  python -m pytest tests/test_ollama_provider_adapter.py tests/test_quiz.py tests/test_flashcards.py tests/test_knowledge_graph.py
  ```
- **Results**: 41 passed in 6.70s.
- **Git Commit**: `05e2691` and `ac97927`.

#### Phase 1 Manual QA Checklist
1. **Ollama Chat**: Ask `this is a test. reply only with "hi"`. Verify that genuine model text is returned and **no** "Offline Fallback" message appears.
2. **Ollama Quiz**: Click **Generate Quiz** in Quiz Studio. Verify that Ollama completes generation and job message displays `Quiz ready` (without `LLM unavailable`).
3. **Ollama Flashcards**: Click **Generate Deck** in Flashcards Studio. Verify cards are generated using the active model.

---

### Phase 2 — Verify Provider/Model Consistency

- **Goal**: Confirm that fixing Ollama timeout behavior did not disrupt provider routing, and verify that active provider and active model selections are respected across Chat, Quiz, and Flashcards for both local and cloud providers.
- **Code Changes Made**:
  1. [`backend/tests/test_provider_routing_consistency.py`](file:///e:/repos/athenus/backend/tests/test_provider_routing_consistency.py):
     - Added test suite verifying:
       - Ollama provider resolution & `llama3:8b` model payload construction.
       - Cloud provider resolution (`groq`) & `llama-3.3-70b-versatile` model payload construction.
       - Active model override via `set_model("qwen3.6:latest")`.

- **Automated Tests Executed**:
  ```bash
  python -m pytest tests/test_provider_routing_consistency.py tests/test_ollama_provider_adapter.py tests/test_quiz.py tests/test_flashcards.py
  ```
- **Results**: 29 passed in 6.09s.
- **Git Commit**: `cdeeffc`.

#### Phase 2 Manual QA Checklist
1. **Switch Provider in Settings**: Change Active Provider to **Groq** (or OpenRouter/OpenAI with valid API key).
2. **Test Chat, Quiz & Flashcards with Cloud Provider**:
   - Send chat query `this is a test: reply with hi`. Verify response comes from Groq model.
   - Generate Quiz & Flashcards. Verify generation completes cleanly using Groq.
3. **Switch Back to Ollama**: Change Active Provider to **Ollama** (`llama3:8b`). Verify Chat, Quiz, and Flashcards route cleanly to Ollama.

---

## Upcoming Phases Roadmap

- **Phase 3 — Reproduce and Reassess Regeneration**:
  - Test Flashcards v1 → v2 and Quiz v1 → v2 regeneration under genuine LLM generation to determine if content duplication was a pure artifact of the timeout fallback.
- **Phase 4 — Fix Genuine Regeneration Duplication (Conditional)**:
  - If duplication persists under genuine LLM generation, implement version-aware novelty prompts or concept context offsets.
- **Phase 5 — Duplicate Completion / Telemetry Investigation**:
  - Streamline job status polling and SSE triggers to eliminate duplicate "Artifact ready" notifications in the UI.
- **Phase 6 — Final Regression Validation**:
  - Execute full test suite and verify end-to-end matrix across all local and cloud providers.
