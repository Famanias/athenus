# Adding a New LLM Provider

This guide walks through registering a new LLM text-generation provider in Athenus, using **Ollama Cloud** as a concrete end-to-end example.

> Architecture reference: [`docs/adr/0019-provider-agnostic-llm-architecture-and-two-tier-adapters.md`](adr/0019-provider-agnostic-llm-architecture-and-two-tier-adapters.md)

## Background: Two-Tier Adapter Classification

Before writing any code, classify your new provider:

| Tier | Adapter | Used for | Endpoints used |
|------|---------|----------|----------------|
| **Tier 1** | `OpenAICompatibleProviderAdapter` | Any provider exposing an OpenAI-compatible API | `/v1/chat/completions`, `/v1/models` |
| **Tier 2** | Custom adapter (e.g., `AnthropicProviderAdapter`, `OllamaTextGenAdapter`) | Proprietary/native APIs | provider-specific |

Ollama Cloud exposes `https://ollama.com/v1` with standard OpenAI-compatible endpoints, so it falls into **Tier 1** — **no new adapter class is required**.

If your provider is OpenAI-compatible, most of the work is just registration and configuration (steps 1–5). Only step 6 (ModelRegistry, optional) and step 7 (tests) change based on classification.

---

## Step 1 — Add configuration fields (`backend/app/core/config.py`)

Add the provider's base URL, default model, and API key next to the existing provider settings (around line 57, after the `ANTHROPIC_*` block):

```python
# Ollama Cloud (OpenAI-compatible)
OLLAMA_CLOUD_BASE_URL: str = "https://ollama.com/v1"
OLLAMA_CLOUD_DEFAULT_MODEL: str = "llama3.3"        # any model id available on your Ollama Cloud account
OLLAMA_CLOUD_API_KEY: Optional[str] = None
```

## Step 2 — Document the secret (`.env.example` + your real `.env`)

Add to `.env.example` under the "Optional Cloud AI Providers" section (line 49):

```
OLLAMA_CLOUD_API_KEY=your_key_here
```

Add the same line to your local `.env` with the real key. API keys are read only from environment configuration and are **never** persisted to SQLite (see `ProviderConfigResolver.get_api_key()`).

## Step 3 — Resolve the secret in `ProviderConfigResolver` (`backend/app/domain/ai/config_resolver.py`)

The `env_map` in `get_api_key()` (lines 42–47) is the single secret-lookup table used by health checks and `is_configured()`. Add the new provider:

```python
env_map: Dict[str, Optional[str]] = {
    "openrouter": getattr(settings, "OPENROUTER_API_KEY", None),
    "groq": getattr(settings, "GROQ_API_KEY", None),
    "openai": getattr(settings, "OPENAI_API_KEY", None),
    "anthropic": getattr(settings, "ANTHROPIC_API_KEY", None),
    "ollama_cloud": getattr(settings, "OLLAMA_CLOUD_API_KEY", None),
}
```

Without this entry, `is_configured("ollama_cloud")` always returns `False` and the UI shows the provider as unconfigured.

## Step 4 — Instantiate and register the adapter (`backend/app/main.py`)

### 4a. Instantiate the adapter

Add an `OpenAICompatibleProviderAdapter` next to the other cloud adapters (after `anthropic_adapter`, line 75):

```python
ollama_cloud_adapter = OpenAICompatibleProviderAdapter(
    provider_id="ollama_cloud",
    name="Ollama Cloud (OpenAI-compatible)",
    base_url=settings.OLLAMA_CLOUD_BASE_URL,
    api_key=settings.OLLAMA_CLOUD_API_KEY,
    default_model=settings.OLLAMA_CLOUD_DEFAULT_MODEL,
)
```

> **Tier 2 providers only:** instantiate your custom adapter class instead.

### 4b. Register in the provider registry

Add next to the other `register()` calls (line 82):

```python
llm_provider_registry.register(ollama_cloud_adapter)
```

This makes the provider appear in the `GET /settings/providers/catalog` output, the chat `ModelSwitcher`, and the System Settings dropdown automatically.

### 4c. Register the text adapter in the service bus

Add next to the other `register_text_adapter()` calls (line 111):

```python
ai_service_bus.register_text_adapter("ollama_cloud", ollama_cloud_adapter)
```

This wires generation/streaming through `AIServiceBus`.

## Step 5 — Allowlist the provider in the settings API (`backend/app/presentation/api/v1/settings.py`)

Two edits so `PUT`/`PATCH /settings/providers` accept the id:

1. Add to `_normalize_provider()` map (lines 47–55):

   ```python
   "ollama_cloud": "ollama_cloud",
   ```

2. Add to the `valid_llms` fallback list (line 63):

   ```python
   valid_llms = ["ollama", "groq", "openrouter", "openai", "anthropic", "ollama_cloud"]
   ```

> Note: `_normalize_provider()` first checks `llm_provider_registry.get(provider)`, so a registered adapter passes validation even without the `valid_llms` entry — but keeping the list in sync is good hygiene.

---

## Step 6 — (Optional) ModelRegistry capability routing (`backend/app/domain/ai/model_registry.py`)

If you want the provider included in capability-based routing (`find_by_capability`, health counts), add it to the enum and seed a model:

```python
class ModelProviderType(str, Enum):
    ...
    OLLAMA_CLOUD = "ollama_cloud"
```

Then in `_register_default_models()`:

```python
self.register(ModelMetadata(
    model_id="ollama_cloud",
    provider=ModelProviderType.OLLAMA_CLOUD,
    capabilities=[ModelCapabilityType.TEXT_GENERATION],
    context_window=8192,
    is_local=False,
    is_installed=True,
    display_name="Ollama Cloud API"
))
```

This step is optional: `LLMProviderRegistry`/`AIServiceBus` resolve the active provider dynamically by id, so chat generation works without it. Add it if you want the provider to participate in router policy decisions.

---

## Step 7 — (Optional) Frontend fallback option (`SystemSettings.tsx`)

The catalog is served dynamically by the backend, so no frontend code is required. There is only a hardcoded fallback `<option>` list at `frontend/src/features/settings/SystemSettings.tsx` (~line 634) used when the backend catalog is unavailable. Add the provider there if you want it visible even when offline:

```tsx
<option value="ollama_cloud">Ollama Cloud (OpenAI-compatible)</option>
```

---

## Step 8 — Tests

Extend the existing test suites to cover the new provider:

- `backend/tests/test_provider_registry.py` — register/get/catalog/health for the new id.
- `backend/tests/test_provider_patch_and_catalog.py` — PUT/PATCH switching to `ollama_cloud`, catalog entry present.
- `backend/tests/test_openai_compatible_adapter.py` — if your provider uses a Tier 2 adapter, add a native-API test (mirror `test_anthropic_adapter.py`).

---

## Step 9 — Verify end-to-end

1. Set `OLLAMA_CLOUD_API_KEY` in `.env` and restart the backend (`python app/main.py`).
2. `GET /api/v1/settings/providers/catalog` → `ollama_cloud` appears with `is_configured: true` and its model list.
3. `POST /api/v1/settings/providers/ollama_cloud/test` → returns healthy.
4. In System Settings → LLM Provider, select "Ollama Cloud", pick a model, hit Test Connection.
5. Send a chat message and confirm responses come from the cloud model.
6. Run the backend test suite: `pytest` (from `backend/`).

---

## Checklist Summary

| # | File | Change |
|---|------|--------|
| 1 | `backend/app/core/config.py` | Add `*_BASE_URL`, `*_DEFAULT_MODEL`, `*_API_KEY` fields |
| 2 | `.env.example` / `.env` | Add the API key variable |
| 3 | `backend/app/domain/ai/config_resolver.py` | Add id to `env_map` in `get_api_key()` |
| 4 | `backend/app/main.py` | Instantiate adapter, `registry.register()`, `register_text_adapter()` |
| 5 | `backend/app/presentation/api/v1/settings.py` | Add to `_normalize_provider()` map + `valid_llms` |
| 6 | `backend/app/domain/ai/model_registry.py` | (Optional) `ModelProviderType` + default model |
| 7 | `frontend/src/features/settings/SystemSettings.tsx` | (Optional) fallback `<option>` |
| 8 | `backend/tests/` | Extend provider/registry/patch tests |

## Notes & Caveats

- **Header format:** `OpenAICompatibleProviderAdapter` sends `Authorization: Bearer <key>`. If your provider expects a different auth scheme (e.g., `x-api-key`), subclass the adapter and override the headers, or write a Tier 2 adapter (see `AnthropicProviderAdapter`).
- **Local-first routing:** `router_policy.policy.prefer_local` is set to `True` only for `"ollama"` (see `settings.py` line 108). Cloud providers keep it `False`, so local models are still preferred when available.
- **Transient API keys:** keys submitted via the settings UI are held in the in-memory `_transient_api_key` variable and pushed to the adapter's `set_api_key()` — they are never written to SQLite.
- **Health/model TTL caches:** `LLMProviderRegistry.get_catalog()` caches health for 30s and models for 1h; use `force_refresh` if a change doesn't appear immediately.
