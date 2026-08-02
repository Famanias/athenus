# DATABASE.md

# Athenus Knowledge OS — Database Schemas & Storage Specifications

---

## 1. SQLite Relational Schema (`athenus.db`)

Managed via SQLModel / SQLAlchemy and Alembic migrations.

### Table: `workspaces`
```sql
CREATE TABLE workspaces (
    id VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    description VARCHAR,
    icon VARCHAR,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Table: `media_items`
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_media_items_workspace_id ON media_items (workspace_id);
```

### Table: `transcript_chunks`
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
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX ix_transcript_chunks_media_id ON transcript_chunks (media_id);
CREATE INDEX ix_transcript_chunks_workspace_id ON transcript_chunks (workspace_id);
```

---

## 2. Embedded Qdrant Vector Collection (`transcript_chunks`)

* **Storage Path**: `./data/qdrant`
* **Vector Configuration**: `384` dimensions (Cosine distance metric)
* **Point Payload Schema**:
```json
{
  "media_id": "med_a1b2c3d4",
  "workspace_id": "default",
  "text": "Artificial intelligence is transforming education by enabling personalized learning paths...",
  "start_time": 0.0,
  "end_time": 15.5,
  "chunk_index": 0
}
```
