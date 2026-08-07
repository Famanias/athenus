# Architectural Review & Proposal: Provider-Agnostic LLM Architecture

**Document Status:** Architectural Proposal & Design Specification (Revised Edition)  
**Date:** August 7, 2026  
**Target Subsystem:** AI Service Bus, Model Registry, Provider Adapters, Configuration & Settings  
**Author:** Antigravity AI  

---

## 1. Executive Summary

This document presents a comprehensive architectural review of the current **Text Generation Provider** and **Settings System** in Athenus Knowledge OS, followed by a production-ready design for a **Provider-Agnostic LLM Architecture**.

The current implementation couples provider selection, model identifiers, API keys, and settings UI components to hardcoded vendor names (`ollama`, `groq`, `openrouter`). Hardcoded model defaults (such as Groq's `llama3-8b-8192` and OpenRouter's `meta-llama/llama-3-8b-instruct:free`) have already resulted in runtime `400` and `404` errors due to upstream model deprecations. Furthermore, API key management relies on a single transient variable, causing key leakage across providers, and ignoring credentials set in environment (`.env`) files.

Our proposed architecture replaces provider-specific logic with a **Provider-Agnostic LLM Abstraction**, a central **LLM Provider Registry**, a **Two-Tier Adapter Classification**, a **Layered Configuration Resolver (`ProviderConfigResolver`)**, **Chat-Model Catalog Filtering (`is_chat_model()`)**, and **Concurrent Dynamic Model Discovery with TTL Caching**. 

This redesign transforms the Settings page into a responsive configuration inspector and hot-swappable active provider selector with credential health badges while supporting any OpenAI-compatible or proprietary provider (Ollama, Groq, OpenRouter, OpenAI, Anthropic, NVIDIA NIM, DeepSeek, Together AI, Fireworks AI, LiteLLM, LM Studio) without modifying core application code.

---

## 2. Comprehensive Analysis of Current Architecture

```
                        CURRENT ARCHITECTURE (BRITTLE & COUPLED)

┌──────────────────────────────────────────────────────────────────────────────────┐
│                             Settings API & UI                                    │
│  - Hardcoded valid LLMs: ["ollama", "groq", "openrouter"]                        │
│  - Single `_transient_api_key` string shared across ALL cloud providers           │
│  - Hardcoded catalog models (`llama3-8b-8192`, `llama-3-8b-instruct:free`)       │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            AIServiceBus & Main                                   │
│  - Direct instantiation of `CloudTextGenAdapter` for OpenRouter and Groq         │
│  - Switch statement in `get_text_capability()` checking string values            │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             Infrastructure Adapters                              │
│  - `CloudTextGenAdapter`: Single class handling OpenRouter & Groq with static models│
│  - `OllamaTextGenAdapter`: Custom local fallback handler                         │
└──────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Current Implementation Summary
* **Adapters (`cloud_llm_adapter.py`, `ollama_adapter.py`)**: `CloudTextGenAdapter` takes a provider name, base URL, and static default model. It implements `ITextGenerationCapability`.
* **Service Bus (`service_bus.py`)**: `AIServiceBus` resolves the active adapter using a simple dictionary lookup based on `settings.default_llm.lower()`.
* **Model Registry (`model_registry.py`)**: Registers hardcoded models like `llama3:8b`, `openrouter`, and `groq` into a static `ModelRegistry` dictionary.
* **Settings Endpoints (`settings.py`)**: Endpoints explicitly define `valid_llms = ["ollama", "groq", "openrouter"]`, store a single global string `_transient_api_key`, and push that key to both `openrouter_adapter` and `groq_adapter` simultaneously.
* **Frontend UI (`SystemSettings.tsx`)**: Hardcodes checks for `"openrouter"` and `"groq"`, renders a single API key input field, and hardcodes catalog dropdown options.

### 2.2 Architectural Weaknesses & Scalability Limitations

| Dimension | Current Architecture Defect | Impact & Risk |
|---|---|---|
| **Model Coupling** | Static hardcoded model strings (`llama3-8b-8192`, `meta-llama/llama-3-8b-instruct:free`) | **High Risk**: Runtime 400/404 errors whenever upstream cloud providers deprecate or remove models. |
| **Provider Coupling** | `valid_llms = ["ollama", "groq", "openrouter"]` hardcoded across 6+ files | **High Debt**: Adding a new provider requires code edits across backend & frontend. |
| **Credential Security** | Single global `_transient_api_key` in memory; `.env` values ignored | **Security & Bug**: Key entered for Groq is sent to OpenRouter; keys in `.env` are overridden or unused; keys passed plaintext in requests. |
| **Model Discovery** | Static 1-item lists returned for cloud providers; no live model querying | **Poor UX**: Users cannot select from available OpenRouter/Groq model catalogs or select new models (e.g. Llama 3.3 70B, Claude 3.5 Sonnet). Unfiltered catalog risks dumping embedding models into dropdowns. |
| **Restart Requirement** | No separation between secret storage and runtime selection | **Painful UX**: Users must restart desktop app or server to change default provider or test model. |
| **Rule Compliance** | Violates Rule #3 (Local-First), Rule #4 (Provider Independence), Rule #5 (Single Responsibility) | **Architecture Non-Compliance**: Application business logic is tightly bound to vendor names instead of provider-agnostic capabilities. |

---

## 3. Proposed High-Level Provider-Agnostic LLM Architecture

```
                       PROPOSED PROVIDER-AGNOSTIC ARCHITECTURE

┌──────────────────────────────────────────────────────────────────────────────────┐
│                      ATHENUS KNOWLEDGE OS APPLICATION LAYER                      │
│   (Chat, Blueprints, Flashcards, Quizzes, Workspace Intelligence, Agents)        │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │ Consumes standard `ILLMProvider` interface
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                                LLM PROVIDER REGISTRY                             │
│  - Dynamically registers provider adapters via Two-Tier classification           │
│  - Resolves active provider adapter via `ProviderConfigResolver`                 │
│  - Performs concurrent `asyncio.gather` health checks & TTL model caching         │
│  - Capability-checked dispatch helper for AIServiceBus                           │
└────────────────────────────────────────┬─────────────────────────────────────────┘
                                         │
        ┌────────────────────────────────┼────────────────────────────────┐
        │                                │                                │
        ▼ (Tier 2 Adapter)               ▼ (Tier 1 Adapter)               ▼ (Tier 2 Adapter)
┌──────────────────────┐      ┌──────────────────────┐      ┌──────────────────────┐
│  OllamaLLMAdapter    │      │ Generic OpenAICompat │      │   AnthropicAdapter   │
│  (Native `/api/tags` │      │ Adapter              │      │   (Native `/v1/      │
│   & `/api/generate`) │      │ (OpenRouter, Groq,   │      │    messages` API &   │
│                      │      │  OpenAI, DeepSeek,   │      │    SSE Format)       │
│                      │      │  NIM, LiteLLM, etc.) │      │                      │
└──────────────────────┘      └──────────────────────┘      └──────────────────────┘
                                         │
                                         ▼
┌──────────────────────────────────────────────────────────────────────────────────┐
│                            PROVIDER CONFIG RESOLVER                              │
│  - Secrets (API Keys): Process Environment / `.env` only (Never stored in DB)    │
│  - Runtime State: Active Provider ID, Model Override, Custom URLs (SQLite DB)    │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Technical Specifications & Interface Design

### 4.1 Two-Tier Adapter Classification

To eliminate ambiguity, provider integration is strictly categorized into two operational tiers:

1. **Tier 1 (Zero-Code Extension)**: Any provider exposing an OpenAI-compatible REST API (`/v1/chat/completions` and `/v1/models`). Adding a Tier 1 provider (OpenRouter, Groq, OpenAI, DeepSeek, NVIDIA NIM, Together AI, Fireworks AI, LiteLLM, LM Studio, vLLM) requires **zero python code edits**—only configuration entry in `ProviderConfigResolver`.
2. **Tier 2 (Dedicated Provider Adapter)**: Providers with non-OpenAI wire formats, custom system prompt positioning, or distinct SSE event schemas. Each Tier 2 provider receives a dedicated class inheriting from `BaseLLMProvider`:
   * `AnthropicProviderAdapter`: Native `/v1/messages` endpoint, `x-api-key` header, system prompt array structure, and Anthropic tool call framing.
   * `OllamaLLMAdapter`: Native Ollama `/api/tags` and `/api/generate` daemon API.

---

### 4.2 Generic Domain Base & LLM Interface (`ILLMProvider` & `BaseLLMProvider`)

Location: `backend/app/domain/ai/provider_interface.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncGenerator, Dict, List, Optional

@dataclass
class LLMProviderCapabilities:
    supports_streaming: bool = True
    supports_vision: bool = False
    supports_function_calling: bool = False
    supports_model_discovery: bool = True
    max_context_window: int = 128000

@dataclass
class LLMModelMetadataDTO:
    id: str
    name: str
    context_window: int = 4096
    owned_by: str = ""
    is_chat_model: bool = True
    size_bytes: Optional[int] = None

@dataclass
class ProviderHealthDTO:
    provider_id: str
    is_available: bool
    is_configured: bool
    active_model: str
    error_message: Optional[str] = None

class ILLMProvider(ABC):
    """Unified domain abstraction interface for all LLM text generation providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Immutable, versioned provider identifier (e.g. 'ollama', 'openrouter', 'groq', 'openai', 'anthropic')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider display label."""
        pass

    @property
    @abstractmethod
    def is_local(self) -> bool:
        """Flag indicating whether execution is local (zero latency/offline) or cloud API."""
        pass

    @abstractmethod
    async def get_capabilities(self) -> LLMProviderCapabilities:
        """Retrieve capability flags for the active provider."""
        pass

    @abstractmethod
    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        """Dynamically discover available chat models from the provider API with TTL caching."""
        pass

    @abstractmethod
    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        """Execute non-streaming text generation."""
        pass

    @abstractmethod
    async def stream(self, request: TextGenerationRequest) -> AsyncGenerator[str, None]:
        """Execute streaming text generation."""
        pass

    @abstractmethod
    async def check_health(self) -> ProviderHealthDTO:
        """Check API connectivity, credential validity, and active model status."""
        pass

class BaseLLMProvider(ILLMProvider):
    """Abstract base provider supplying sensible default implementations for common methods."""

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(supports_streaming=True, supports_model_discovery=True)

    async def check_health(self) -> ProviderHealthDTO:
        has_creds = bool(getattr(self, "api_key", "")) or self.is_local
        default_m = getattr(self, "default_model", "unknown")
        if not has_creds:
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=False,
                is_configured=False,
                active_model=default_m,
                error_message="Missing API key in .env"
            )
        try:
            models = await self.list_models()
            is_avail = len(models) > 0
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=is_avail,
                is_configured=True,
                active_model=models[0].id if models else default_m
            )
        except Exception as e:
            return ProviderHealthDTO(
                provider_id=self.provider_id,
                is_available=False,
                is_configured=True,
                active_model=default_m,
                error_message=str(e)
            )
```

---

### 4.3 Tier 1 Generic OpenAI-Compatible Adapter with `is_chat_model()` Filter

Location: `backend/app/infrastructure/adapters/openai_compatible_adapter.py`

```python
import httpx
import time
from typing import AsyncGenerator, Dict, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO, ProviderHealthDTO

NON_CHAT_KEYWORDS = (
    "embed", "embedding", "bge-", "rerank", "whisper", "guard", 
    "reward", "tts", "stt", "moderation", "transcription", "vector"
)

def default_is_chat_model(model_id: str) -> bool:
    """Predicate filtering out non-chat models (embeddings, rerankers, guardrails, STT/TTS)."""
    mid = model_id.lower()
    return not any(kw in mid for kw in NON_CHAT_KEYWORDS)

class OpenAICompatibleProviderAdapter(BaseLLMProvider):
    """Generic, reusable Tier 1 adapter for any OpenAI-compatible provider."""

    def __init__(
        self,
        provider_id: str,
        name: str,
        base_url: str,
        api_key: Optional[str],
        default_model: str,
        is_local: bool = False,
        extra_headers: Optional[Dict[str, str]] = None,
        http_client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self._provider_id = provider_id.lower()
        self._name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or ""
        self.default_model = default_model
        self._is_local = is_local
        self.extra_headers = extra_headers or {}
        self._http_client = http_client
        self._model_cache: List[LLMModelMetadataDTO] = []
        self._cache_timestamp: float = 0

    @property
    def provider_id(self) -> str:
        return self._provider_id

    @property
    def name(self) -> str:
        return self._name

    @property
    def is_local(self) -> bool:
        return self._is_local

    async def list_models(self, force_refresh: bool = False) -> List[LLMModelMetadataDTO]:
        now = time.time()
        # 1-Hour TTL Cache
        if not force_refresh and self._model_cache and (now - self._cache_timestamp < 3600):
            return self._model_cache

        if not self.api_key and not self.is_local:
            return [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Default)")]

        url = f"{self.base_url}/models"
        headers = self._build_headers()
        client = self._http_client or httpx.AsyncClient(timeout=10.0)
        try:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                raw_models = data.get("data", [])
                discovered = []
                for m in raw_models:
                    mid = m.get("id", "")
                    if mid and default_is_chat_model(mid):
                        discovered.append(LLMModelMetadataDTO(
                            id=mid,
                            name=mid,
                            context_window=m.get("context_length", 4096),
                            owned_by=m.get("owned_by", self.provider_id),
                            is_chat_model=True
                        ))
                if discovered:
                    self._model_cache = discovered
                    self._cache_timestamp = now
                    return discovered
        except Exception:
            pass
        finally:
            if not self._http_client:
                await client.aclose()

        return [LLMModelMetadataDTO(id=self.default_model, name=f"{self.default_model} (Configured Default)")]

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json", **self.extra_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers
```

---

### 4.4 Tier 2 Anthropic Native Adapter Spec (`AnthropicProviderAdapter`)

Location: `backend/app/infrastructure/adapters/anthropic_adapter.py`

```python
import httpx
from typing import AsyncGenerator, Dict, List, Optional
from app.domain.ai.capabilities import TextGenerationRequest, TextGenerationResponse
from app.domain.ai.provider_interface import BaseLLMProvider, LLMProviderCapabilities, LLMModelMetadataDTO

class AnthropicProviderAdapter(BaseLLMProvider):
    """Tier 2 Adapter implementing Anthropic's native `/v1/messages` API spec."""

    def __init__(
        self,
        api_key: Optional[str],
        base_url: str = "https://api.anthropic.com/v1",
        default_model: str = "claude-3-5-sonnet-latest",
        http_client: Optional[httpx.AsyncClient] = None
    ) -> None:
        self.api_key = api_key or ""
        self.base_url = base_url.rstrip("/")
        self.default_model = default_model
        self._http_client = http_client

    @property
    def provider_id(self) -> str:
        return "anthropic"

    @property
    def name(self) -> str:
        return "Anthropic Claude API"

    @property
    def is_local(self) -> bool:
        return False

    async def get_capabilities(self) -> LLMProviderCapabilities:
        return LLMProviderCapabilities(
            supports_streaming=True,
            supports_vision=True,
            supports_function_calling=True,
            max_context_window=200000
        )

    async def generate(self, request: TextGenerationRequest) -> TextGenerationResponse:
        if not self.api_key:
            return TextGenerationResponse(text="⚠️ Anthropic API Key Missing in .env", prompt_tokens=0, completion_tokens=0)

        url = f"{self.base_url}/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.default_model,
            "system": request.system_prompt or "You are Athenus AI.",
            "messages": [{"role": "user", "content": request.prompt}],
            "max_tokens": request.max_tokens or 1024,
            "temperature": request.temperature,
        }
        client = self._http_client or httpx.AsyncClient(timeout=30.0)
        try:
            resp = await client.post(url, headers=headers, json=payload)
            if resp.status_code == 200:
                data = resp.json()
                text = data["content"][0]["text"] if data.get("content") else ""
                usage = data.get("usage", {})
                return TextGenerationResponse(
                    text=text,
                    prompt_tokens=usage.get("input_tokens", 0),
                    completion_tokens=usage.get("output_tokens", 0)
                )
            return TextGenerationResponse(text=f"⚠️ Anthropic API Error ({resp.status_code}): {resp.text[:200]}")
        finally:
            if not self._http_client:
                await client.aclose()
```

---

### 4.5 Provider Registry Architecture & Concurrent Health Aggregation

Location: `backend/app/domain/ai/provider_registry.py`

```python
import asyncio
import time
from typing import Dict, List, Optional
from app.domain.ai.provider_interface import ILLMProvider, ProviderHealthDTO

class LLMProviderRegistry:
    """Centralized registry for resolving, listing, and querying LLM providers."""

    def __init__(self) -> None:
        self._providers: Dict[str, ILLMProvider] = {}
        self._health_cache: Dict[str, ProviderHealthDTO] = {}
        self._health_cache_time: float = 0

    def register(self, provider: ILLMProvider) -> None:
        """Register an instantiated provider adapter."""
        self._providers[provider.provider_id.lower()] = provider

    def get(self, provider_id: str) -> Optional[ILLMProvider]:
        """Resolve a registered provider by ID."""
        return self._providers.get(provider_id.lower())

    async def get_catalog(self, force_refresh: bool = False) -> List[Dict]:
        """Build provider catalog concurrently using `asyncio.gather` with 30s TTL health caching."""
        now = time.time()
        use_cached_health = not force_refresh and (now - self._health_cache_time < 30)

        async def fetch_provider_info(p: ILLMProvider) -> Dict:
            if use_cached_health and p.provider_id in self._health_cache:
                health = self._health_cache[p.provider_id]
            else:
                health = await p.check_health()
                self._health_cache[p.provider_id] = health

            models = await p.list_models(force_refresh=force_refresh)
            return {
                "id": p.provider_id,
                "name": p.name,
                "is_local": p.is_local,
                "is_configured": health.is_configured or p.is_local,
                "is_available": health.is_available,
                "active_model": health.active_model,
                "models": [{"id": m.id, "name": m.name, "size_bytes": m.size_bytes} for m in models],
                "error": health.error_message,
            }

        tasks = [fetch_provider_info(p) for p in self._providers.values()]
        catalog = await asyncio.gather(*tasks, return_exceptions=False)
        self._health_cache_time = now
        return catalog
```

---

## 5. Configuration Architecture & `ProviderConfigResolver`

### 5.1 Layered Configuration Model

To resolve the UX regression of process restarts, configuration is split into two distinct tiers:

1. **Secrets Tier (Read-Only from `.env` / Process Environment)**: API keys (`OPENROUTER_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, etc.) live strictly in process environment variables or `.env` files. Secrets are never saved to SQLite or exposed plaintext to the client.
2. **Runtime Preference Tier (Writable in SQLite DB)**: Active provider selection (`LLM_PROVIDER`), selected model override (`LLM_MODEL`), default STT provider, and custom base URL overrides are saved in SQLite (`settings` table) and managed via `ProviderConfigResolver`. Updating the active provider in the UI takes effect **immediately without restarting the process**.

### 5.2 Escape-Hatch Custom Provider Schema (`config.py`)

In addition to named environment variables, Athenus supports multiple custom OpenAI-compatible providers via structured JSON or indexed environment variables:

```python
# Custom OpenAI-compatible providers JSON array format:
# CUSTOM_LLM_PROVIDERS='[{"id":"fireworks","name":"Fireworks AI","base_url":"https://api.fireworks.ai/inference/v1","api_key":"...","default_model":"accounts/fireworks/models/llama-v3p3-70b-instruct"}]'
CUSTOM_LLM_PROVIDERS: Optional[str] = None
```

### 5.3 Log & Traceback Secret Redaction Standard
All HTTP logging and traceback handlers across Athenus are configured to sanitize headers matching `Authorization`, `x-api-key`, or key patterns matching `sk-*`, replacing them with redacted masks (`[REDACTED_API_KEY]`).

---

## 6. AIServiceBus Capability-Checked Dispatching

When `AIServiceBus` dispatches a text generation request, it performs capability negotiation against the active provider:

```python
class UnsupportedCapabilityError(RuntimeError):
    """Raised when an operation requests a capability not supported by the active LLM provider."""
    pass

class AIServiceBus:
    async def get_text_capability(self, required_capabilities: Optional[List[str]] = None) -> ILLMProvider:
        active_provider_id = self.config_resolver.get_active_provider_id()
        provider = self.registry.get(active_provider_id) or self.registry.get("ollama")
        if not provider:
            raise RuntimeError(f"No registered LLM provider found for '{active_provider_id}'.")

        if required_capabilities:
            caps = await provider.get_capabilities()
            for req in required_capabilities:
                if req == "vision" and not caps.supports_vision:
                    raise UnsupportedCapabilityError(f"Active provider '{provider.name}' does not support Vision capabilities.")
                if req == "function_calling" and not caps.supports_function_calling:
                    raise UnsupportedCapabilityError(f"Active provider '{provider.name}' does not support Function Calling.")
        return provider
```

---

## 7. Settings UX Architecture Redesign

The Settings page in `frontend/src/features/settings/SystemSettings.tsx` acts as an **Interactive Configuration Inspector & Hot-Swappable Selector**:

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                             SYSTEM LLM SETTINGS                                  │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Active LLM Provider:  [ OpenRouter API (Cloud Universal)              ▼ ]       │
│ Status:               🟢 Configured via .env (Key: sk-or-v1-***9f4a)            │
│                       🧪 [Test Connection]                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Active Model:         [ google/gemini-2.5-flash                        ▼ ]       │
│                       🔄 Refresh Model Catalog                                   │
├──────────────────────────────────────────────────────────────────────────────────┤
│ Provider Credentials & Health Overview:                                          │
│   • Ollama (Local Daemon):   🟢 Connected (llama3:8b, 4.7 GB)                   │
│   • OpenRouter:              🟢 Configured in .env (214 Chat Models Discovered) │
│   • Groq:                    🟢 Configured in .env (14 Chat Models Discovered)  │
│   • Anthropic:               🔴 Key missing in .env (Missing ANTHROPIC_API_KEY) │
├──────────────────────────────────────────────────────────────────────────────────┤
│ 💡 Credentials Notice: API keys are loaded securely from `.env`.                 │
│ Hot-swapping active provider and model updates instantly without server restart. │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Potential Risks & Mitigation Strategies

| Potential Risk | Impact | Recommended Mitigation |
|---|---|---|
| **Catalog Clutter (Non-chat models)** | Embeddings and guard models pollute model dropdown | Implement `is_chat_model()` filtering in `OpenAICompatibleProviderAdapter` from day one. |
| **Settings Page Latency** | Sequential provider health checks block UI load | Run provider health checks concurrently (`asyncio.gather`) with 30s TTL cache. |
| **Anthropic Wire Divergence** | Developers try to reuse generic adapter for Anthropic | Establish Two-Tier classification: Tier 2 `AnthropicProviderAdapter` handles native `/v1/messages`. |
| **TCP/TLS Handshake Overhead** | Re-creating `httpx.AsyncClient` on every request adds latency | Shared, adapter-owned `httpx.AsyncClient` connection pool managed during app boot/shutdown. |
| **Mid-Stream Disconnects** | Chat or agent loops crash unpredictably on network drops | Define standard `LLMStreamException` sentinel error chunks for uniform handling. |
| **Log Key Leakage** | API keys printed to stdout in traceback logs | Explicit header redaction middleware sanitizing `Authorization` and `x-api-key` headers. |

---

## 9. Phased Implementation Roadmap

### Phase 1 — Core Abstraction & Configuration Resolver (Backend Foundation)
* Create `backend/app/domain/ai/provider_interface.py` (`ILLMProvider`, `BaseLLMProvider`, capability DTOs).
* Create `backend/app/domain/ai/provider_registry.py` (`LLMProviderRegistry` with `asyncio.gather` health checks).
* Implement `ProviderConfigResolver` separating `.env` secrets from SQLite runtime state.

### Phase 2 — Adapter Implementations (Provider Integration)
* Implement Tier 1 `OpenAICompatibleProviderAdapter` with `is_chat_model()` filter and shared `httpx.AsyncClient`.
* Implement Tier 2 `AnthropicProviderAdapter` and refactor `OllamaLLMAdapter`.
* Register default providers (Ollama, OpenRouter, Groq, OpenAI, Anthropic) in `LLMProviderRegistry`.

### Phase 3 — API Endpoints & Service Bus Integration
* Update `backend/app/domain/ai/service_bus.py` with `UnsupportedCapabilityError` dispatch checks.
* Update `/settings/providers/catalog` and `/settings/providers/active` REST APIs.

### Phase 4 — Frontend Settings UX Overhaul
* Refactor `frontend/src/features/settings/SystemSettings.tsx` to render dynamic providers, models, status badges, model sizes, and interactive `Test Connection` button.

### Phase 5 — Verification, QA Matrix & Documentation Update
* Execute comprehensive pytest suite covering mock `httpx` transports (`respx`), capability checks, mid-stream exceptions, and zero-code custom provider registration.
* Update canonical documentation in `docs/ARCHITECTURE.md`.
