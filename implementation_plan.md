# Architectural Review & Implementation Plan: Provider-Agnostic LLM Architecture (Revised Edition)

Refactor the current text generation provider architecture from hardcoded, provider-specific logic (OpenRouter, Groq, Ollama) into a **scalable, provider-agnostic LLM architecture** based on a central **Provider Registry**, **Two-Tier Adapter Classification**, **Layered Configuration Resolver (`ProviderConfigResolver`)**, **Chat-Model Catalog Filtering (`is_chat_model()`)**, and **Concurrent Dynamic Model Discovery with TTL Caching**.

Comprehensive architectural documentation has been updated in [`docs/LLM_PROVIDER_ARCHITECTURE_REVIEW.md`](file:///e:/repos/athenus/docs/LLM_PROVIDER_ARCHITECTURE_REVIEW.md).

---

## Key Architectural Decisions (Revised per Independent Senior Review)

> [!IMPORTANT]
> **Key Architecture Decisions:**
> 1. **Two-Tier Adapter Classification**:
>    - **Tier 1 (Zero-Code Extension)**: Generic `OpenAICompatibleProviderAdapter` serves all OpenAI-wire compatible providers (OpenRouter, Groq, OpenAI, DeepSeek, NVIDIA NIM, Together AI, Fireworks AI, LiteLLM, LM Studio, vLLM) with zero code changes.
>    - **Tier 2 (Dedicated Provider Adapters)**: Specialized classes inheriting from `BaseLLMProvider` handle non-OpenAI wire formats: `AnthropicProviderAdapter` (native `/v1/messages` format) and `OllamaLLMAdapter` (native daemon API).
> 2. **Layered Configuration Resolver (`ProviderConfigResolver`)**:
>    - **Secrets Tier**: API keys live strictly in `.env` / process environment variables (never written to DB).
>    - **Runtime State Tier**: Active provider selection (`LLM_PROVIDER`), selected model override (`LLM_MODEL`), and custom endpoint URLs are stored in SQLite and hot-swappable in the UI **without restarting the server**.
> 3. **Chat-Model Filtering (`is_chat_model()`)**: Automatically filters out embedding, reranker, guardrail, and speech models from discovered `/models` catalogs, eliminating dropdown clutter on OpenRouter (200+ models) and NVIDIA NIM.
> 4. **Concurrent Health Checks & TTL Caching**: `LLMProviderRegistry.get_catalog()` aggregates health checks concurrently via `asyncio.gather` with a 30s health TTL cache and 1-hour model discovery TTL cache, preventing settings page load lag.
> 5. **Capability-Checked Dispatching**: `AIServiceBus` negotiates capabilities (`supports_vision`, `supports_function_calling`) before dispatching requests, throwing typed `UnsupportedCapabilityError` exceptions when feature requirements are missing.

---

## Resolved Design Questions

> [!NOTE]
> **Resolution to Model Filtering**: Rather than forcing a choice between dumping 200+ unfiltered models or hardcoding static whitelists, the adapter applies an automated `is_chat_model()` predicate at discovery time, returning clean chat models to the UI. The UI includes client-side search/sort for smooth UX.

---

## Proposed Component Changes

### Core Domain Abstraction (`app/domain/ai`)

#### [NEW] [provider_interface.py](file:///e:/repos/athenus/backend/app/domain/ai/provider_interface.py)
- Define `ILLMProvider` interface protocol and `BaseLLMProvider` abstract base class with default method contracts.
- Implement `BaseLLMProvider.check_health()` to explicitly check credential presence (`api_key` or `is_local`) *before* invoking `list_models()`, ensuring unconfigured cloud providers accurately report `is_configured=False` and `is_available=False` (`🔴 Key missing in .env`).
- Define DTOs: `LLMProviderCapabilities`, `LLMModelMetadataDTO`, `ProviderHealthDTO`.

#### [NEW] [provider_registry.py](file:///e:/repos/athenus/backend/app/domain/ai/provider_registry.py)
- Implement `LLMProviderRegistry` responsible for registering provider adapters, resolving active provider, exposing provider catalog via concurrent `asyncio.gather` health checks, and supporting 30s health TTL caching.

#### [NEW] [config_resolver.py](file:///e:/repos/athenus/backend/app/domain/ai/config_resolver.py)
- Implement `ProviderConfigResolver` to cleanly separate `.env` secrets from hot-swappable SQLite runtime preferences.

#### [MODIFY] [service_bus.py](file:///e:/repos/athenus/backend/app/domain/ai/service_bus.py)
- Update `AIServiceBus` to delegate text generation capabilities directly to `LLMProviderRegistry` with capability negotiation checks (`UnsupportedCapabilityError`).

#### [MODIFY] [model_registry.py](file:///e:/repos/athenus/backend/app/domain/ai/model_registry.py)
- Refactor `ModelRegistry` to pull model metadata dynamically from registered provider capabilities instead of maintaining brittle static lists.

---

### Infrastructure Adapters (`app/infrastructure/adapters`)

#### [NEW] [openai_compatible_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/openai_compatible_adapter.py)
- Implement Tier 1 `OpenAICompatibleProviderAdapter` implementing `BaseLLMProvider`.
- Provide generic support for OpenRouter, Groq, OpenAI, DeepSeek, NVIDIA NIM, Together AI, LiteLLM, LM Studio, etc.
- Implement dynamic `/models` endpoint discovery with `is_chat_model()` filtering, 1-hour TTL caching, shared `httpx.AsyncClient` connection pool, and fallback defaults.

#### [NEW] [anthropic_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/anthropic_adapter.py)
- Implement Tier 2 `AnthropicProviderAdapter` implementing `BaseLLMProvider` for native `/v1/messages` execution.

#### [MODIFY] [ollama_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/ollama_adapter.py)
- Adapt `OllamaLLMAdapter` to implement `BaseLLMProvider` interface, supporting native daemon status, reported model size bytes, and model discovery.

#### [DELETE] [cloud_llm_adapter.py](file:///e:/repos/athenus/backend/app/infrastructure/adapters/cloud_llm_adapter.py)
- Replaced by `OpenAICompatibleProviderAdapter` and `AnthropicProviderAdapter`.

---

### Configuration & Security (`app/core` & `app/main.py`)

#### [MODIFY] [config.py](file:///e:/repos/athenus/backend/app/core/config.py)
- Expand Pydantic `Settings` schema to support environment variables for all supported providers (`LLM_PROVIDER`, `LLM_MODEL`, `OPENROUTER_*`, `GROQ_*`, `OPENAI_*`, `ANTHROPIC_*`, `CUSTOM_LLM_PROVIDERS`).

#### [NEW] [redaction_middleware.py](file:///e:/repos/athenus/backend/app/core/redaction_middleware.py)
- Implement HTTP log and traceback redaction middleware sanitizing `Authorization` and `x-api-key` headers (`[REDACTED_API_KEY]`).

#### [MODIFY] [main.py](file:///e:/repos/athenus/backend/app/main.py)
- Initialize `LLMProviderRegistry` and `ProviderConfigResolver` during application boot.
- Dynamically register Tier 1 and Tier 2 provider adapters with shared `httpx` connection pool.

---

### Presentation API & Frontend UI (`app/presentation/api/v1` & `frontend`)

#### [MODIFY] [settings.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py)
- Refactor `/api/v1/settings/providers` and `/settings/providers/catalog` endpoints to query `LLMProviderRegistry`.
- Support hot-swapping active provider in SQLite via `ProviderConfigResolver`.
- Expose `/api/v1/settings/providers/{id}/test` connection endpoint.

#### [MODIFY] [settingsService.ts](file:///e:/repos/athenus/frontend/src/services/settingsService.ts)
- Update TypeScript DTO interfaces to match dynamic provider catalog, model metadata, model sizes, and health status structures.

#### [MODIFY] [SystemSettings.tsx](file:///e:/repos/athenus/frontend/src/features/settings/SystemSettings.tsx)
- Redesign Settings UI into an interactive configuration inspector and hot-swappable provider selector.
- Render dynamic provider options, model dropdowns, model sizes, health badges, and an interactive `Test Connection` button.

---

## Verification Plan

### Automated Tests
- `pytest backend/tests/test_provider_registry.py` (Verify provider registration, fallback logic, active provider resolution, and concurrent health checks)
- `pytest backend/tests/test_openai_compatible_adapter.py` (Verify text generation, streaming, `is_chat_model()` filtering, TTL caching using `respx` mock HTTP transports)
- `pytest backend/tests/test_anthropic_adapter.py` (Verify Anthropic native `/v1/messages` format)
- `pytest backend/tests/test_ai_service_bus.py` (Verify capability-checked dispatch and `UnsupportedCapabilityError` handling)

### Manual Verification
- Test hot-swapping active provider between Ollama, OpenRouter, Groq, and Anthropic in the Settings UI without server restart.
- Verify log outputs to confirm `Authorization` headers are sanitized as `[REDACTED_API_KEY]`.
- Test adding a custom OpenAI-compatible provider via `CUSTOM_LLM_PROVIDERS` in `.env` with zero code modifications.
