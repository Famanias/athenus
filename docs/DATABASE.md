# DATABASE.md — Athenus Knowledge OS Database & Storage Specifications

Canonical database schema reference and vector storage specifications for Athenus Knowledge OS.

---

## 1. SQLite Relational Schema (`./data/athenus.db`)

Managed via SQLModel / SQLAlchemy with auto-creation on application startup (`init_db()`).

### Table: `workspaces`
Stores learning workspace definitions and metadata.
```sql
CREATE TABLE workspaces (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    icon VARCHAR,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `media_items`
Stores uploaded lecture video/audio asset records.
```sql
CREATE TABLE media_items (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    title VARCHAR NOT NULL,
    file_path VARCHAR NOT NULL,
    media_type VARCHAR DEFAULT 'video',
    file_size_bytes BIGINT DEFAULT 0,
    duration_seconds FLOAT DEFAULT 0.0,
    status VARCHAR DEFAULT 'pending',
    error_message VARCHAR,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_media_items_workspace_id ON media_items (workspace_id);
```

### Table: `transcript_chunks`
Stores semantic RAG text chunks extracted from transcripts.
```sql
CREATE TABLE transcript_chunks (
    id VARCHAR PRIMARY KEY,
    media_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    text TEXT NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    chunk_index INT NOT NULL,
    word_count INT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_transcript_chunks_media_id ON transcript_chunks (media_id);
CREATE INDEX ix_transcript_chunks_workspace_id ON transcript_chunks (workspace_id);
```

### Table: `transcript_segments`
Stores raw Whisper ASR transcript segments with timestamps.
```sql
CREATE TABLE transcript_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id VARCHAR NOT NULL,
    start_time FLOAT NOT NULL,
    end_time FLOAT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX ix_transcript_segments_media_id ON transcript_segments (media_id);
```

### Table: `chat_sessions`
Stores chat session containers bound to workspaces.
```sql
CREATE TABLE chat_sessions (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    title VARCHAR DEFAULT 'Chat Session',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_chat_sessions_workspace_id ON chat_sessions (workspace_id);
```

### Table: `chat_messages`
Stores user queries, assistant responses, and citation JSON payloads across sessions.
```sql
CREATE TABLE chat_messages (
    id VARCHAR PRIMARY KEY,
    session_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    sender VARCHAR NOT NULL,
    content TEXT NOT NULL,
    citations_json TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_chat_messages_session_id ON chat_messages (session_id);
CREATE INDEX ix_chat_messages_workspace_id ON chat_messages (workspace_id);
```

### Table: `processing_logs`
Stores immutable ingestion telemetry audit logs for every pipeline stage.
```sql
CREATE TABLE processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    media_id VARCHAR NOT NULL,
    workspace_id VARCHAR NOT NULL,
    stage VARCHAR NOT NULL,
    status VARCHAR DEFAULT 'processing',
    progress INT DEFAULT 0,
    message VARCHAR,
    error_message VARCHAR,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_processing_logs_media_id ON processing_logs (media_id);
CREATE INDEX ix_processing_logs_workspace_id ON processing_logs (workspace_id);
```

### Table: `knowledge_concepts`
Stores extracted domain entity concept nodes bound to workspaces.
```sql
CREATE TABLE knowledge_concepts (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    name VARCHAR NOT NULL,
    description TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_knowledge_concepts_workspace_id ON knowledge_concepts (workspace_id);
CREATE INDEX ix_knowledge_concepts_name ON knowledge_concepts (name);
```

### Table: `knowledge_relations`
Stores directional concept relationship triples for Knowledge Graph traversal.
```sql
CREATE TABLE knowledge_relations (
    id VARCHAR PRIMARY KEY,
    workspace_id VARCHAR NOT NULL,
    source_concept VARCHAR NOT NULL,
    target_concept VARCHAR NOT NULL,
    relation_type VARCHAR DEFAULT 'relates_to',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_knowledge_relations_workspace_id ON knowledge_relations (workspace_id);
CREATE INDEX ix_knowledge_relations_source_concept ON knowledge_relations (source_concept);
CREATE INDEX ix_knowledge_relations_target_concept ON knowledge_relations (target_concept);
```

---

## 2. Embedded Qdrant Vector Storage (`transcript_chunks`)

* **Storage Directory**: `./data/qdrant`
* **Collection Name**: `transcript_chunks`
* **Vector Dimension**: `384` (Cosine distance metric via `SentenceTransformersEmbeddingAdapter`)
* **Payload Schema & Mandatory Isolation Fields**:
```json
{
  "chunk_id": "chunk_9a8b7c6d",
  "workspace_id": "default",
  "media_id": "med_12345678",
  "text": "Gradient descent optimizes neural network parameters using partial derivatives...",
  "start_time": 12.5,
  "end_time": 28.0,
  "chunk_index": 1
}
```
* **Filter Conditions**: Search queries apply `Filter(must=[FieldCondition(key="workspace_id", match=MatchValue(value=filter_workspace_id))])` to enforce strict workspace boundaries.
