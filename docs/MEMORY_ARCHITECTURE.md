# MEMORY_ARCHITECTURE.md

# Athenus Knowledge OS — Structured Memory Architecture

---

## Overview

Structured Memory in Athenus Knowledge OS is strictly separated into **Knowledge Storage** and **User Memory** across a **4-Layer Memory Model**:

```text
 ┌─────────────────────────────────────────────────────────────┐
 │                      4-Layer Memory Model                   │
 │                                                             │
 │  ┌──────────────────────┐       ┌──────────────────────┐    │
 │  │ 1. Short-Term Memory │       │  2. Working Memory   │    │
 │  │ (Active Chat Turn)   │       │(Active Workspace Context)│
 │  └──────────────────────┘       └──────────────────────┘    │
 │                                                             │
 │  ┌──────────────────────┐       ┌──────────────────────┐    │
 │  │ 3. Long-Term Memory  │       │ 4. Semantic Memory   │    │
 │  │(User Profile/SM-2)   │       │  (Knowledge Graph)   │    │
 │  └──────────────────────┘       └──────────────────────┘    │
 └─────────────────────────────────────────────────────────────┘
```

---

## Storage vs. Memory Separation

* **Knowledge Storage**: Immutable ingested knowledge units (`TranscriptChunk`s, vector embeddings in Qdrant, source media file paths).
* **User Memory**: Personal user learning state (`UserMemory`, `ConceptMastery` scores, SM-2/FSRS flashcard review timestamps, quiz accuracy, user notes).
