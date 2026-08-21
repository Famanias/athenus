# Note Generation Heuristic Fallback — Root-Cause Investigation

**Investigation date:** 2026-08-21  
**Scope:** Frontend Generate Notes action, backend Notes and Chat LLM paths, provider dispatch, response parsing, persistence, runtime evidence, and test coverage.  
**Implementation changes:** None.

## 1. Executive Summary

The reported Notes request did not bypass the configured LLM, select a different provider, or fail because `NoteService` lacked its `AIServiceBus`. It reached the configured Groq adapter, received a provider-side non-2xx response, and then lost the error at the adapter boundary.

The confirmed failure chain is:

1. The UI called the item-generation endpoint and `NoteService.generate_note_content()`.
2. Notes resolved the same process-wide provider abstraction used by Chat: Groq, with persisted model `groq/compound-mini`.
3. `OpenAICompatibleProviderAdapter.generate()` converted a non-2xx HTTP response into an ordinary `TextGenerationResponse.text` string instead of raising or returning a typed failure.
4. `NoteService` therefore believed generation had returned normally and passed the synthetic API-error string to `parse_llm_notes()`.
5. Parsing returned `None`; `generate_note_content()` silently invoked `generate_notes_heuristic()`.
6. The heuristic result was persisted as `ready`, the endpoint returned HTTP 200, and the frontend displayed “AI notes generated and saved.”

The strongest historical fingerprint is the backend log at `2026-08-21T10:40:42Z`: `parse_llm_notes returned None (raw text len=241)`. Production names the adapter `Groq API (Cloud LPU)`. Its non-2xx return template contributes a 41-character prefix and appends exactly `resp.text[:200]`, producing exactly 241 characters when the provider error body is at least 200 characters. This matches the historical response length exactly. The preceding graph-generation request also fell back from its LLM path seconds earlier.

A live replay using the same configured provider, model, transcript, prompt shape, and adapter reproduced the failure class as HTTP 429: the provider reported a token-per-minute limit for underlying model `openai/gpt-oss-120b`; the adapter converted it to text; Notes parsing failed. A later replay succeeded with valid Notes JSON and parsed correctly, while `Hi` also succeeded. This proves the configured provider and Notes parser can work, and that the failure is transient/request-specific rather than a permanently unavailable LLM.

Groq's own API documentation defines 429 as a rate-limit response, exposes `Retry-After` and `x-ratelimit-*` response headers, and recommends retry/throttling rather than treating the body as generated content ([Groq rate limits](https://console.groq.com/docs/rate-limits), [Groq API errors](https://console.groq.com/docs/errors)).

The exact HTTP status and body of the **historical 10:40 request** cannot be recovered because the adapter truncated them into response text and neither logged nor persisted them. The historical non-2xx response is confirmed by its adapter-text fingerprint; HTTP 429 is the reproduced and most likely upstream trigger, but is not claimed as definitively recovered historical fact.

## 2. Observed Behavior

The canonical SQLite database contained the reported note (`note_aca42216fd1946b6b49052ce1f1751ba`) with:

- `summary`: `Structured synthesis of 1 transcript segments covering key educational concepts from 0s to 115s.`
- the three standard review/verification/recall action items;
- `status = ready`;
- update time `2026-08-21 10:40:42.195915`.

Those strings are emitted verbatim by `generate_notes_heuristic()` ([`backend/app/domain/learning/note_generation.py:251-267`](../backend/app/domain/learning/note_generation.py#L251)). They prove that fallback output was persisted, but are not themselves the cause.

The persisted runtime setting at investigation time selected provider `groq` and model `groq/compound-mini`. The same database contains a successful Chat exchange at `10:35:48`: user `hello`, assistant `Hello! How can I help you today?`.

## 3. Expected Behavior

When the configured provider returns a valid structured Notes response, the service should parse, validate, and persist it. A genuine provider failure may legitimately invoke heuristic fallback, but the failure must remain identifiable as a provider failure; the artifact and frontend must not misreport the result as successful AI generation.

This is also consistent with the repository's accepted “error integrity” decision: provider adapters should raise real generation failures so higher-level artifact services can make an explicit fallback decision ([`docs/adr/0020-local-first-llm-generation-timeout-policy-and-error-integrity.md`](adr/0020-local-first-llm-generation-timeout-policy-and-error-integrity.md)). That policy was applied to the Ollama adapter, but the generic cloud adapter still returns error-looking success text.

## 4. End-to-End Note Generation Flow

The current Generate Notes UI does **not** call `NoteService.generate_notes()`. It uses the item-generation path:

1. `NoteBottomBar` invokes `onGenerateNotes` on click or Enter ([`frontend/src/features/notes/NoteBottomBar.tsx:83-96`](../frontend/src/features/notes/NoteBottomBar.tsx#L83)).
2. `NotesWorkspace.handleGenerateNotes()` creates a note if needed, attaches the active media if needed, and calls `generateNotes(..., target.id)` ([`frontend/src/features/notes/NotesWorkspace.tsx:308-317`](../frontend/src/features/notes/NotesWorkspace.tsx#L308)).
3. `useNotes.generateNotes()` sends `POST /api/v1/learning/notes/item/{note_id}/generate`, with optional `custom_instruction` ([`frontend/src/features/notes/useNotes.ts:252-269`](../frontend/src/features/notes/useNotes.ts#L252)).
4. FastAPI `generate_note_item()` calls `note_service.generate_note_content()` ([`backend/app/presentation/api/v1/learning.py:678-689`](../backend/app/presentation/api/v1/learning.py#L678)).
5. `generate_note_content()` loads the note, requires attached media, marks it `generating`, and loads transcript chunks ([`backend/app/domain/learning/note_service.py:585-636`](../backend/app/domain/learning/note_service.py#L585)).
6. `_generate_with_llm()` resolves `get_text_capability()`, builds the Notes prompt, and calls non-streaming `generate()` with temperature `0.3` and `max_tokens=4096` ([`backend/app/domain/learning/note_service.py:411-445`](../backend/app/domain/learning/note_service.py#L411)).
7. `parse_llm_notes()` extracts a JSON object, manually coerces fields into dataclasses, and returns `None` for empty/unusable content ([`backend/app/domain/learning/note_generation.py:92-168`](../backend/app/domain/learning/note_generation.py#L92)). There is no Pydantic model validation in this stage.
8. If the parsed result is missing or has no sections, `generate_note_content()` calls `generate_notes_heuristic()` ([`backend/app/domain/learning/note_service.py:638-644`](../backend/app/domain/learning/note_service.py#L638)). This is the exact LLM-to-heuristic transition used by the UI.
9. The service stores summary/action items in `notes`, replaces rows in `note_sections`, marks the artifact job and note `ready`, and returns the persisted note ([`backend/app/domain/learning/note_service.py:646-659`](../backend/app/domain/learning/note_service.py#L646)).
10. The response DTO has no provider/model/generator/fallback fields ([`backend/app/presentation/api/v1/learning.py:558-571`](../backend/app/presentation/api/v1/learning.py#L558)). Any HTTP 200 leads the frontend to display `AI notes generated and saved` ([`frontend/src/features/notes/useNotes.ts:261-269`](../frontend/src/features/notes/useNotes.ts#L261)).

The separate workspace endpoint `POST /learning/notes/{workspace_id}` calls `NoteService.generate_notes()` ([`backend/app/presentation/api/v1/learning.py:692-712`](../backend/app/presentation/api/v1/learning.py#L692)); it contains the same parsing and heuristic transition, but it is not the button's current route.

## 5. Chat vs. Notes LLM Pipeline Comparison

| Concern | Chat | Notes | Finding |
|---|---|---|---|
| Frontend transport | Shared `apiClient` | Shared `apiClient` | Same base URL; neither adds a frontend timeout ([`frontend/src/services/apiClient.ts:15-50`](../frontend/src/services/apiClient.ts#L15)). |
| Backend entry | `POST /chat/query` | `POST /learning/notes/item/{id}/generate` | Different application services. |
| Service | `WorkspaceIntelligenceManager.query_workspace()` | `NoteService.generate_note_content()` | Divergence is after HTTP routing. |
| Provider abstraction | Process-wide `AIServiceBus` | Same process-wide `AIServiceBus` | `main.py` constructs one bus and injects it into both paths ([`backend/app/main.py:102-118`](../backend/app/main.py#L102), [`backend/app/main.py:169-173`](../backend/app/main.py#L169)). |
| Provider/model selection | `get_text_capability()`; provider registry reads SQLite active provider; adapter resolves active per-provider model | Identical | No Notes-specific provider or model override ([`backend/app/domain/ai/service_bus.py:37-70`](../backend/app/domain/ai/service_bus.py#L37), [`backend/app/domain/ai/provider_registry.py:35-48`](../backend/app/domain/ai/provider_registry.py#L35)). |
| Request mode | Non-streaming `generate()` | Non-streaming `generate()` | Streaming is not the difference ([`backend/app/application/services/workspace_intelligence.py:57-65`](../backend/app/application/services/workspace_intelligence.py#L57)). |
| Prompt | Retrieved conversational/RAG prompt | Transcript plus strict JSON instructions | Notes is longer and structured. |
| Maximum output | 2,048 tokens | 4,096 tokens | Notes has a larger quota footprint. |
| Success criterion | Any response text becomes the answer | Text must parse to Notes JSON with at least one section | This is the decisive behavioral difference. |
| Error behavior | Synthetic adapter error text can be displayed/persisted as an answer | Synthetic adapter error text fails parsing and triggers heuristic output | Both paths suffer the adapter contract bug, but Notes masks it more completely. |
| Retries | None in this call chain | None in this call chain | A transient 429/5xx immediately reaches the masking behavior. |
| Cloud timeout | Generic adapter creates `httpx.AsyncClient(timeout=30.0)` | Same | Not implicated in the historical fingerprint, but still a fixed cloud timeout ([`backend/app/infrastructure/adapters/openai_compatible_adapter.py:86-87`](../backend/app/infrastructure/adapters/openai_compatible_adapter.py#L86)). |

Thus, successful Chat proves the provider can answer a small request, but does not prove a later, larger structured request will avoid transient quota/provider errors. It also does not exercise Notes parsing.

## 6. Fallback Trigger Analysis

There are four ways `_generate_with_llm()` returns no usable result:

1. `ai_service_bus` is `None`;
2. provider capability resolution raises;
3. `generate()` raises;
4. generation returns text that `parse_llm_notes()` rejects.

The historical log selects path 4: `parse_llm_notes returned None (raw text len=241)` ([`backend/app/domain/learning/note_service.py:417-445`](../backend/app/domain/learning/note_service.py#L417)). It rules out a missing bus and a raised resolution/generation exception for this request.

The reason path 4 was entered is the cloud adapter's error contract:

- A non-200 response is converted into `TextGenerationResponse(text="⚠️ {provider} API Error ({status}): {resp.text[:200]}")` ([`backend/app/infrastructure/adapters/openai_compatible_adapter.py:177-196`](../backend/app/infrastructure/adapters/openai_compatible_adapter.py#L177)).
- Network exceptions are similarly converted to normal response text ([`backend/app/infrastructure/adapters/openai_compatible_adapter.py:197-202`](../backend/app/infrastructure/adapters/openai_compatible_adapter.py#L197)).
- `NoteService` has no way to distinguish these from model output, because `TextGenerationResponse` carries no success/error discriminator ([`backend/app/domain/ai/capabilities.py:13-17`](../backend/app/domain/ai/capabilities.py#L13)).
- Parsing the synthetic error returns `None`; the caller then takes the heuristic branch.

The heuristic is therefore operating as designed at the service layer, but it is being triggered by an incorrectly represented provider failure and then mislabeled as success.

## 7. Runtime / Code Evidence

### Historical request

Read-only SQLite and Docker-log inspection established this sequence for `med_68cd215f`:

| UTC timestamp | Evidence |
|---|---|
| `10:40:29.833` | Graph worker enters `Running LLM concept extraction...`. |
| `10:40:38.098` | Graph worker records `LLM extraction unavailable; using deterministic heuristic extraction...`. Persisted concepts have the heuristic description `Key concept extracted from lecture content.` |
| `10:40:40.770` | Notes enters `Synthesizing comprehensive notes with AI model...`. |
| `10:40:42.167` | `NoteService: parse_llm_notes returned None (raw text len=241). Falling back to heuristic.` |
| `10:40:42.195` | Heuristic summary/action items are stored with `status=ready`. |
| `10:40:42.292` | Generate endpoint returns HTTP 200. |

The 241-character response is the exact length produced by the production Groq adapter's 41-character non-2xx prefix plus its 200-character body truncation. No credential or authorization header was captured.

### Live replay (not the historical request)

A direct replay against the same configured Groq endpoint/model and the same saved 115-second transcript produced both sides of the behavior:

- One run returned a real HTTP 429 for underlying `openai/gpt-oss-120b`, with an 8,000 TPM limit, 4,956 tokens already used, and the requested amount truncated in the captured preview. The adapter returned zero token usage as ordinary text; `parse_llm_notes()` returned `None`.
- After the transient condition cleared, the Notes request returned HTTP 200 in 3.433 seconds, with 1,893 prompt tokens, 1,265 completion tokens, 3,317 response characters, valid JSON, and two parsed sections.
- In the same successful sequence, the graph request returned HTTP 200 and parsed, and `Hi` returned HTTP 200 in 0.659 seconds with `Hello! How can I help you today?`.

This is a red-capable reproduction of the actual transition: provider non-2xx → synthetic `TextGenerationResponse` → parse failure → heuristic eligibility. It also rules out a deterministic inability of `groq/compound-mini` to emit the required Notes JSON.

### Automated tests

The focused Notes test module passed:

```text
$env:PYTHONPATH='.'; pytest tests/test_note_generation.py -q
9 passed in 0.80s
```

They cover valid fake JSON and provider-routing consistency, but not the production failure contract. `test_note_service_llm_execution` injects already-valid JSON ([`backend/tests/test_note_generation.py:194-278`](../backend/tests/test_note_generation.py#L194)). The endpoint test asserts only that summary, action items, and sections are non-empty, all of which heuristic output satisfies ([`backend/tests/test_note_endpoints.py:160-187`](../backend/tests/test_note_endpoints.py#L160)). The generic adapter test covers HTTP 200 and missing credentials, but not non-2xx generation responses ([`backend/tests/test_openai_compatible_adapter.py:27-100`](../backend/tests/test_openai_compatible_adapter.py#L27)).

## 8. Confirmed Root Cause

**Confirmed:** `OpenAICompatibleProviderAdapter.generate()` violates error integrity by representing provider HTTP/network failures as successful `TextGenerationResponse` text. For the observed request, the returned 241-character text has the exact production adapter fingerprint for a non-2xx response. `NoteService` attempted to parse that provider-error text as Notes JSON; parsing returned `None`; `generate_note_content()` invoked the heuristic; persistence and the API then reported the result as `ready`/HTTP 200.

**Most likely upstream trigger, but not historically recoverable:** a transient Groq rate-limit response. The identical live path reproduced HTTP 429 from `groq/compound-mini`'s underlying `openai/gpt-oss-120b`, and the graph LLM path had failed seconds before the historical Notes request. However, the historical status/body was discarded, so the report does not relabel that exact request as a proven 429.

This answers why Chat could work: Chat and Notes share the provider, but a small Chat request can succeed outside the transient quota condition; Notes made a later, larger structured request and uniquely rejects non-JSON text. The working live Notes replay further confirms that provider dispatch and JSON parsing are functional when the provider returns HTTP 200 JSON.

## 9. Contributing Issues

- **Error swallowing in the generic cloud adapter:** non-2xx and network failures do not raise.
- **No retry/backoff:** 429 and transient 5xx responses go directly to parsing/fallback; `Retry-After` is ignored.
- **No typed generation outcome:** `TextGenerationResponse` cannot express provider ID, model, HTTP status, error category, latency, or retryability.
- **Fallback is indistinguishable from LLM success:** notes/artifact jobs end as `ready`; the response schema and frontend expose no `generation_method` or `fallback_reason`.
- **Misleading UI:** every HTTP 200 shows “AI notes generated and saved.”
- **Larger Notes request:** Notes requests 4,096 output tokens versus Chat's 2,048, increasing exposure to token quotas. The nearby graph generation is another provider workload. This is a risk factor, not independently proven as the historical status.
- **Parser fragility:** JSON is extracted with one greedy `\{.*\}` regex and manually coerced. It tolerates fenced JSON and passed the live valid response, but can reject otherwise recoverable output containing multiple brace-delimited objects or truncated JSON. It is not the cause shown by the 241-character provider-error fingerprint.
- **Insufficient historical telemetry:** only response length survived. The provider status/body, model, latency, and parse stage were not recorded.
- **Tests accept fallback as success:** the real button endpoint has no assertion that an LLM-configured test actually used LLM output.

## 10. Issues Ruled Out

- **A missing/uninjected Notes AI bus:** historical execution reached parsing; a missing bus returns earlier. `main.py` also injects the process-wide bus into `NoteService`.
- **A separate Notes provider/configuration path:** Notes and Chat resolve through the same registry/config resolver and active adapter.
- **Streaming differences:** both paths call non-streaming `generate()`.
- **A permanently invalid credential/base URL/model:** Chat succeeded with the configured provider, and the identical live Notes request later returned valid JSON.
- **A deterministic schema incompatibility with `groq/compound-mini`:** the identical live Notes response parsed successfully.
- **Pydantic validation failure:** Notes parsing uses dataclasses/manual coercion, not Pydantic validation.
- **Persistence causing the fallback:** the fallback decision occurs before persistence. Persistence successfully stored exactly what the heuristic returned.
- **Frontend calling the wrong backend:** the actual item endpoint and service path are confirmed; the frontend simply cannot see which generator produced the successful response.
- **The heuristic strings as root cause:** they are only a reliable marker that the fallback branch ran.

## 11. Recommended Fix

Do not implement only a parser workaround. Correct the provider error boundary first.

1. Change `OpenAICompatibleProviderAdapter.generate()` (and Anthropic where it has the same pattern) to raise typed exceptions for missing credentials, non-2xx HTTP responses, timeouts, and network failures. Preserve status, provider, resolved model, safe retry metadata, and a redacted error summary. Never return warning/error prose as `TextGenerationResponse.text`.
2. In `NoteService`, distinguish `ProviderRateLimitError`, other provider errors, parse errors, and schema-validation errors. Apply bounded retry/backoff for retryable failures, respecting `Retry-After`, before choosing heuristic fallback.
3. Make fallback explicit in the persisted/API outcome, for example `generation_method: llm | heuristic`, `provider_id`, `model_id`, and a safe `fallback_reason`. A legitimate fallback can still be `ready`, but must not be reported as LLM-generated.
4. Use a defined Notes response schema and provider-native JSON/schema mode where the selected adapter supports it. Groq documents JSON Object Mode across models and stricter schema modes on a smaller supported-model set ([Groq structured outputs](https://console.groq.com/docs/structured-outputs)); capability negotiation must therefore be provider/model aware. Retain a robust text parser for providers without structured-output support; do not use a single greedy regex as the only extraction strategy.
5. Right-size output limits for Notes and coordinate artifact-generation concurrency against provider rate limits. For compound/agentic models, consider a stable structured-generation model or provider-aware token budget rather than assuming `max_tokens=4096` is harmless.
6. Keep fallback policy at the service/application layer, not inside provider adapters, consistent with ADR 0020.

## 12. Recommended Logging / Observability Improvements

Emit one correlated generation event at provider dispatch and one at completion/failure with:

- request/correlation ID, workspace/media/note IDs;
- capability/workload (`chat`, `notes`, `graph`);
- provider ID and resolved model (never API key or authorization header);
- prompt character count and estimated tokens, requested maximum output, temperature;
- attempt number, HTTP status, latency, timeout category, retryability, safe rate-limit headers;
- response character count, prompt/completion token usage, finish reason;
- structured parsing stage (`json_extract`, `json_decode`, `schema_validate`) and validation error summary;
- final generation method and explicit fallback reason.

For non-2xx bodies, log a bounded, redacted summary and stable hash. Do not log transcript text, full prompts, secrets, auth headers, or arbitrary raw provider bodies. Persist the safe failure category/status in `artifact_jobs.error_message` or dedicated generation telemetry instead of overwriting the job with an unqualified `ready` message.

The minimum temporary instrumentation needed to recover the one remaining historical unknown is at the adapter/Notes boundary: log correlation ID, provider/model, HTTP status, latency, retry headers, response length/hash, and parse outcome. That would prove whether a future recurrence is 429, another non-2xx, timeout, or genuine malformed model output.

## 13. Verification Plan

### Automated

1. **Adapter error integrity:** mock 400, 401, 404, 429, 500, timeout, and connection failure; assert typed exceptions, redacted metadata, and no `TextGenerationResponse` warning strings.
2. **Successful structured Notes:** through the actual `POST /learning/notes/item/{id}/generate` seam, mock HTTP 200 with plain JSON and fenced JSON; assert persisted content is the LLM payload and `generation_method=llm`.
3. **Parser/schema cases:** cover surrounding prose, code fences, multiple JSON-like spans, numeric strings, missing required sections, wrong collection types, truncation, and provider error JSON. Assert distinct parse/validation failures.
4. **Retryable provider failure:** return 429 then 200; assert `Retry-After` is honored, the eventual LLM result is persisted, and heuristic generation is not invoked.
5. **Legitimate fallback:** exhaust retryable failures or return a non-retryable provider failure under the chosen policy; assert heuristic content is persisted with `generation_method=heuristic`, a safe reason, provider/model/status telemetry, and no false “AI generated” claim.
6. **No silent success:** make a 200 response contain malformed structured content; assert the parse failure is logged and surfaced distinctly from provider unavailability.
7. **Chat regression:** send `Hi` through `/api/v1/chat/query`; assert the configured provider still answers and adapter changes do not break Chat.
8. **Provider-routing consistency:** assert Chat and Notes record the same configured provider/model unless a deliberate workload override is configured.
9. **Frontend/E2E:** drive the Generate Notes button; assert the UI shows LLM success for `generation_method=llm` and an explicit fallback notice for `heuristic`.

### Manual runtime verification

1. Select the target provider/model in Settings and verify connection.
2. Send `Hi` in Chat and record provider/model/correlation ID.
3. Generate Notes for a known transcript; verify the same provider/model is logged, valid structured output parses, and the persisted note is not the deterministic heuristic signature.
4. Force a controlled 429 or point a test adapter at a mock 429 endpoint; verify retry/error telemetry and explicit fallback behavior.
5. Disable/unconfigure the provider intentionally; verify heuristic fallback still works, is clearly labeled, and secrets are absent from logs.
6. Repeat immediately after graph generation to verify provider-workload coordination and quota behavior.

The eventual fix is proven only when Chat still succeeds, Notes persists configured-LLM output on HTTP 200, successful provider output cannot silently fall back, structured responses parse across supported formats, genuine failures retain their real error category, and deliberate heuristic fallback remains functional and visible.
