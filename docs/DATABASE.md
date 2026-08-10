# DATABASE.md — Athenus Relational & Vector Storage Specifications

This document defines the canonical relational database schema (SQLite) and vector collection parameters for **Athenus**.

---

## 1. SQLite Relational Schema (`./data/athenus.db`)

All tables are defined as dual-compatible **SQLModel** / **SQLAlchemy ORM** classes in `backend/app/infrastructure/db/models.py` with automatic startup schema migration (`init_db()`).

### Core System & Workspace Tables
- **`workspaces`**: Workspace definitions, metadata, custom settings JSON, and access timestamps.
- **`system_settings`**: Global provider configuration (`default_llm`, `selected_ollama_model`, `ollama_models_dir`, `default_stt`, `gpu_acceleration`).

### Ingestion & Media Asset Tables
- **`media_items`**: Uploaded asset metadata (`workspace_id`, `file_path`, `media_type` (`video`/`audio`/`document`), `duration_seconds`, `status`, `error_message`).
- **`transcript_segments`**: Raw Whisper ASR transcript output for video/audio assets (`media_id`, `start_time`, `end_time`, `text`).
- **`transcript_chunks`**: Processed ~500-word sub-chunks for document pages and video segments (`media_id`, `workspace_id`, `text`, `start_time`, `end_time`, `chunk_index`, `word_count`). Hard ceiling of $\le 750$ tokens per sub-chunk.
- **`transcript_chunks_fts`**: SQLite FTS5 full-text search virtual table (`chunk_id UNINDEXED`, `workspace_id UNINDEXED`, `text`). Mirrored automatically via native SQLite DB triggers:
  - `transcript_chunks_ai`: `AFTER INSERT ON transcript_chunks`
  - `transcript_chunks_au`: `AFTER UPDATE ON transcript_chunks`
  - `transcript_chunks_ad`: `AFTER DELETE ON transcript_chunks`
- **`processing_logs`**: Immutable telemetry audit trail for background processing stages (`stage`, `status`, `progress`, `message`, `error_message`).

### Conversational Memory Tables
- **`chat_sessions`**: Session containers bound to workspaces with session preview metadata (`title`, `last_message_at`, `message_count`, `preview_text`).
- **`chat_messages`**: Conversational turn turns (`session_id`, `workspace_id`, `sender`, `content`, `citations_json`).

### Knowledge Graph & Job Tables
- **`knowledge_concepts`**: Domain concept nodes with provenance grounding (`workspace_id`, `name`, `description`, `status`, `media_id`, `source_chunk_ids`, `start_time`, `end_time`, `embedding`).
- **`knowledge_relations`**: Directed graph relationship edges (`workspace_id`, `source_concept`, `target_concept`, `relation_type`, `weight`, `media_id`).
- **`concept_aliases`**: Exact and alias mapping table for entity deduplication (`concept_id`, `alias`).
- **`artifact_jobs`**: Async lifecycle job tracker for graph extraction, ingestion, and legacy document re-chunking migration (`workspace_id`, `artifact_type` (`ingestion`/`rechunk_ingestion`), `target_key`, `status`, `stage`, `progress`, `message`).

### Active Recall & Spaced Repetition Tables
- **`flashcard_decks`**: Versioned flashcard decks (`workspace_id`, `name`, `version`, `status`, `media_ids`, `concept_ids`, `card_count`).
- **`flashcards`**: Concept-grounded cards (`deck_id`, `workspace_id`, `concept_id`, `card_type`, `front`, `back`, `cloze_text`, `options_json`, `ease_factor`, `interval_days`, `repetitions`).
- **`flashcard_reviews`**: Immutable SM-2 review logs (`flashcard_id`, `workspace_id`, `rating`, `ease_factor`, `interval_days`, `repetitions`, `reviewed_at`).

### Diagnostic Quiz Studio Tables
- **`quizzes`**: Versioned quiz suites (`workspace_id`, `title`, `version`, `status`, `concept_ids`, `question_count`).
- **`quiz_questions`**: Concept-balanced multiple choice questions (`quiz_id`, `workspace_id`, `concept_id`, `question_text`, `options_json`, `correct_index`, `explanation`).
- **`quiz_attempts`**: Immutable quiz execution attempts (`quiz_id`, `workspace_id`, `version`, `score`, `total_questions`, `correct_count`, `answers_json`, `time_taken`).

### Precomputed Learning Analytics Tables
- **`workspace_analytics`**: Precomputed workspace summary counters (`workspace_id`, `total_media`, `total_concepts`, `total_flashcards`, `total_quiz_attempts`, `total_reviews`, `avg_quiz_score`, `total_study_seconds`, `review_streak_days`, `last_activity_at`).
- **`concept_mastery`**: Real-time concept retention scores (`concept_id`, `workspace_id`, `concept_name`, `mastery_level`, `review_count`, `quiz_correct`, `quiz_attempts`, `last_reviewed_at`).
- **`study_sessions`**: Activity log entries (`workspace_id`, `activity_type`, `started_at`, `ended_at`, `duration_seconds`).

---

## 2. Factory Reset Purge Sequence

When **CLEAR MY DATA** (`POST /api/v1/system/clear-data`) is invoked, `SystemResetService` executes a single transaction purging all tables in strict foreign key order (child tables first):

```
1. FlashcardReviewTable
2. FlashcardTable
3. FlashcardDeckTable
4. QuizAttemptTable
5. QuizQuestionTable
6. QuizTable
7. ConceptMasteryTable
8. WorkspaceAnalyticsTable
9. StudySessionTable
10. ConceptAliasTable
11. KnowledgeRelationTable
12. KnowledgeConceptTable
13. ArtifactJobTable
14. ChatMessageTable
15. ChatSessionTable
16. TranscriptSegmentTable
17. TranscriptChunkTable (and transcript_chunks_fts)
18. ProcessingLogTable
19. MediaItemTable
20. WorkspaceTable (re-initialized with default workspace)
21. SystemSettings (reset to defaults)
```

---

## 3. Embedded Qdrant Vector Storage (`transcript_chunks`)

- **Storage Path**: `./data/qdrant`
- **Collection Name**: `transcript_chunks`
- **Vector Dimension**: 384 (`BAAI/bge-small-en-v1.5`)
- **Distance Metric**: Cosine Distance
- **Score Thresholding**: `score_threshold = 0.2` (filters low-relevance noise)
- **Point ID Scheme**: `uuid5(NAMESPACE_URL, chunk_id)`
