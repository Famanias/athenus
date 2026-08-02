# DEPLOYMENT.md

# Athenus Knowledge OS — Deployment Strategies

---

## 1. Local Desktop Mode (Default)
* **Shell**: Tauri native binary (`src-tauri/`)
* **Backend**: PyInstaller bundled Python sidecar executable
* **Database**: Embedded SQLite (`./data/athenus.db`)
* **Vector Store**: Embedded Qdrant (`./data/qdrant`)
* **Models**: Local Ollama + Faster-Whisper + BGE Small Embeddings

## 2. Self-Hosted Server Mode (Docker Compose)
* Run backend via Uvicorn container: `docker-compose up -d`
* PostgreSQL for multi-user database storage
* Containerized Qdrant instance

## 3. Cloud Mode (Railway / VPS)
* FastAPI deployed to Railway / Coolify
* Supabase / PostgreSQL for cloud metadata
* Qdrant Cloud for managed vector database
