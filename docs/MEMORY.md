# MEMORY.md

# Athenus Knowledge OS — Memory Reference

---

## Overview

Living memory reference documenting memory layers and state persistence:

1. **Short-Term Memory**: Conversation turn state managed by `MemoryManager`.
2. **Working Memory**: Active workspace context (`workspace_id`, `media_id`).
3. **Long-Term Memory**: Persistent SQLite tables for `UserMemory`, `ConceptMastery`, and SM-2 flashcard intervals.
4. **Semantic Memory**: Knowledge Graph concept linkages (`ConceptNode`, `ConceptRelation`).
