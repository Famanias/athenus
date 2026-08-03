# MEMORY.md

# Athenus — Memory Reference

---

## Overview

Living memory reference documenting memory layers and state persistence:

1. **Short-Term Memory**: Conversation turn state & Zustand UI store (`llmProvider`, `activeView`).
2. **Working Memory**: Active workspace context (`workspace_id`, `media_id`, active chat session).
3. **Long-Term Memory**: Persistent SQLite tables for `SystemSettings`, `ChatSessionTable`, `ChatMessageTable`, `ProcessingLogTable`, and SM-2 flashcard intervals.
4. **Semantic Memory**: Knowledge Graph concept linkages (`KnowledgeConceptTable`, `KnowledgeRelationTable`).
