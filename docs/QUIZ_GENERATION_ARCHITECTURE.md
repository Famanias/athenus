# Quiz Generation & Regeneration Architecture

Read-only analysis of the prompt templates and LLM orchestration used for quiz
generation and regeneration. No code was modified.

## Overview

- Quiz generation is **LLM-first with a rule-based heuristic fallback**.
- There is **only one prompt template**. Initial generation and regeneration
  reuse the exact same `build_quiz_prompt`. Regeneration differs only in
  orchestration (cache bypass + context rotation), never in prompt text.
- No JSON-schema / tool / `response_format` parameter is passed to the LLM; the
  output contract is expressed in the prompt text and enforced post-hoc by a
  parser.

## File references

| Concern | File | Function / line |
|---|---|---|
| Prompt template (single, shared) | `backend/app/domain/learning/quiz_generation.py` | `build_quiz_prompt()` lines **28-63** |
| Response parser | `backend/app/domain/learning/quiz_generation.py` | `parse_llm_quiz()` lines **66-102** |
| Heuristic fallback engine | `backend/app/domain/learning/quiz_generation.py` | `generate_quiz_heuristic()` lines **112-191** |
| LLM dispatch | `backend/app/domain/learning/quiz_service.py` | `_generate_with_llm()` lines **155-173** |
| Generation / regeneration orchestration | `backend/app/domain/learning/quiz_service.py` | `generate_quiz()` lines **175-247** |
| Concept/chunk rotation (regeneration context) | `backend/app/domain/learning/quiz_service.py` | `_rotate_concepts_and_chunks()` lines **267-288**, `_concept_coverage()` lines **249-265** |
| API entry (both flows) | `backend/app/presentation/api/v1/learning.py` | `generate_quiz()` line **312** |
| Frontend triggers | `frontend/src/features/quiz/useQuiz.ts` | initial: line **264**; regenerate: lines **230-233** |

Dispatch chain:
`learning.py:312` → `QuizService.generate_quiz()` → `_generate_with_llm()` →
`AIServiceBus.get_text_capability()` (service_bus.py:37-70) → active provider
adapter `.generate(TextGenerationRequest(prompt=...))`.

## Which model is used

The model is resolved at runtime from the active provider:

- **Default provider:** Ollama (local daemon at `http://localhost:11434`),
  default model **`llama3:8b`** (`backend/app/core/config.py:37`). Overridable
  via the `selected_ollama_model` DB setting (ollama_adapter.py:48-60).
- **Hot-swappable cloud providers** (registered in `main.py:49-82`, selected via
  Settings → persisted `default_llm` in SQLite):
  - OpenRouter → `google/gemini-2.5-flash`
  - Groq → `llama-3.3-70b-versatile`
  - OpenAI → `gpt-4o-mini`
  - Anthropic → `claude-3-5-sonnet-latest`

Active provider resolution: `AIServiceBus.get_text_capability()` →
`LLMProviderRegistry.get_active_provider()` → `config_resolver.get_active_provider_id()`
→ DB `default_llm`, falling back to `.env LLM_PROVIDER` (`ollama`).

## Generation prompt specification

The prompt is a **single string** (system role + instructions + context all in
`prompt`; `system_prompt` is `None`, so providers receive everything as one user
prompt).

Exact template (`quiz_generation.py:37-63`):

```
You are a comprehension-quiz author for an educational video transcript.

Create {max_questions} novel, concept-balanced Quiz Version {version} comprehension questions that are:
- Grounded in the provided concepts and transcript chunks (distractors must be plausible but incorrect).
- Formulated from fresh angles (e.g. application scenarios, analytical relationships, or key definitions).
- Answerable ONLY from the transcript material.

Respond with ONLY a JSON object in exactly this shape:
{
  "questions": [
    {
      "question_text": "...",
      "options": ["A", "B", "C", "D"],
      "correct_index": 1,
      "explanation": "Why this answer is correct (grounded in the transcript).",
      "concept": "Concept Name",
      "source_chunk_ids": ["chunk_0"]
    }
  ]
}

Extracted concepts:
{concept_blob}

Transcript chunks:
{chunk_blob}
```

### Dynamic variable map

| Variable | Rendered from | Injection context |
|---|---|---|
| `{max_questions}` | `generate_quiz(max_questions=10)`; API query param default 10 (learning.py:313). Frontend never sends it → always 10 | quiz_service.py:165 |
| `{version}` | `build_quiz_prompt(..., version=1)` — **always defaults to 1**; `_generate_with_llm` calls it WITHOUT passing version (quiz_service.py:165) | quiz_generation.py:39 |
| `{concept_blob}` | one line per concept, format `- {name}: {description}  [chunks: {id1}, {id2}]` (quiz_generation.py:29-32) | built inside builder |
| `{chunk_blob}` | one line per chunk, format `[chunk:{id}] ({start:.1f}s - {end:.1f}s) {text}` (quiz_generation.py:33-36) | built inside builder |

Context payload sources:
- Concepts → `QuizService._concept_dicts()` (graph_service, quiz_service.py:137-150).
- Chunks → `load_chunks()` (SQLite `TranscriptChunkTable`, quiz_service.py:27-53).

Initial generation injects `concept_dicts[:12]` and all chunks
(quiz_service.py:231-232).

### Structured output constraints

- **No JSON-schema / tool / `response_format` parameter is passed.**
  `TextGenerationRequest` (capabilities.py:4-10) has no schema field; the schema
  is expressed only inside the prompt text.
- Contract enforced **post-hoc** by `parse_llm_quiz` (lines 66-102): extracts the
  first `{...}` block via `re.search(r"\{.*\}", text, re.DOTALL)`, `json.loads`,
  iterates `data["questions"]`, drops items lacking non-empty `question_text` or
  `len(options) < 2`, coerces `correct_index` to int and clamps to
  `[0, len(options)-1]`, maps into `ExtractedQuestion` (dataclass, lines 9-19).
- Dispatch params: `temperature=0.3`, `max_tokens=2048` (quiz_service.py:166-167).
- **No retry loop.** If parsing fails, `_generate_with_llm` returns `[]` and
  `generate_quiz` falls back to the rule-based `generate_quiz_heuristic`
  (quiz_service.py:236-237).

### Heuristic fallback (rule-based)

When the LLM path yields no questions (error, unparseable JSON, or offline),
`generate_quiz_heuristic` (quiz_generation.py:112-191) generates questions using
fixed templates (`"Which statement correctly characterizes '{name}'?"`, etc.),
using concept descriptions as explanations and other concept names as distractor
options, or True/False questions when no distractors exist. RNG is seeded by
version for variation.

## Regeneration prompt specification

**There is no distinct regeneration/refinement prompt.** Regeneration (frontend
`generateQuiz`, useQuiz.ts:230-233 → `POST /api/v1/learning/quizzes/{ws}/generate?force_new_version=true`)
reuses the identical `build_quiz_prompt` with the same JSON output contract.

What actually changes for regeneration (`generate_quiz`, quiz_service.py:203-235):

1. **Cache bypass** — `force_new_version=True` skips the ready-quiz return at
   line 205; `version = latest + 1` (line 208); new `QuizTable` row status
   `generating`.
2. **Context rotation** — `_rotate_concepts_and_chunks` (lines 267-288) selects
   the least-covered concepts: `_concept_coverage` (lines 249-265) counts prior
   questions per `concept_id` from `QuizQuestionTable`, ranks by
   `(coverage, name)`, takes first 12; chunks are rotated by a version-based
   offset `(version-1) % len(chunks)`.
3. **Same LLM call** — `_generate_with_llm(selected_concepts, rotated_chunks,
   max_questions)` at line 235, same prompt/temperature/tokens.

### Regeneration context payload rules

- Concepts injected = least-covered 12 (coverage from all prior versions), not
  all concepts.
- Chunks injected = all chunks, reordered by version offset; not filtered to the
  selected concepts' source chunks.
- No previous-version questions are fed to the model; novelty relies solely on
  the prompt phrase "novel, concept-balanced ... fresh angles" plus the rotated
  context.

## Notes / caveats

- The `{version}` placeholder is **dead in production** — the prompt always says
  "Quiz Version 1" regardless of the actual regenerated version, because
  `_generate_with_llm` never passes `version` to `build_quiz_prompt`. Likely a
  latent bug in the regeneration prompt. Out of scope for this read-only task.
- Fallback on parse/LLM failure silently swaps in heuristic questions, so the LLM
  path is not strictly required for generation to succeed.
- Ollama's adapter returns a placeholder string when the local daemon is offline
  (ollama_adapter.py:138-142); `parse_llm_quiz` cannot parse it, so the heuristic
  engine silently produces the quiz in that case.
