---
trigger: always_on
---

# Development Rules

These rules are **non-negotiable** and apply to every change made in this repository.

---

# 1. Architecture First

Never begin implementation without understanding the architecture.

Before writing code:

* Read the relevant documentation.
* Identify affected modules.
* Explain the implementation plan.
* Consider tradeoffs.

Do not bypass the design process.

---

# 2. Vertical Slice Development

Every phase must produce a usable application.

Avoid building isolated infrastructure that provides no immediate user value.

Each completed phase should be deployable and demonstrable.

---

# 3. Local-First

Local functionality always takes priority.

Preferred execution order:

1. Local models
2. Free cloud providers
3. Premium cloud providers

The application should remain functional without internet access whenever practical.

---

# 4. Provider Independence

Never hardcode a specific AI provider into business logic.

All providers must be accessed through abstraction layers.

Supported provider categories include:

* LLMs
* Embeddings
* Speech-to-Text
* OCR
* Vision Models
* Vector Databases
* Storage Providers

Every provider should be replaceable with minimal code changes.

---

# 5. Single Responsibility

Classes, services, agents, and modules should have one clear responsibility.

Avoid "god objects."

---

# 6. Keep Files Small

Prefer multiple focused files over very large ones.

If a file becomes difficult to navigate, split it into logical modules.

---

# 7. Avoid Duplication

If the same logic appears multiple times:

Extract it.

Do not copy and paste implementations.

---

# 8. Strong Typing

Use explicit types whenever possible.

Avoid unnecessary use of generic types or untyped objects.

---

# 9. Documentation Is Required

Whenever architecture changes:

Update the corresponding documentation.

Code and documentation must evolve together.

---

# 10. Explain Complex Logic

Use comments only when they explain **why**, not **what**.

Prefer self-explanatory code.

---

# 11. Test New Features

Every new feature should include an appropriate testing strategy.

Consider:

* Unit Tests
* Integration Tests
* End-to-End Tests
* AI Evaluation

---

# 12. Security

Never commit:

* API keys
* Secrets
* Credentials

Validate all uploaded files.

Treat user input as untrusted.

---

# 13. Performance

Measure before optimizing.

Do not optimize based on assumptions.

Document performance bottlenecks.

---

# 14. AI Engineering Standards

Every AI feature should be:

* Observable
* Explainable
* Measurable

Track:

* Latency
* Token usage
* Retrieval quality
* Citation quality
* Cost (when applicable)

---

# 15. Breaking Changes

Do not introduce breaking architectural changes without updating documentation and explaining the migration path.

---

# 16. Commit Quality

Each commit should represent one logical change.

Avoid mixing unrelated work.

---

# 17. Dependencies

Prefer mature, well-maintained libraries.

Avoid introducing dependencies unless they provide clear value.

---

# 18. Simplicity

Prefer simple, maintainable solutions.

Avoid unnecessary complexity.

Future extensibility should come from good architecture—not overengineering.
