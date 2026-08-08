# Phased Implementation Plan — Local-First LLM Generation, Timeout Policy, Fallback Integrity & Artifact Regeneration

## Objective

Investigate and fix the current Athenus LLM generation and artifact regeneration issues while preserving the existing architecture and avoiding unnecessary complexity.

There are currently two major observations:

1. **Local Ollama generation is incorrectly subject to a short HTTP generation timeout**, causing valid but slow local inference to be treated as a failure.
2. **Artifact regeneration appears to produce duplicated content**, but investigation suggests this may be a downstream consequence of Ollama timing out and falling back to deterministic heuristic generation.

There is also a secondary issue involving duplicate completion/status messages during artifact generation.

The implementation must therefore proceed **incrementally**.

> **IMPORTANT: STOP AFTER EVERY PHASE.**
>
> Do not automatically continue to the next phase.
>
> At the end of each phase:
>
> 1. Show exactly what was changed.
> 2. Show the tests that were executed.
> 3. Show the results.
> 4. Explain what was validated.
> 5. Identify any remaining uncertainty.
> 6. Provide a concise manual QA checklist for me.
> 7. **STOP and wait for my approval before proceeding.**

---

# Core Architectural Principles

These principles should guide every phase.

### 1. Local-first means generation is not arbitrarily time-limited

A local LLM may take:

* 5 seconds
* 30 seconds
* 2 minutes
* 5+ minutes

depending on:

* model size
* hardware
* GPU availability
* prompt length
* output length
* concurrent workloads
* model loading time

Slow inference does **not** mean the provider is unavailable.

Therefore:

> **Athenus must not impose an arbitrary wall-clock timeout on AI generation.**

This applies to all AI-related generation, including but not limited to:

* Athenus Chat
* Quiz generation
* Quiz regeneration
* Flashcard generation
* Flashcard regeneration
* Other LLM-powered artifact generation
* Future local-model generation capabilities

### 2. Distinguish different timeout types

Do not blindly remove every timeout.

These are different concerns:

```text
Health / discovery timeout
        ↓
Short timeout is appropriate

Connection establishment timeout
        ↓
Reasonable timeout is appropriate

AI generation timeout
        ↓
No arbitrary wall-clock timeout

User cancellation
        ↓
Explicit mechanism for stopping generation
```

A health check should not hang indefinitely.

An LLM generation request, however, should remain active until:

* generation completes,
* the provider reports a genuine failure,
* the connection genuinely fails,
* or the user explicitly cancels the generation.

### 3. Provider adapters must report real failures

A provider adapter must not convert a genuine generation failure into fake successful-looking LLM text.

For example, this behavior is incorrect:

```text
Ollama generation fails
        ↓
catch exception
        ↓
return fake text:
"Local AI Response (Ollama Offline Fallback)..."
```

The provider layer should instead propagate a structured/real error.

If Athenus intentionally supports heuristic fallback generation, that decision must occur at the appropriate generation-service layer rather than being hidden inside the provider adapter.

### 4. Do not solve the regeneration problem prematurely

The current evidence suggests:

```text
Ollama
  ↓
10-second timeout
  ↓
fake fallback response
  ↓
LLM parsing fails
  ↓
heuristic generation
  ↓
similar/deterministic content
  ↓
v2 appears duplicated
```

Therefore:

> **Do not immediately implement complex anti-duplication prompts, concept rotation, or heuristic randomization.**

First fix the underlying LLM execution path and then re-test regeneration.

Only implement additional regeneration logic if duplication can still be reproduced after genuine LLM generation is confirmed.

---

# Current Evidence

## Ollama

Settings reports:

```text
Ollama Status
Connected v0.32.5

REST Latency
145 ms

Catalog Providers
5 Registered

Active LLM
OLLAMA

Test Connection:
OLLAMA: Available & Configured
Active Model: llama3:8b

Ollama
🟢 Configured
Discovered Models: 3
```

However, generation behaves differently.

### Athenus Chat

Input:

```text
this is a test. reply with hi
```

Current response:

```text
Local AI Response (Ollama Offline Fallback):
Processed request 'You are Athenus AI, an intelligent learn...'
```

### Quiz

```text
Artifact:
generating
llm generation
progress 50%
Generating questions with AI model...

Artifact:
ready
progress 100%
Quiz ready — generated with local fallback engine (LLM unavailable).
```

### Flashcards

```text
Artifact:
generating
llm generation
progress 50%
Generating cards with AI model...

Artifact:
ready
progress 100%
Deck ready.
```

Investigation found:

```text
Ollama health:
GET /api/version
GET /api/tags

Generation:
POST /api/generate
```

The adapter currently uses:

```text
httpx.AsyncClient(timeout=10.0)
```

Local inference using `llama3:8b` can exceed 10 seconds.

The resulting `ReadTimeout` is swallowed and converted into fallback text.

---

# PHASE 0 — Baseline & Scope Verification

## Goal

Before changing anything, establish the current behavior and verify the investigation findings against the actual code.

### Investigate

Trace:

```text
Athenus Chat
    ↓
AIServiceBus
    ↓
OllamaTextGenAdapter
    ↓
HTTP request
    ↓
Ollama
```

Also trace:

```text
Quiz generation
    ↓
AIServiceBus
    ↓
Ollama
    ↓
LLM parsing
    ↓
heuristic fallback
```

and:

```text
Flashcard generation
    ↓
AIServiceBus
    ↓
Ollama
    ↓
LLM parsing
    ↓
heuristic fallback
```

Confirm:

* active provider resolution
* active model resolution
* Ollama adapter usage
* timeout configuration
* exception handling
* fallback behavior
* artifact generation path

Also inspect regeneration:

* version calculation
* artifact identity
* previous artifact retrieval
* generation prompt
* persistence
* telemetry

### Do not modify code yet.

### Required output

Provide:

1. Confirmed dependency/request flow.
2. Exact files/functions responsible.
3. Confirmation or contradiction of the current RCA.
4. Any additional relevant findings.
5. Minimal proposed change for Phase 1.

### Automated validation

Run appropriate existing tests and import checks.

### Manual QA

Do not ask me to test anything yet if no changes were made.

### STOP

Wait for approval before Phase 1.

---

# PHASE 1 — Fix LLM Generation Timeout & Error Integrity

## Goal

Make local LLM generation compatible with local-first behavior.

### Required changes

#### A. Remove arbitrary generation timeout

Modify the Ollama adapter so generation does not fail merely because inference exceeds 10 seconds.

Do NOT simply change:

```text
10 seconds → 120 seconds
```

unless there is a specific technical reason.

Prefer separating:

```text
connection timeout
health-check timeout
generation read timeout
```

The generation read operation should be allowed to continue indefinitely or until explicit cancellation/provider failure.

Follow the existing HTTP/client architecture rather than introducing a new networking abstraction.

#### B. Preserve reasonable connection timeouts

Do not make health checks or TCP connection establishment infinite.

#### C. Remove fake successful responses

Remove behavior where Ollama exceptions are converted into dummy text such as:

```text
Local AI Response (Ollama Offline Fallback)...
```

A real provider failure should propagate as a real error.

#### D. Preserve intentional fallback behavior

If Quiz/Flashcard heuristic fallback is an intentional feature, do not remove it unless evidence shows it is harmful.

However, it must only activate after a genuine, explicit generation failure.

Do not allow fake fallback text to masquerade as an LLM response.

### Tests

Add or update tests for:

* generation exceeding 10 seconds
* successful Ollama generation
* Ollama connection failure
* Ollama HTTP failure
* Ollama generation exception
* no fake fallback text returned from the provider adapter
* intentional higher-level fallback behavior, if applicable

### Manual QA

I will verify:

#### Ollama Chat

Ask:

```text
this is a test. reply only with "hi"
```

Expected:

```text
hi
```

or a genuine model response.

It must NOT say:

```text
Ollama Offline Fallback
```

#### Ollama Quiz

Generate a quiz.

Expected:

```text
Generating questions with AI model...
        ↓
actual Ollama inference
        ↓
Quiz ready
```

It must NOT report:

```text
LLM unavailable
```

when Ollama successfully generated the response.

#### Ollama Flashcards

Same verification.

### STOP

Wait for manual QA approval before proceeding.

---

# PHASE 2 — Verify Provider/Model Consistency

## Goal

Confirm that fixing timeout behavior did not affect provider/model routing.

### Verify

For Ollama:

```text
Provider = OLLAMA
Model = llama3:8b
```

Confirm actual generation requests use that model.

Do not rely solely on UI state.

Trace/log the actual model passed to Ollama.

Then verify a cloud provider such as Groq.

Confirm:

```text
Settings selected provider
        ↓
AIServiceBus
        ↓
actual provider adapter
        ↓
selected model
```

### Important

Do not redesign provider architecture.

Do not change working cloud-provider behavior unless evidence requires it.

### Tests

Verify:

* Ollama chat
* Ollama quiz
* Ollama flashcards
* cloud chat
* cloud quiz
* cloud flashcards
* active model selection

### Manual QA

I will manually switch between:

```text
Ollama
Groq
```

and verify:

* Chat uses the selected provider.
* Quiz uses the selected provider.
* Flashcards use the selected provider.
* Selected model is respected.
* No unexpected fallback occurs.

### STOP

Wait for approval.

---

# PHASE 3 — Reproduce and Reassess Regeneration

## Goal

Determine whether the regeneration duplication bug still exists after fixing genuine LLM generation.

Do NOT implement anti-duplication logic yet.

### Test sequence

Create:

```text
Flashcards v1
```

Record:

* version
* artifact ID
* card count
* card contents

Then:

```text
Regenerate
```

Record:

* version
* artifact ID
* card contents
* generation path
* provider
* model

Repeat for Quiz.

### Determine

If:

```text
v1 ≠ v2
```

and both were genuinely generated by the LLM, then the previous duplication was likely caused by the timeout/fallback chain.

If:

```text
v1 == v2
```

despite genuine LLM generation, continue investigation.

### STOP

Do not automatically implement a fix.

Provide the evidence and wait for approval.

---

# PHASE 4 — Fix Genuine Regeneration Duplication Only If Still Reproducible

This phase is conditional.

Only proceed if Phase 3 demonstrates that independently generated LLM artifacts still produce duplicate or near-duplicate content.

## Investigate

Determine whether duplication originates from:

* identical prompts
* previous artifact being reused
* deterministic seed
* identical context selection
* concept rotation
* insufficient generation diversity
* artifact persistence
* version-specific state
* frontend displaying stale content

### Important distinction

Versioning and content generation are separate:

```text
Version correctness:
v1 → v2 → v3

Content independence:
v1 ≠ v2 ≠ v3
```

Verify both.

### Preferred implementation order

1. Fix incorrect artifact reuse.
2. Ensure a new artifact identity is created.
3. Ensure regeneration invokes the LLM again.
4. Ensure the generation context is correct.
5. Only then consider prompt-level novelty instructions.
6. Only if necessary consider deterministic heuristic variation.

Do not add randomness simply to hide a deeper bug.

### Manual QA

Verify:

```text
v1
↓
Regenerate
↓
v2
↓
Regenerate
↓
v3
```

Each version must:

* have a distinct artifact ID
* remain independently accessible
* contain independently generated content
* preserve the previous versions
* not merely copy previous content

### STOP

Wait for approval.

---

# PHASE 5 — Duplicate Completion/Telemetry Investigation

## Goal

Resolve the duplicate:

```text
Artifact:
ready
progress 100%
Deck ready.

Artifact:
ready
progress 100%
Deck ready.
```

### Investigate first

Determine whether duplication originates from:

```text
Backend job updates
        ↓
SSE
        ↓
Frontend hooks
        ↓
refreshArtifactStatus()
        ↓
UI
```

Determine whether the cause is:

* duplicate backend events
* duplicate SSE delivery
* duplicate polling/refresh
* frontend state handling
* toast + status UI representing the same event
* actual duplicate generation jobs

### Do not assume frontend is responsible.

### Implementation

Only modify the layer proven to be responsible.

Avoid broad event-system changes.

### Tests

Verify one generation produces:

```text
one job
one completion event
one final artifact state
```

### Manual QA

I will generate and regenerate:

* Quiz
* Flashcards

and verify the UI does not display duplicate completion states.

### STOP

Wait for approval.

---

# PHASE 6 — Final Regression Validation

Only after all previous phases have been individually approved.

## Automated tests

Run the complete relevant backend test suite.

At minimum:

```bash
pytest backend/tests/test_quiz.py
pytest backend/tests/test_flashcards.py
pytest backend/tests/test_knowledge_graph.py
```

Also run the full test suite if practical:

```bash
pytest
```

Verify:

* no import failures
* no provider regressions
* no generation regressions
* no artifact version regressions
* no telemetry regressions

## Manual QA Matrix

| Feature                | Ollama | Cloud Provider |
| ---------------------- | ------ | -------------- |
| Chat                   | ✅      | ✅              |
| Quiz generation        | ✅      | ✅              |
| Flashcard generation   | ✅      | ✅              |
| Quiz regeneration      | ✅      | ✅              |
| Flashcard regeneration | ✅      | ✅              |

For each:

* selected provider is respected
* selected model is respected
* generation is not artificially terminated
* genuine failures are visible
* intentional fallback behaves correctly
* no fake LLM responses appear
* artifacts are independently versioned
* completion state is displayed once

---

# Final Acceptance Criteria

The work is complete only when all of the following are true:

### Local-first generation

* Local LLM generation is not limited by an arbitrary wall-clock timeout.
* Slow inference is treated as valid inference.
* Health checks still have reasonable timeouts.
* Connection establishment still has reasonable timeouts.
* User cancellation remains the mechanism for intentionally stopping long generation.

### Provider integrity

* Ollama generation actually reaches Ollama.
* The selected Ollama model is actually used.
* Cloud providers continue working.
* Provider selection remains consistent across Chat, Quiz, Flashcards, and Settings.

### Error integrity

* Provider failures are not converted into fake successful LLM responses.
* Errors are observable and diagnosable.
* Intentional heuristic fallback only occurs through the appropriate higher-level generation logic.

### Regeneration

* v1 → v2 → v3 increments correctly.
* Each version has a distinct artifact identity.
* Previous versions remain intact.
* Regeneration invokes genuine generation.
* Regenerated content is independently generated.
* No unnecessary anti-duplication mechanisms are added if the timeout fix already resolves the issue.

### Telemetry

* One generation produces one authoritative completion state.
* Duplicate completion events are eliminated at their actual source.
* Progress remains accurate.

---

# Implementation Discipline

Throughout the entire implementation:

### DO

* Investigate before modifying.
* Make the smallest change that fixes the confirmed root cause.
* Reuse existing architecture.
* Preserve working cloud-provider behavior.
* Add regression tests around every confirmed bug.
* Provide evidence for conclusions.
* Stop after each phase.

### DO NOT

* Refactor unrelated architecture.
* Introduce a new DI framework.
* Replace the provider system.
* Rewrite the generation pipeline.
* Add arbitrary timeouts merely to make requests terminate.
* Add randomness to hide deterministic bugs.
* Add complex anti-duplication logic before proving duplication persists.
* Modify multiple layers when one layer is responsible.
* Continue to the next phase without manual QA approval.

## Most Important Rule

**Do not optimize for completing all phases quickly. Optimize for proving each root cause and making the smallest correct change.**

After each phase, stop and wait for my explicit approval.
