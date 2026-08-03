# CONTRIBUTING.md

# Contributing to Athenus

Thank you for your interest in contributing to **Athenus**!

---

## Architecture Principles

When contributing code, enforce the following non-negotiable rules:
1. **Architecture First**: Understand module boundaries before modifying code.
2. **Domain Layer Purity**: Business logic in `app/domain/` MUST remain pure Python with zero external framework or database dependencies.
3. **Provider Independence**: Implement new AI models behind strongly-typed Capability Interfaces (`ITextGenerationCapability`, `ISpeechToTextCapability`, `IEmbeddingCapability`).
4. **Local-First Default**: Ensure all core features function 100% offline without mandatory cloud services.
5. **Architecture Decision Records**: Document significant architectural decisions in `docs/adr/`.

---

## Development Workflow

1. Fork & clone the repository.
2. Setup environment configuration (`cp .env.example .env`).
3. Run the backend test suite:
   ```bash
   cd backend
   python -m pytest tests
   ```
4. Create small, focused pull requests targeting `main`.
