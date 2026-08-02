# RULES.md

# Development & Architecture Rules

---

1. **Architecture First**: Understand module boundaries before writing code.
2. **Vertical Slice Execution**: Deliver end-to-end usable features with every phase.
3. **Local-First Priority**: Core functionality must operate 100% offline without mandatory cloud dependencies.
4. **Provider Independence**: Access AI models strictly through capability abstractions (`ITextGenerationCapability`, `ISpeechToTextCapability`, `IEmbeddingCapability`).
5. **Domain Layer Purity**: Pure Python code in `app/domain/` with zero framework or database dependencies.
6. **Strong Typing & Testing**: Mandatory explicit types and passing pytest test coverage.
7. **ADR Process**: Document all major decisions in `docs/adr/`.
