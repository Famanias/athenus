# ADR 0019: Provider-Agnostic LLM Architecture & Two-Tier Adapters

- **Status**: Accepted
- **Date**: 2026-08-07
- **Author**: Antigravity AI
- **Deciders**: Athenus Engineering Team

## Context

The previous LLM text generation provider implementation coupled provider selection, model identifiers, API keys, and settings UI components to hardcoded vendor strings (`ollama`, `groq`, `openrouter`). Upstream model deprecations caused runtime `400`/`404` errors, API keys leaked across cloud providers via a single shared transient variable, and settings could not dynamically incorporate arbitrary OpenAI-compatible or proprietary endpoints without core code modifications.

## Decision

We implemented a **Provider-Agnostic LLM Architecture**:

1. **Core Domain Protocols**: Defined standard `ILLMProvider` interface protocol and `BaseLLMProvider` abstract base class supplying credential validation and health checking.
2. **Layered Configuration Resolver (`ProviderConfigResolver`)**: Separates read-only `.env` secrets (`GROQ_API_KEY`, `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`) from SQLite runtime provider and model selection.
3. **Two-Tier Adapter Classification**:
   - **Tier 1 Generic Adapter**: `OpenAICompatibleProviderAdapter` supporting any OpenAI-compatible provider with `is_chat_model()` catalog filtering and connection pooling.
   - **Tier 2 Custom Adapters**: Dedicated `AnthropicProviderAdapter` (`/v1/messages`) and `OllamaTextGenAdapter` (`/api/tags` dynamic model discovery).
4. **Central Provider Registry**: `LLMProviderRegistry` supporting concurrent `asyncio.gather()` catalog retrieval with 30s health TTL cache and 1-hour model discovery TTL cache.
5. **Deprecation of Disk Scanner**: Replaced legacy filesystem path scanning (`ollama_models_dir`) with 100% native Ollama daemon HTTP API discovery (`/api/tags`).
6. **Frontend Settings Overhaul**: Transformed System Settings into an interactive configuration inspector and provider router with real-time `🧪 Test Connection` feedback and credential health badges.

## Consequences

- **Extensibility**: New providers (NVIDIA NIM, DeepSeek, Together AI, LiteLLM, LM Studio) can be registered without modifying domain logic.
- **Security & Reliability**: Eliminates API key cross-contamination across providers and respects `.env` configuration.
- **Docker & Cross-Platform Compatibility**: Eliminates container directory path access errors by using HTTP daemon model discovery.
