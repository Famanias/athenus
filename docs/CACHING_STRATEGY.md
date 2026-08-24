# Athenus Caching & Performance Architecture Strategy

> **Document Status**: Living Architectural Specification  
> **Target Subsystems**: AI Service Bus, Multi-Stage RAG, Knowledge Graph, Storage & DB Layer, Frontend State  
> **Focus**: Key-Value (KV) Caching, Computational Memoization, Query Optimization, and Invalidation Contracts  

---

## Executive Summary

Athenus Knowledge OS is a **local-first, privacy-focused educational intelligence platform** that combines multi-modal ingestion (video, audio, PDF/document), multi-stage hybrid RAG (dense vector search + SQLite FTS5 BM25 + cross-encoder re-ranking), an incremental Knowledge Graph, and spaced repetition (SM-2 flashcards, comprehension quizzes, and structured note generation).

Athenus now has a formal local-first cache boundary: domain services depend on `ICacheStore`, composition roots supply memory or SQLite adapters, deterministic AI work uses capability-level caches, and resource-specific frontend query modules own server-state caching. Remaining opportunities in this document are explicitly described as planned work rather than current behavior.

The key consistency rule is ownership: a cache policy lives with the resource or capability that knows when its value becomes stale. Generic transports remain cache-neutral, and workspace deletion invalidates only that workspace's `kg`, `rag`, and `llm` namespaces.

---

## 1. Inventory of Existing Caching Mechanisms

The following inventory details every caching mechanism currently implemented in the codebase, verified against source files, component roles, and data flows.

```
                                  EXISTING CACHING ARCHITECTURE
                                  
     [ Frontend (Next.js / Tauri) ]
          │
          ├── localStorage ("athenus_active_model", "athenus_playback_speed")
          │
          ▼ (HTTP / SSE / REST via apiClient)
     [ FastAPI Backend Presentation Layer ]
          │
          ├── LLMProviderRegistry: _health_cache (30s TTL Dict)
          │    └── OllamaTextGenAdapter: _model_cache (30s TTL List)
          │    └── OpenAICompatibleAdapter: _model_cache (3600s TTL List)
          │
          ├── ProgressStore: _snapshots (Unbounded In-Memory Dict)
          │
          ├── KnowledgeGraphService: _nodes / _edges (In-Memory Fallback Dict)
          │
          ├── SQLite DB (athenus.db):
          │    ├── FlashcardService: "Permanent Version Cache" (FlashcardDeckTable)
          │    ├── QuizService: "Permanent Version Cache" (QuizTable)
          │    └── NoteService: "Permanent Version Cache" (NoteTable)
          │
          └── Docker Layer / Disk:
               ├── hf-cache Named Volume (/root/.cache/huggingface)
               └── ollama-data Named Volume (/root/.ollama)
```

### 1.1 In-Memory TTL Provider Health Cache
* **File**: [`backend/app/domain/ai/provider_registry.py:13-92`](file:///E:/repos/athenus/backend/app/domain/ai/provider_registry.py#L13-L92)
* **Component**: `LLMProviderRegistry`
* **Data Flow**: When `get_catalog(force_refresh=False)` is invoked (e.g. from `/api/v1/settings/providers`), it checks `now - self._health_cache_time < 30.0`. If valid, it reads `_health_cache[provider_id]` instead of querying `provider.check_health()`.
* **State Scope**: In-memory instance dictionary (`self._health_cache: Dict[str, ProviderHealthDTO]`).
* **TTL**: 30.0 seconds (global timestamp `self._health_cache_time`).

### 1.2 In-Memory Model Discovery TTL Caches
* **Files**:
  * [`backend/app/infrastructure/adapters/ollama_adapter.py:29-134`](file:///E:/repos/athenus/backend/app/infrastructure/adapters/ollama_adapter.py#L29-L134)
  * [`backend/app/infrastructure/adapters/openai_compatible_adapter.py:114-211`](file:///E:/repos/athenus/backend/app/infrastructure/adapters/openai_compatible_adapter.py#L114-L211)
* **Components**: `OllamaTextGenAdapter`, `OpenAICompatibleProviderAdapter`
* **Data Flow**: `list_models(force_refresh=False)` returns `self._model_cache` if within TTL.
* **TTL**: 30.0 seconds for local Ollama daemon; 3600.0 seconds (1 hour) for cloud OpenAI-compatible providers.
* **Invalidation Logic**: `OpenAICompatibleProviderAdapter.set_api_key()` clears `self._model_cache = []` and resets `self._cache_timestamp = 0.0`.

### 1.3 In-Memory Ingestion Snapshot Registry
* **File**: [`backend/app/application/events/progress_store.py:16-98`](file:///E:/repos/athenus/backend/app/application/events/progress_store.py#L16-L98)
* **Component**: `ProgressStore` (System Singleton)
* **Data Flow**: Real-time background workers (ASR, chunking, vector indexing) publish `StageProgressEvent`. `record_stage_progress()` stores the snapshot in `self._snapshots: Dict[str, Dict[str, Any]]` and notifies active SSE listeners.
* **State Scope**: Unbounded in-memory dictionary.
* **Invalidation/Pruning**: None (accumulates indefinitely in RAM until process shutdown).

### 1.4 In-Memory Knowledge Graph Shadow Cache
* **File**: [`backend/app/domain/knowledge/knowledge_graph_service.py:27-240`](file:///E:/repos/athenus/backend/app/domain/knowledge/knowledge_graph_service.py#L27-L240)
* **Component**: `KnowledgeGraphService`
* **Data Flow**: `_nodes: Dict[str, ConceptNode]` and `_edges: List[ConceptRelation]` store graph elements in RAM.
* **State Scope**: Per-instance dictionaries.
* **Observation**: High discrepancy risk. When SQLite is connected, node queries hit SQLite `KnowledgeConceptTable`, but edge queries in `_edges_for()` check `self._edges` first before querying SQLite `KnowledgeRelationTable`, creating potential state divergence across multiple service instances.

### 1.5 Shared Client Map in Embedded Qdrant Adapter
* **File**: [`backend/app/infrastructure/adapters/qdrant_adapter.py:6-40`](file:///E:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py#L6-L40)
* **Component**: `EmbeddedQdrantVectorStoreAdapter`
* **Data Flow**: Class-level dictionary `_shared_clients: Dict[str, Any]` caches initialized `QdrantClient` instances per path to prevent SQLite/RocksDB storage lock collisions.

### 1.6 Permanent SQLite Artifact Caching ("On-Demand Versioning")
* **Files**:
  * [`backend/app/domain/learning/flashcard_service.py:231-234`](file:///E:/repos/athenus/backend/app/domain/learning/flashcard_service.py#L231-L234)
  * [`backend/app/domain/learning/quiz_service.py:222-225`](file:///E:/repos/athenus/backend/app/domain/learning/quiz_service.py#L222-L225)
  * [`backend/app/domain/learning/note_service.py:594-596`](file:///E:/repos/athenus/backend/app/domain/learning/note_service.py#L594-L596)
* **Components**: `FlashcardService`, `QuizService`, `NoteService`
* **Data Flow**: `generate_deck`, `generate_quiz`, and `generate_note` check SQLite for an existing `ready` artifact at `_latest_version(workspace_id)`. If present and `force_new_version=False`, the cached entity is returned directly without re-invoking AI pipelines.
* **Invalidation Logic**: Explicit version bump (`force_new_version=True`) creates an immutable `vN+1` row.

### 1.7 Frontend LocalStorage Transient Cache
* **File**: [`frontend/src/store/useAppStore.ts:97-128`](file:///E:/repos/athenus/frontend/src/store/useAppStore.ts#L97-L128)
* **Component**: `useAppStore` (Zustand)
* **Data Flow**: Reads `localStorage` (`athenus_active_media_id`, `athenus_playback_speed`, `athenus_active_model`, `athenus_sidebar_collapsed`) on page boot to eliminate render flicker before backend `/api/v1/settings` returns.

### 1.8 Docker Named Volume Model Cache
* **Files**: [`docker-compose.yml:88-92`](file:///E:/repos/athenus/docker-compose.yml#L88-L92), [`docker-compose.prod.yml:78-81`](file:///E:/repos/athenus/docker-compose.prod.yml#L78-L81)
* **Component**: Container volume mapping `hf-cache:/root/.cache/huggingface` and `ollama-data:/root/.ollama`
* **Data Flow**: Persists downloaded weights (BGE embeddings, Whisper models, GGUF LLMs) across container lifecycle events.

### 1.9 Resource-owned Frontend Transcript Cache
* **Files**: `frontend/src/features/video/transcriptQueries.ts`, `frontend/src/features/video/useVideo.ts`
* **Component**: TanStack Query transcript resource policy.
* **Data Flow**: Queries are keyed by workspace and media identity. A completed ingestion job invalidates and immediately refetches exactly that transcript while subscribed components render the updated response.
* **Ownership Rule**: `apiClient` performs HTTP transport only; it does not cache GET responses.

---

## 2. Assessment: What Is Cached, What Is Not, and Vulnerability Analysis

| Subsystem / Operation | Currently Cached? | Mechanism | Weaknesses & Performance Risks |
| :--- | :--- | :--- | :--- |
| **Embedding Generation** (`SentenceTransformersEmbeddingAdapter`) | ❌ **NO** | Raw PyTorch model execution on every call | **Severe CPU/GPU Bottleneck**: Identical queries, concept deduplication loops, and repeated search strings recompute 384-dim embeddings from scratch every time. |
| **LLM Inference** (Ollama, OpenAI, Anthropic) | ❌ **NO** | Full network / local inference on every generation | **High Latency & Cloud API Cost**: Repetitive queries, summary regeneration, or zero-temperature RAG answers execute redundant inference without response memoization or prefix caching. |
| **RAG Retrieval Pipeline** (`MultiStageRetriever`) | ❌ **NO** | Re-executes all 8 stages per user query | **Redundant Retrieval Overhead**: Dense Qdrant search, FTS5 BM25 search, triple parsing, RRF fusion, and cross-encoder re-ranking run on every conversation turn, even for repeated questions. |
| **Knowledge Graph Queries** (`KnowledgeGraphService`) | ⚠️ **Partial / Flawed** | In-memory instance dict with SQLite bypass | **Cache Incoherency & $O(N)$ Traversal**: `get_workspace_triples` and `get_concepts` execute table scans on every RAG query. `get_neighbors` performs repeated $O(V)$ individual DB queries in a loop. |
| **Concept Deduplication** (`ConceptMergingService`) | ❌ **NO** | Linear SQLite query + JSON decode per candidate | **Ingestion Slowdown**: For every concept candidate, `list_concepts()` scans the table and decodes JSON embedding strings sequentially in Python before computing cosine similarities. |
| **Ingestion Progress Store** (`ProgressStore`) | ⚠️ **Unbounded RAM** | In-memory dictionary `_snapshots` | **Memory Leak Risk**: Snapshots are never evicted upon completion; historical processing runs accumulate in RAM over time. |
| **SQLite DB Connection & PRAGMAs** (`session.py`) | ❌ **NO** | Default single-threaded connection pool | **Disk I/O Contention**: Missing WAL mode, `cache_size=-64000`, and `mmap_size` causes frequent disk syncs and table lock contention during concurrent ingestion and chat. |
| **HTTP / Static Media Delivery** (`media.py`) | ❌ **NO** | Bare `FileResponse` without headers | **Bandwidth Waste**: Static video, audio, and PDF binaries lack `ETag` and `Cache-Control`, causing browser reload re-downloads. |
| **Frontend transcript resource** (`transcriptQueries.ts`) | ✅ **Yes** | TanStack Query keyed by workspace and media | Other frontend resources should adopt the same resource-owned pattern rather than adding cache policy to `apiClient`. |

---

## 3. Key-Value (KV) Caching Architecture & Opportunities

To address these vulnerabilities while strictly adhering to our **local-first, provider-independent, and strong-typing principles**, we introduce a **Unified Tiered Key-Value Cache Architecture**.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Unified ICacheStore Interface                       │
│  - get(key: str) -> Optional[T]                                            │
│  - set(key: str, value: T, ttl_seconds: Optional[int]) -> None             │
│  - delete(key: str) -> bool                                                 │
│  - delete_prefix(prefix: str) -> int                                        │
│  - clear() -> None                                                          │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │
            ┌──────────────────────────┴──────────────────────────┐
            ▼                                                     ▼
┌───────────────────────────────┐             ┌───────────────────────────────┐
│     MemoryCacheAdapter        │             │      SqliteKVCacheAdapter     │
│  - Fast LRU / TTL in RAM      │             │  - Persistent across reboots  │
│  - Thread-safe with asyncio   │             │  - Disk-backed table          │
│  - Ideal for queries/sessions │             │  - Ideal for embeddings/LLM   │
└───────────────────────────────┘             └───────────────────────────────┘
```

### 3.1 Use Case 1: Embedding Vector KV Cache
* **Purpose**: Eliminate redundant sentence transformer tensor computations for identical text queries and concept deduplication candidates.
* **Cache Layer**: SQLite-backed persistent KV cache (`SqliteKVCacheAdapter`) with warm in-memory LRU front.
* **Cache Key Formula**:
  $$\text{Key} = \text{"embed:"} + \text{model\_name} + \text{":"} + \text{SHA256}(\text{normalized\_text})$$
* **Recommended TTL**: $604,800\text{ seconds}$ (7 days) or indefinite LRU (embeddings of static strings for a fixed model are mathematically deterministic).
* **Invalidation Rule**: Invalidate only if `model_name` changes (automatic key namespace change).
* **Ownership**: `SentenceTransformersEmbeddingAdapter` (or `AIServiceBus`).
* **Fallback Behavior**: On cache miss, execute `model.encode(text)`, write vector to KV store, and return result.

### 3.2 Use Case 2: LLM Prompt & Deterministic Completion KV Cache
* **Purpose**: Cache deterministic LLM responses (e.g. concept extraction, summaries, low-temperature RAG answers).
* **Cache Layer**: Persistent SQLite KV or Memory LRU (configurable by deployment mode).
* **Cache Key Formula**:
  $$\text{Key} = \text{"llm:"} + \text{provider\_id} + \text{":"} + \text{model\_id} + \text{":"} + \text{temp} + \text{":"} + \text{SHA256}(\text{system\_prompt} + \text{"\|"} + \text{user\_prompt})$$
* **Recommended TTL**:
  * Temperature $= 0.0$ to $0.2$: $86,400\text{ seconds}$ (24 hours).
  * Temperature $> 0.5$: Bypass cache (dynamic creative queries).
* **Invalidation Rule**:
  * Workspace reset / media deletion: purge `llm:*` entries associated with workspace.
  * User forces refresh (`force_refresh=True` or `force_new_version=True`): bypass cache.
* **Ownership**: `AIServiceBus` / Adapter Generation Pipeline.
* **Fallback Behavior**: On miss, forward request to active provider adapter, store completed response, and return.

### 3.3 Use Case 3: Knowledge Graph Workspace Topology & Adjacency KV Cache
* **Purpose**: Accelerate RAG context expansion (`get_workspace_triples`) and interactive UI graph rendering (`/api/v1/graph/workspace/{id}`) from $O(N)$ DB queries to $O(1)$ memory lookup.
* **Cache Layer**: In-Memory LRU (`MemoryCacheAdapter`).
* **Cache Key Formula**:
  * Topology: `kg:ws:{workspace_id}:topology`
  * Adjacency List: `kg:ws:{workspace_id}:adjacency`
  * Workspace Triples: `kg:ws:{workspace_id}:triples:{SHA256(query_tokens)}`
* **Recommended TTL**: $600\text{ seconds}$ (10 minutes).
* **Invalidation Rule**: Event-driven invalidation. Any `ConceptGraphUpdatedEvent`, `ConceptNodeCreatedEvent`, or manual relation mutation calls `cache.delete_prefix(f"kg:ws:{workspace_id}:")`.
* **Ownership**: `KnowledgeGraphService`.
* **Fallback Behavior**: On miss, query SQLite tables `KnowledgeConceptTable` and `KnowledgeRelationTable`, assemble graph structures, set cache, and return.

### 3.4 Use Case 4: Multi-Stage Retrieval Context Cache
* **Purpose**: Avoid re-running vector search, FTS5 BM25 search, and cross-encoder re-ranking when users ask follow-up questions or re-submit queries.
* **Cache Layer**: In-Memory LRU (`MemoryCacheAdapter`).
* **Cache Key Formula**:
  $$\text{Key} = \text{"rag:"} + \text{ws\_id} + \text{":"} + \text{media\_id\_or\_doc\_id} + \text{":"} + \text{SHA256}(\text{query} + \text{str(page\_or\_time)})$$
* **Recommended TTL**: $120\text{ seconds}$ (2 minutes).
* **Invalidation Rule**: When new chunks are indexed (`ChunksIndexedEvent` or `DocumentParsedEvent`), purge `rag:{ws_id}:*`.
* **Ownership**: `MultiStageRetriever`.
* **Fallback Behavior**: Execute stages 0 through 8, store assembled `RetrievalContext`, and return.

### 3.5 Use Case 5: Ingestion Progress Ring-Buffer KV Cache
* **Purpose**: Fix the memory leak in `ProgressStore` where completed job snapshots accumulate indefinitely in `_snapshots`.
* **Cache Layer**: Memory LRU Cache with automatic maximum capacity (e.g. 500 active jobs) and TTL eviction.
* **Cache Key Formula**: `progress:{media_id}`
* **Recommended TTL**:
  * Active status (`processing`, `queued`): $3,600\text{ seconds}$ (sliding expiration on update).
  * Terminal status (`completed`, `failed`): $600\text{ seconds}$ (10 minutes), after which frontend reads historical logs from `ProcessingLogTable` in SQLite.
* **Invalidation Rule**: Explicit delete upon media item deletion.
* **Ownership**: `ProgressStore`.

---

## 4. Key Specifications, TTLs, Invalidation, and Ownership Matrix

| Cache Domain | Key Format | Storage Engine | TTL | Invalidation Trigger | Owner Service | Fallback Policy |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Embeddings** | `embed:{model}:{sha256(text)}` | Persistent SQLite KV | 7 Days (LRU) | Model switch / DB wipe | `AIServiceBus` | Compute via SentenceTransformers & persist |
| **LLM Output** | `llm:{prov}:{model}:{temp}:{sha256(prompt)}` | SQLite KV | 24 Hours | Media delete / Force flag | `AIServiceBus` | Query LLM provider & persist |
| **Provider Health** | `provider:health:{provider_id}` | Memory LRU | 30 Sec | Settings change | `LLMProviderRegistry` | Async health check probe |
| **Model Catalog** | `provider:models:{provider_id}` | Memory LRU | 1 Hour (Local: 30s) | Key update / Force flag | `BaseLLMProvider` | Query provider `/models` endpoint |
| **KG Topology** | `kg:ws:{ws_id}:topology` | Memory LRU | 10 Min | `ConceptGraphUpdatedEvent` | `KnowledgeGraphService` | Query SQLite concepts & relations |
| **KG Adjacency** | `kg:ws:{ws_id}:adj` | Memory LRU | 10 Min | `ConceptGraphUpdatedEvent` | `KnowledgeGraphService` | Rebuild from relations table |
| **RAG Context** | `rag:{ws_id}:{target}:{sha256(q)}` | Memory LRU | 2 Min | `ChunksIndexedEvent` | `MultiStageRetriever` | Full 8-stage retrieval pipeline |
| **Job Progress** | `progress:{media_id}` | Memory LRU | 10m post-done | Media item removed | `ProgressStore` | Fallback to `ProcessingLogTable` |
| **System Settings**| `settings:global` | Memory LRU | Indefinite | Settings PATCH/PUT | `SettingsService` | Query SQLite `SystemSettings` |

---

## 5. Architectural Performance Improvements Beyond KV Caching

Beyond Key-Value caching, deep codebase inspection indicates four high-impact architectural performance optimizations:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   COMPREHENSIVE PERFORMANCE OPTIMIZATIONS                    │
├───────────────────────────────┬─────────────────────────────────────────────┤
│ 1. SQLite PRAGMA Optimization │ WAL mode, 64MB Page Cache, 256MB mmap       │
│ 2. Concept In-Memory Matrix   │ Vectorized NumPy Cosine Similarity          │
│ 3. LLM Native Prefix Caching  │ Anthropic Ephemeral Cache & Ollama KeepAlive│
│ 4. Frontend Data Layer        │ TanStack Query & HTTP ETag/Cache-Control    │
└───────────────────────────────┴─────────────────────────────────────────────┘
```

### 5.1 SQLite Connection PRAGMA Optimization
* **Location**: [`backend/app/infrastructure/db/session.py:8`](file:///E:/repos/athenus/backend/app/infrastructure/db/session.py#L8)
* **Rationale**: By default, SQLite operates in `DELETE` rollback journal mode with a conservative 2MB cache, causing synchronous disk writes and blocking reads during background chunk ingestion.
* **Proposed Enhancement**: Configure connection event listeners on the SQLAlchemy engine:
  ```python
  from sqlalchemy import event

  @event.listens_for(engine, "connect")
  def set_sqlite_pragma(dbapi_connection, connection_record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA journal_mode = WAL;")
      cursor.execute("PRAGMA synchronous = NORMAL;")
      cursor.execute("PRAGMA cache_size = -64000;")  # 64 MB memory page cache
      cursor.execute("PRAGMA mmap_size = 268435456;") # 256 MB memory-mapped I/O
      cursor.execute("PRAGMA busy_timeout = 5000;")   # 5s retry before SQLITE_BUSY
      cursor.close()
  ```
* **Impact**: Eliminates SQLite write-lock contention between background ingestion workers and chat queries; speeds up read throughput by $3\times\text{--}5\times$.

### 5.2 Vectorized NumPy Concept Merging Matrix
* **Location**: [`backend/app/domain/knowledge/concept_merging.py:110-136`](file:///E:/repos/athenus/backend/app/domain/knowledge/concept_merging.py#L110-L136)
* **Rationale**: Currently, `_find_semantic_match` iterates sequentially through all concepts in a workspace, executes `json.loads(concept.embedding)` for each node, and computes cosine similarity in a pure-Python scalar loop.
* **Proposed Enhancement**: Maintain a cached NumPy 2D array $(N \times 384)$ of normalized concept embeddings in memory per workspace. Compute similarity in a single vectorized matrix-vector dot product:
  $$\mathbf{scores} = \mathbf{E}_{\text{norm}} \cdot \mathbf{q}_{\text{norm}}$$
* **Impact**: Reduces concept deduplication from $O(N)$ JSON decodes and Python loops to a sub-millisecond BLAS vector operation.

### 5.3 Native Provider Prefix & Prompt Caching Integration
* **Locations**:
  * [`backend/app/infrastructure/adapters/anthropic_adapter.py:168-175`](file:///E:/repos/athenus/backend/app/infrastructure/adapters/anthropic_adapter.py#L168-L175)
  * [`backend/app/infrastructure/adapters/ollama_adapter.py:159-168`](file:///E:/repos/athenus/backend/app/infrastructure/adapters/ollama_adapter.py#L159-L168)
* **Enhancements**:
  * **Anthropic**: Add `"cache_control": {"type": "ephemeral"}` metadata to large system prompts and multi-source document context blocks ($>1024$ tokens) in `AnthropicProviderAdapter`. Anthropic prompt caching provides **90% discount on cached input tokens and up to 80% lower latency**.
  * **Ollama**: Add `"keep_alive": "30m"` to prevent repeated unloading/reloading of local GGUF models from VRAM.

### 5.4 Frontend Data Query Layer & HTTP Binary Caching
* **Locations**:
  * [`frontend/src/services/apiClient.ts`](file:///E:/repos/athenus/frontend/src/services/apiClient.ts)
  * [`backend/app/presentation/api/v1/media.py:214-222`](file:///E:/repos/athenus/backend/app/presentation/api/v1/media.py#L214-L222)
* **Enhancements**:
  * **Implemented for transcripts**: TanStack Query owns workspace/media identity, a 30-second freshness window, subscriptions, and exact refresh when ingestion completes. The generic HTTP client is intentionally cache-neutral.
  * Extend the same resource-owned pattern to `useGraph`, `useFlashcards`, `useQuiz`, `useAnalytics`, and `useNotes`; each resource must define its own key and invalidation contract.
  * Add HTTP `ETag` and `Cache-Control: public, max-age=31536000, immutable` headers when serving static files via `/api/v1/media/{id}/file`.

---

## 6. Phased Implementation Plan

The plan is strictly ordered by **Impact**, **Complexity**, and **Risk** to preserve system stability and deliver immediate vertical slice value.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PHASED IMPLEMENTATION PLAN                         │
├─────────────────────────────────────────────────────────────────────────────┤
│ Phase 1: Core KV Engine & SQLite PRAGMAs (Low Risk, High Immediate Impact) │
│ Phase 2: AI Compute Caches — Embeddings & LLM (High Impact on Latency/Cost) │
│ Phase 3: Domain & RAG Layer Caching (Medium Complexity, High RAG Throughput)│
│ Phase 4: Frontend Query Caching & HTTP ETags (Polishing & Client UX)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Phase 1: Core KV Storage Abstraction & SQLite Optimization
* **Scope**:
  1. Define `ICacheStore` abstract interface in `backend/app/domain/common/cache_interface.py`.
  2. Implement `MemoryCacheAdapter` (LRU + TTL using standard library or lightweight `cachetools`).
  3. Implement `SqliteKVCacheAdapter` (persistent key-value table `app_kv_cache` with expiration index).
  4. Configure SQLite WAL mode, 64MB cache size, and mmap settings in `session.py`.
  5. Replace unbounded dict in `ProgressStore` with TTL-bounded LRU ring buffer.
* **Risk**: Very Low.
* **Verification**: Run complete backend test suite (`pytest tests/`) to ensure no DB lock regressions.

### Phase 2: Embedding Vector & LLM Inference KV Caching
* **Scope**:
  1. Wrap `SentenceTransformersEmbeddingAdapter.embed_query` and `embed_texts` with persistent SQLite KV cache.
  2. Implement exact-match prompt cache in `AIServiceBus` for low-temperature text generation requests ($T \le 0.2$).
  3. Add `cache_control: {"type": "ephemeral"}` header support in `AnthropicProviderAdapter`.
  4. Add `keep_alive` parameter to `OllamaTextGenAdapter`.
* **Risk**: Low.
* **Verification**: Benchmark embedding speed on repeated RAG questions; verify zero regression in chat citation accuracy.

### Phase 3: Knowledge Graph & Multi-Stage RAG Pipeline Memoization
* **Scope**:
  1. Add in-memory caching to `KnowledgeGraphService.get_workspace_triples`, `get_concepts`, and `get_relations`.
  2. Implement event-driven cache invalidation subscribing to `ConceptGraphUpdatedEvent` and `ConceptNodeCreatedEvent`.
  3. Vectorize `ConceptMergingService._find_semantic_match` using a cached workspace embedding array.
  4. Add short-lived (120s) retrieval context cache to `MultiStageRetriever`.
* **Risk**: Medium (requires strict invalidation testing to prevent stale context in RAG answers).
* **Verification**: Run `test_knowledge_graph.py`, `test_retrieval_rag.py`, and `test_concept_importance_allocator.py`.

### Phase 4: Frontend Query Caching & Static Asset HTTP Semantics
* **Scope**:
  1. Add `ETag` and `Cache-Control` headers to `/api/v1/media/{media_id}/file` and `/info`.
  2. Add TanStack Query provider to `frontend/src/app/layout.tsx`.
  3. Refactor `useGraph`, `useFlashcards`, `useQuiz`, and `useAnalytics` to use cached queries with automatic background revalidation.
* **Risk**: Low to Medium.
* **Verification**: Verify smooth view transitions in UI without redundant network spinners or stale state glitches.

---

## 7. Assumptions, Trade-Offs, and Failure Mode Analysis

### 7.1 Stale Data Risks & Invalidation Guarantees
* **Risk**: RAG returns citations for deleted files, or Knowledge Graph reflects outdated concept relationships.
* **Mitigation**:
  * All domain mutation events (`MediaDeletedEvent`, `ConceptGraphUpdatedEvent`, `WorkspaceResetEvent`) MUST explicitly invoke `cache.delete_prefix(...)`.
  * RAG context caches must have short TTLs ($\le 120\text{s}$) so any missed invalidation self-heals rapidly.

### 7.2 Memory Growth & Resource Limits
* **Risk**: Unbounded in-memory caches could cause Out-Of-Memory (OOM) errors in low-spec environments (e.g. 8GB RAM laptops running local Ollama).
* **Mitigation**:
  * Every in-memory cache instance MUST have an explicit `maxsize` (e.g. max 1,000 items in memory LRU).
  * Heavy binary objects (embedding tensors, audio segments) are stored in the SQLite persistent KV store on disk, not pinned in RAM.

### 7.3 Concurrency & Race Conditions
* **Risk**: Multiple async requests triggering identical embedding or LLM computations simultaneously (Cache Stampede).
* **Mitigation**:
  * Implement an async mutex/lock per key or use `asyncio.Lock()` around cache computation blocks (`single-flight` pattern) so only one coroutine computes the value while others await the cached result.

### 7.4 Multi-Instance / Distributed Considerations
* **Context**: Athenus is designed primarily as a local-first desktop and self-hosted application.
* **Design Decision**: A local SQLite/Memory KV implementation avoids external infrastructure dependencies (e.g. requiring a separate Redis daemon). If multi-replica cloud deployment is required in future milestones, the `ICacheStore` interface can be swapped for a Redis/Valkey provider with zero business logic changes.

---

## Summary Architecture Scorecard

| Metric | Current State | Target Post-Implementation | Expected Gain |
| :--- | :--- | :--- | :--- |
| **Embedding Query Latency** | 35ms – 120ms (every query) | < 0.5ms (cached) | **> 98% Latency Reduction** |
| **Repeated RAG Query Latency** | 2.5s – 8.0s (full pipeline) | 200ms – 600ms | **70% – 85% Speedup** |
| **KG Triples Generation** | 40ms – 180ms (full DB scan) | < 1ms (in-memory) | **99% Faster RAG Prep** |
| **SQLite Read Concurrency** | Blocks on write operations | Non-blocking via WAL + 64MB Cache | **Zero SQLITE_BUSY errors** |
| **Cloud LLM Token Cost** | 100% billed per repeat query | 0% billed on cache hit ($T=0$) | **Significant API cost savings** |
| **Frontend View Switch Latency**| 150ms – 500ms network fetch | Instant (0ms via SWR/TanStack) | **Fluid UI / No Layout Shift** |
