# 4. AI Service Bus & Capability Routing

* **Status**: Accepted
* **Date**: 2026-08-02
* **Context**: Business logic should not call AI vendors (OpenAI, Gemini, Groq, Ollama) directly. A centralized gateway is required to handle routing, retries, model capability matching, telemetry, streaming, and caching.

## Decision
We implement a centralized **AI Service Bus** backed by a **Model Registry** and **Provider Router**. Domain layers interact exclusively with strongly-typed Capability Interfaces (`ITextGenerationCapability`, `ISpeechToTextCapability`, `IEmbeddingCapability`, etc.).

## Consequences
* **Positive**: Complete vendor independence, centralized telemetry and evaluation hooks, automated fallback routing based on local hardware resources.
* **Negative**: Additional abstraction layer requiring explicit capability adapter implementations.
