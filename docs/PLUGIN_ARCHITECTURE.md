# PLUGIN_ARCHITECTURE.md

# Athenus Knowledge OS — Plugin Architecture

---

## Overview

Knowledge sources behave as modular **Plugins** feeding into a unified processing pipeline:

```text
Knowledge Sources
 ├── Video Plugin (Version 0.1)
 ├── PDF Plugin (Phase 3)
 ├── Audio Plugin (Phase 3)
 ├── Documentation Plugin
 └── Web & GitHub Plugin
          │
          ▼
Unified Processing Pipeline
 (Ingestion ──► Preprocessing ──► Chunking ──► Embedding ──► Qdrant Vector Storage)
```

Every plugin implements the standard `BasePlugin` interface:
* `extract_raw_content(source_path: str) -> ContentPayload`
* `extract_metadata(source_path: str) -> MetadataPayload`
* `parse_chunks(content: ContentPayload) -> List[TranscriptChunk]`
