# ADR 0009: Concept-Centric Knowledge Model & Provenance Grounding

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: Learning artifacts (flashcards, quiz questions) were previously coupled directly to raw transcript chunks. This led to fragmented cards, duplicate concepts across multiple lecture videos, and lack of a single unified knowledge model.
* **Decision**: Establish a **Concept-Centric Knowledge Foundation**. All downstream learning artifacts (flashcards, quizzes, study sessions) anchor directly to canonical `KnowledgeConceptTable` nodes in the knowledge graph. Provenance (`media_id`, `source_chunk_ids`, `start_time`, `end_time`) is aggregated on the concept and passed through to generated cards and questions.
* **Alternatives Considered**:
  - *Direct Chunk Coupling*: Flashcards tied to transcript chunks directly. Resulted in duplicated cards when multiple videos discussed the same topic.
  - *Global Fixed Taxonomy*: Predefining concepts using a hardcoded dictionary. Failed to adapt to domain-specific lecture videos.
* **Rationale**: Anchoring flashcards and quizzes to concepts (`Flashcard -> Concept -> Transcript Chunk`) creates a single knowledge model where concepts act as canonical domain entities across the workspace.
* **Trade-offs**: Requires a two-stage pipeline (concept extraction + entity deduplication before artifact generation), but guarantees 100% grounding, provenance traceability, and cross-media concept synthesis.
