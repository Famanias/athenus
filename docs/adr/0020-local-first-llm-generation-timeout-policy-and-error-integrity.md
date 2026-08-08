# ADR 0020: Local-First LLM Generation Timeout Policy & Error Integrity

- **Status**: Accepted
- **Date**: 2026-08-08
- **Author**: Antigravity AI
- **Deciders**: Athenus Engineering Team

## Context

Local LLM text generation via Ollama was previously subject to a hardcoded 10.0-second HTTP read timeout in `OllamaTextGenAdapter`. Because local CPU/GPU inference for complex prompts (e.g. Quiz and Flashcard generation or long Chat responses) routinely exceeds 10 seconds, `httpx` raised a `ReadTimeout`.

The adapter silently caught this exception and returned a fake success string:
`"Local AI Response (Ollama Offline Fallback): Processed request..."`.

This resulted in two major architectural regressions:
1. Downstream services (`QuizService` and `FlashcardService`) failed JSON parsing on the fake fallback text string and silently dropped into deterministic heuristic fallback generation, displaying misleading messages (`"generated with local fallback engine (LLM unavailable)"`) despite Ollama being active and connected.
2. Artifact regeneration (`force_new_version=True`) repeatedly invoked the deterministic heuristic generator, causing version `v2` to duplicate version `v1` content.

## Decision

We implemented a **Local-First LLM Generation Timeout Policy & Error Integrity Architecture**:

1. **Separation of Timeout Concerns**:
   - **Health Checks & Discovery**: Fast GET endpoints (`/api/version`, `/api/tags`) use a strict 5.0-second timeout (`httpx.Timeout(5.0)`).
   - **TCP Connection Establishment**: Protected by a 10.0-second connection timeout (`connect=10.0`).
   - **Generation Read Timeout**: Generation POST requests (`/api/generate`) set `timeout=httpx.Timeout(timeout=None, connect=10.0)`. Local inference is allowed unlimited execution time without artificial wall-clock cancellation.

2. **Error Integrity**:
   - Removed code in `OllamaTextGenAdapter.generate()` and `stream()` that swallowed exceptions and returned fake fallback text strings.
   - Genuine HTTP or connection failures log explicit warnings/errors and raise a structured `RuntimeError` exception.

3. **Higher-Level Heuristic Fallbacks**:
   - `QuizService` and `FlashcardService` fall back to heuristic generators only when a genuine exception or error is raised.

4. **Circular Import Removal via Setter Injection**:
   - Removed direct import `from app.main import ai_service_bus` from `learning.py`.
   - Added `set_ai_service_bus(ai_bus)` in `learning.py` invoked during `app.main` composition boot.

## Consequences

- **Local-First Compliance**: Local model generation runs to completion without arbitrary 10s cancellation.
- **Accurate Telemetry**: Eliminates misleading "Offline Fallback" messages when Ollama is running cleanly.
- **Artifact Regeneration Integrity**: Regeneration (`force_new_version=True`) invokes active LLM generation, producing distinct, non-duplicated `v2` artifacts.
