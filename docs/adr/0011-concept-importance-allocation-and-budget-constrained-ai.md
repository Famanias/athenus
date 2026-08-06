# ADR 0011: Concept Importance Allocation & Budget-Constrained AI Generation

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: Fixed item allocation per concept (e.g. static 2 cards per concept) produced sub-optimal study decks. Foundational or complex concepts (e.g. "React State") require more cards than simpler or peripheral concepts (e.g. "JSX Syntax").
* **Decision**: Implement a **Concept Importance Allocator** (`ConceptImportanceAllocator`). Concepts are dynamically scored and ranked based on:
  1. Graph Centrality: Degree of connected edges in `KnowledgeRelationTable`.
  2. Concept Weight: Explicit weight metadata assigned during graph extraction.
  3. Mastery Deficit: Concepts with low user mastery (<0.5) receive priority allocation boost.
  The total card/question count is capped by a user-configurable **Target Budget** (10 to 50 items per deck/quiz), adjustable inline via the Studio UI toolbar.
* **Alternatives Considered**:
  - *Fixed N Cards Per Concept*: Equal weighting regardless of concept importance or graph density.
  - *Unbounded AI Generation*: Generating unlimited items led to high LLM latency and redundant questions.
* **Rationale**: Importance allocation combined with budget constraints creates balanced, high-yield study materials that prioritize critical and low-mastery concepts while respecting compute/token budgets.
* **Trade-offs**: Slightly higher compute overhead during allocation planning, but yields vastly superior pedagogical quality.
