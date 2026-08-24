# Walkthrough: Caching and Performance Strategy Implementation

This document describes the implementation of [`docs/CACHING_STRATEGY.md`](docs/CACHING_STRATEGY.md), including the architecture, behavior, invalidation contracts, verification performed during implementation, and a manual QA plan.

Implementation commit: `a20904d feat: implement caching strategy`

## Outcome

The caching strategy was implemented across the backend, AI adapters, retrieval pipeline, knowledge graph, SQLite layer, HTTP media delivery, and frontend data layer.

The resulting architecture remains local-first:

- No Redis, Valkey, or external cache process is required.
- Short-lived application data is stored in a bounded in-memory LRU/TTL cache.
- Expensive deterministic AI results can persist in the existing SQLite database.
- Domain callers depend on one small cache interface rather than SQLite or in-memory implementation details.
- The deterministic LLM decorator handles cache read/write failures as misses, so provider generation remains the fallback path.

## 1. Unified Cache Module

### Domain interface

[`backend/app/domain/common/cache_interface.py`](backend/app/domain/common/cache_interface.py) defines `ICacheStore`, the common seam used by cache consumers:

```python
get(key: str) -> Optional[Any]
set(key: str, value: Any, ttl_seconds: Optional[float] = None) -> None
delete(key: str) -> bool
delete_prefix(prefix: str) -> int
clear() -> None
```

The interface keeps storage and expiry mechanics out of AI, graph, retrieval, settings, and progress modules.

### Memory cache adapter

[`backend/app/infrastructure/cache/memory_cache.py`](backend/app/infrastructure/cache/memory_cache.py) implements a thread-safe bounded LRU cache with:

- Per-entry TTLs.
- Least-recently-used eviction.
- Expired-entry pruning.
- Prefix invalidation.
- Explicit maximum capacity.
- A replaceable clock for deterministic TTL testing.
- An `RLock` protecting concurrent access.

The shared application cache is created with a maximum of 2,000 entries. Modules created directly in tests get isolated caches unless a shared cache is explicitly injected.

### Persistent SQLite cache adapter

[`backend/app/infrastructure/cache/sqlite_cache.py`](backend/app/infrastructure/cache/sqlite_cache.py) implements a persistent JSON key-value cache using the application database.

It lazily creates this table and index:

```sql
CREATE TABLE IF NOT EXISTS app_kv_cache (
    cache_key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    expires_at REAL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_app_kv_cache_expires_at
ON app_kv_cache (expires_at);
```

The adapter provides:

- Atomic SQLite upserts using `ON CONFLICT`.
- JSON encoding and decoding.
- Expired-row deletion on access.
- Explicit bulk pruning through `prune_expired()`.
- Escaped prefix deletion, including keys containing SQL wildcard characters.
- Persistent values across application restarts.
- Internal locking around database operations.

### Runtime cache instances

[`backend/app/infrastructure/cache/runtime.py`](backend/app/infrastructure/cache/runtime.py) exposes:

- `application_memory_cache`: shared application LRU/TTL cache.
- `persistent_cache`: SQLite-backed cache using the existing database engine.

The shared memory instance allows a graph mutation in one service instance to invalidate cached graph data used by another service instance.

## 2. SQLite Performance Profile

[`backend/app/infrastructure/db/session.py`](backend/app/infrastructure/db/session.py) now configures every SQLite connection with:

```sql
PRAGMA busy_timeout = 5000;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;
PRAGMA mmap_size = 268435456;
PRAGMA foreign_keys = ON;
```

Expected behavior:

- WAL permits readers to continue while ingestion writes are active.
- `synchronous=NORMAL` reduces unnecessary synchronization overhead while retaining WAL durability guarantees appropriate for this local application.
- `cache_size=-64000` allocates approximately 64 MiB to SQLite's page cache.
- `mmap_size=268435456` enables up to 256 MiB of memory-mapped database reads.
- `busy_timeout=5000` retries transient lock contention for up to five seconds.
- The profile is registered before migrations or table initialization use the engine.

## 3. Ingestion Progress Cache

[`backend/app/application/events/progress_store.py`](backend/app/application/events/progress_store.py) no longer stores snapshots in an unbounded dictionary.

The progress cache now has these rules:

| Snapshot state | TTL |
| --- | ---: |
| `processing`, `queued`, or other non-terminal state | 3,600 seconds |
| `completed` or `failed` | 600 seconds |
| Maximum retained snapshots | 500 |

Every update refreshes the entry's TTL. Processing history continues to be written to `ProcessingLogTable`, so cache eviction does not remove historical audit data.

`ProgressStore.delete(media_id)` supports explicit cleanup when a media deletion workflow uses it. Factory reset clears the complete progress cache.

## 4. Embedding Cache

[`backend/app/infrastructure/adapters/sentence_transformers_adapter.py`](backend/app/infrastructure/adapters/sentence_transformers_adapter.py) now caches embeddings at the adapter seam.

### Key construction

Text is normalized with Unicode NFKC normalization and whitespace collapsing. Case is preserved because changing case can change the embedding produced by a model.

```text
embed:{model_name}:{sha256(normalized_text)}
```

The model name is part of the namespace, so switching embedding models naturally produces cache misses without deleting vectors from other model namespaces.

### Behavior

- Persistent TTL: seven days.
- Shared in-memory cache acts as a hot front cache.
- SQLite provides persistence across backend restarts.
- Duplicate texts in the same batch are encoded only once.
- Results are restored to the original input order, including duplicates.
- The adapter rechecks misses inside an async computation lock.
- Only one model encoding batch can run at a time, preventing simultaneous requests from stampeding CPU/GPU execution.
- Empty input returns an empty result without model execution.

If `sentence-transformers` or its configured weights cannot be initialized, the existing mock-vector fallback is used. Cache read/write errors are treated as misses so embedding remains operational.

## 5. Deterministic LLM Completion Cache

[`backend/app/domain/ai/cached_text_generation.py`](backend/app/domain/ai/cached_text_generation.py) adds a provider decorator used by [`AIServiceBus`](backend/app/domain/ai/service_bus.py).

Tests and callers that construct an `AIServiceBus` without a cache retain the original provider identity and behavior. The application singleton injects the persistent SQLite cache.

### Eligibility

A non-streaming completion is cached only when:

- `temperature <= 0.2`, and
- `force_refresh` is false.

Higher-temperature requests bypass the cache. Streaming requests also bypass exact-response caching and delegate directly to the provider.

### Key construction

```text
llm:ws:{workspace_id}:{provider_id}:{model_id}:{temperature}:{sha256(request_fingerprint)}
```

The request fingerprint includes:

- System prompt.
- User prompt.
- Maximum output tokens.
- Stop sequences.

Including these values avoids returning a response produced under different generation constraints. The provider and resolved model ID prevent cross-provider or cross-model reuse.

### Behavior

- TTL: 24 hours.
- Per-key async locks implement single-flight behavior.
- Concurrent identical requests wait for the first generation and then read its cached response.
- Text, token counts, and finish reason are persisted.
- Provider errors are not cached.
- `TextGenerationRequest` now supports optional `workspace_id` and `force_refresh` fields.
- `AIServiceBus.invalidate_workspace_cache(workspace_id)` deletes deterministic completions for one workspace.

The graph extraction worker supplies its workspace ID and uses temperature `0.1`, making deterministic extraction requests eligible for caching.

## 6. Native Provider Caching and Model Residency

### Anthropic prompt caching

[`backend/app/infrastructure/adapters/anthropic_adapter.py`](backend/app/infrastructure/adapters/anthropic_adapter.py) marks large prompt blocks with:

```json
{"cache_control": {"type": "ephemeral"}}
```

System prompts or user prompt/context blocks of at least 4,096 characters are sent as Anthropic content blocks with ephemeral cache metadata. Smaller prompts retain the original string payload shape for compatibility.

This applies to non-streaming and streaming Anthropic requests.

### Ollama model residency

[`backend/app/infrastructure/adapters/ollama_adapter.py`](backend/app/infrastructure/adapters/ollama_adapter.py) adds:

```json
{"keep_alive": "30m"}
```

to streaming and non-streaming generation requests. Ollama should keep the selected model resident for 30 minutes after use, reducing repeated model loading and VRAM churn.

The streaming payload now also forwards temperature and maximum generation tokens consistently.

## 7. Knowledge Graph Cache

[`backend/app/domain/knowledge/knowledge_graph_service.py`](backend/app/domain/knowledge/knowledge_graph_service.py) caches graph reads for ten minutes.

### Cache entries

```text
kg:ws:{workspace_id}:topology:nodes
kg:ws:{workspace_id}:topology:relations
kg:ws:{workspace_id}:adjacency
kg:ws:{workspace_id}:triples:{sha256(normalized_query)}
```

### Cached operations

- `get_concepts()`.
- `get_relations()`.
- Workspace adjacency construction.
- Filtered workspace triples used by RAG.

### Traversal improvements

- `get_neighbors()` now builds a concept map once instead of repeatedly querying the database for each neighboring ID.
- `shortest_path()` and `get_neighbors()` share the cached adjacency map.
- JSON-encoded `source_chunk_ids` are decoded correctly when database rows become domain nodes.

### Invalidation

The complete `kg:ws:{workspace_id}:` prefix is deleted when:

- A node is added.
- An edge or relation is added or updated.
- Concept merging creates or updates a canonical concept.
- `ConceptGraphUpdatedEvent` is published.
- `ConceptNodeCreatedEvent` is published.
- A workspace is deleted.
- Factory reset is performed.

This prevents the ten-minute TTL from hiding newly extracted concepts or relations.

## 8. Vectorized Concept Matching

[`backend/app/domain/knowledge/concept_merging.py`](backend/app/domain/knowledge/concept_merging.py) replaces the scalar semantic matching loop with a cached, vectorized path.

For each workspace it caches:

```text
kg:ws:{workspace_id}:concept-matrix
```

The cached value contains eligible concepts and their decoded embedding vectors. A semantic lookup then:

1. Converts the vectors to a NumPy `float32` matrix.
2. Normalizes matrix rows and the query vector.
3. Computes all cosine similarities with one matrix-vector product.
4. Selects the maximum score.
5. Applies the existing semantic threshold of `0.88`.

If NumPy is unavailable or the matrix is malformed, matching falls back to the original scalar cosine implementation.

Creating or merging a concept invalidates the workspace graph prefix, including this matrix.

## 9. Multi-Stage Retrieval Cache

[`backend/app/infrastructure/retrieval/multi_stage_retriever.py`](backend/app/infrastructure/retrieval/multi_stage_retriever.py) wraps the complete retrieval pipeline in a two-minute memory cache.

### Key construction

```text
rag:{workspace_id}:{document_id|media_id|workspace}:{sha256(context_fingerprint)}
```

The context fingerprint includes:

- Normalized query.
- Source type.
- Current video timestamp.
- Current document page.
- Selected text.

This prevents an answer assembled for one page, timestamp, or text selection from being reused in a different active context.

### Behavior

- TTL: 120 seconds.
- Cached `RetrievalContext` objects are deep-copied on read and write so callers cannot mutate the cached value.
- Per-key async locks prevent duplicate dense search, FTS5 search, graph traversal, and reranking work for concurrent identical requests.
- `force_refresh=True` bypasses the cache.
- Conversational-query guard results are cached as well as full RAG results.

### Invalidation

`ChunksIndexedEvent` deletes `rag:{workspace_id}:`, so newly indexed media becomes visible immediately. Workspace deletion and factory reset also clear relevant entries.

## 10. Settings Cache

[`backend/app/domain/settings/settings_service.py`](backend/app/domain/settings/settings_service.py) caches the global settings record under:

```text
settings:global
```

The cache has no automatic expiry. `update_settings()` commits the database update and replaces the cached value immediately. Returned Pydantic models are deep-copied so a caller cannot mutate the shared cached record.

Factory reset clears the cached settings entry before the settings table is reset.

## 11. Cache Lifecycle and Invalidation Wiring

The shared invalidation paths are registered in:

- [`backend/app/bootstrap/event_subscribers.py`](backend/app/bootstrap/event_subscribers.py)
- [`backend/app/application/events/media_event_handlers.py`](backend/app/application/events/media_event_handlers.py)
- [`backend/app/domain/workspace/workspace_service.py`](backend/app/domain/workspace/workspace_service.py)
- [`backend/app/application/services/system_reset_service.py`](backend/app/application/services/system_reset_service.py)

### Workspace deletion

Deleting a workspace clears:

```text
kg:ws:{workspace_id}:*
rag:{workspace_id}:*
llm:ws:{workspace_id}:*
```

### Factory reset

Factory reset clears:

- Progress snapshots.
- The complete shared memory cache.
- All rows in `app_kv_cache`.
- Existing Qdrant, SQLite domain data, and uploaded files through the pre-existing reset flow.

The `app_kv_cache` table remains available after reset, but contains zero rows.

## 12. HTTP Media Caching

[`backend/app/presentation/api/v1/media.py`](backend/app/presentation/api/v1/media.py) adds HTTP cache semantics.

### Media file endpoint

`GET /api/v1/media/{media_id}/file` now returns:

```http
ETag: "<sha256-of-media-id-size-and-mtime>"
Cache-Control: public, max-age=31536000, immutable
```

When `If-None-Match` matches the current ETag, the endpoint returns `304 Not Modified` without sending the file body.

### Media information endpoint

`GET /api/v1/media/{media_id}/info` returns an ETag derived from its serialized response and:

```http
Cache-Control: private, max-age=30, stale-while-revalidate=30
```

It also returns `304 Not Modified` for a matching `If-None-Match` request.

## 13. Frontend Query Cache and Request Deduplication

TanStack Query was added to [`frontend/package.json`](frontend/package.json).

[`frontend/src/services/queryClient.ts`](frontend/src/services/queryClient.ts) configures:

| Setting | Value |
| --- | ---: |
| Default stale time | 30 seconds |
| Garbage collection time | 5 minutes |
| Query retries | 1 |
| Refetch on window focus | Disabled |

[`frontend/src/app/QueryProvider.tsx`](frontend/src/app/QueryProvider.tsx) exposes this client to the Next.js application through the root layout.

[`frontend/src/services/apiClient.ts`](frontend/src/services/apiClient.ts) integrates the query client at the shared request seam, so existing Graph, Flashcards, Quiz, Analytics, Notes, Library, and Settings hooks gain caching without changing their public return shapes.

### GET behavior

- Identical concurrent requests share one network operation.
- Fresh cached results are returned immediately for 30 seconds.
- Stale results are returned while a background revalidation is started.
- `/status` and `/jobs` requests use `staleTime: 0` so progress polling remains live.

### Mutation behavior

After a successful non-GET request, all cached application queries are invalidated. The next read therefore retrieves the updated server state rather than using a stale pre-mutation value.

## 14. Failure Modes and Safety Properties

The implementation preserves these guarantees:

- A cache miss always falls through to the authoritative computation or database query.
- SQLite cache corruption for one JSON value deletes that value and treats it as a miss.
- Deterministic LLM cache read/write failures do not replace successful provider results with errors.
- High-temperature and streaming LLM requests are never replayed from the exact-response cache.
- Model IDs and provider IDs prevent cache reuse after a model/provider switch.
- Workspace prefixes prevent deterministic LLM results from leaking between workspaces.
- Every memory cache has an explicit maximum size.
- Large embeddings are persisted as JSON vectors rather than model tensors.
- Retrieval objects are copied to avoid mutation-based cache corruption.
- Misses are rechecked inside locks to prevent cache stampedes.
- Short RAG TTLs provide a self-healing limit even if an invalidation event is missed.

## 15. CI Foreign-Key Regression Correction

Enabling `PRAGMA foreign_keys = ON` exposed a pre-existing inconsistency in note deletion on a brand-new CI database. The SQLModel definitions generated `NO ACTION` constraints from notes to folders and from note sections to notes, while the fallback SQLAlchemy definitions already declared `ON DELETE CASCADE`.

The folder deletion service attempted to delete sections, notes, and the folder in one transaction. Because those models do not define ORM relationships, SQLAlchemy did not have enough relationship metadata to order the queued object deletes and attempted the folder delete first. SQLite correctly rejected that statement with `FOREIGN KEY constraint failed`.

The correction has two complementary parts:

- [`backend/app/infrastructure/db/models.py`](backend/app/infrastructure/db/models.py) now declares `ondelete="CASCADE"` on `NoteTable.folder_id` and `NoteSectionTable.note_id` in the SQLModel definitions, matching the fallback models. Fresh databases therefore create cascading constraints.
- [`backend/app/domain/learning/note_service.py`](backend/app/domain/learning/note_service.py) flushes each dependency level explicitly: sections first, notes second, then the folder. Direct note deletion also flushes section deletion before deleting the note. This preserves correct behavior for existing SQLite databases whose already-created constraints remain `NO ACTION`.

[`backend/tests/test_note_foreign_keys.py`](backend/tests/test_note_foreign_keys.py) locks down the model-level cascade contract. The existing endpoint regression verifies the complete generated-section, note, and folder deletion flow.

Adding `init_db()` to the failing test was not the solution: its media-seeding helper already calls `init_db()`, and CI was failing against a successfully initialized clean schema. The failure was the newly enforced referential-integrity contract exposing incorrect delete ordering and inconsistent DDL.

## 16. Automated Verification Completed

### Backend

Command:

```powershell
cd E:\repos\athenus\backend
$env:DATABASE_URL = "sqlite:///./data/ci_validation.db"
$env:QDRANT_PATH = "./data/ci_validation_qdrant"
$env:UPLOADS_DIR = "./data/ci_validation_uploads"
venv\Scripts\python.exe -m pytest -q tests
```

Result:

```text
193 passed, 1 warning in 68.72s
```

The warning is an existing Starlette `TestClient` deprecation warning and is unrelated to caching behavior.

New cache-focused coverage is in [`backend/tests/test_caching.py`](backend/tests/test_caching.py), including:

- Memory TTL, LRU, and prefix deletion.
- Persistent SQLite values and escaped prefixes.
- Embedding batch deduplication.
- LLM temperature eligibility and force-refresh behavior.
- SQLite connection PRAGMAs.

The CI foreign-key correction was also verified against both database states:

- An already-created schema with `NO ACTION` foreign keys, validating the explicit child-first flushes.
- A brand-new schema with `ON DELETE CASCADE`, validating the corrected SQLModel declarations.

The focused foreign-key and note-deletion checks passed with `3 passed` before the clean full-suite run.

Targeted graph, RAG, settings, reset, and cache verification also passed:

```text
30 passed, 1 warning
```

### Frontend

Commands:

```powershell
cd E:\repos\athenus\frontend
npm.cmd run typecheck
npm.cmd run build
```

Results:

- TypeScript completed with zero errors.
- Next.js production build completed successfully.
- Static routes were generated successfully.

### Dependency note

`npm install` reported four high-severity advisories in the dependency tree. No automatic `npm audit fix` was run because that can introduce unrelated or breaking dependency upgrades.

---

# Manual QA Validation

Use this section to validate the behavior in a real application session. Record Pass/Fail and any observations in the sign-off table at the end.

## Prerequisites

1. Back up any local data you want to preserve. The factory-reset validation intentionally deletes application data.
2. Start the backend using the normal project workflow.
3. Start the frontend using the normal project workflow.
4. Open browser developer tools and select the Network panel.
5. Have at least one supported media/document file ready for ingestion.
6. For provider-specific checks, have Ollama and/or Anthropic configured.

## QA-1: Verify SQLite cache table and PRAGMAs

From `E:\repos\athenus\backend`, run:

```powershell
venv\Scripts\python.exe -c "from app.infrastructure.db.session import engine; from sqlalchemy import text; c=engine.connect(); print({p:c.execute(text('PRAGMA '+p)).scalar() for p in ['journal_mode','synchronous','cache_size','mmap_size','busy_timeout','foreign_keys']}); c.close()"
```

Expected:

- `journal_mode` is `wal`.
- `synchronous` is `1` (`NORMAL`).
- `cache_size` is `-64000`.
- `mmap_size` is `268435456`.
- `busy_timeout` is `5000`.
- `foreign_keys` is `1`.

After the backend has performed at least one cached embedding or deterministic LLM request, run:

```powershell
venv\Scripts\python.exe -c "from app.infrastructure.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT cache_key, expires_at FROM app_kv_cache ORDER BY cache_key')).all()); c.close()"
```

Expected:

- The `app_kv_cache` table exists.
- Cached embedding rows start with `embed:`.
- Eligible deterministic LLM rows start with `llm:ws:`.

## QA-2: Verify embedding persistence and speedup

1. Ingest a document or media file and wait for vector indexing to complete.
2. Ask a question that causes retrieval against the workspace.
3. Record the response time.
4. Ask the identical question again.
5. Restart only the backend.
6. Ask the identical question once more.
7. Inspect `app_kv_cache` using the command in QA-1.

Expected:

- An `embed:{model}:...` row exists for the normalized retrieval query.
- The second request avoids repeated embedding model computation.
- After restart, the embedding remains available from SQLite.
- Restarting the backend with a different `EMBEDDING_MODEL_NAME` creates a different key namespace and does not reuse the old model's vector.

Timing varies with hardware, so use cache rows and the absence of model recomputation as the primary evidence rather than enforcing a strict millisecond threshold.

## QA-3: Verify deterministic LLM caching

1. Run an operation using temperature `0.2` or lower. Graph extraction uses temperature `0.1` and is the normal eligible application path.
2. Inspect `app_kv_cache` for a key beginning with `llm:ws:{workspace_id}:`.
3. Repeat the exact same eligible provider/model/prompt request within 24 hours.
4. Trigger the same request with `force_refresh=True` through a development call or test harness.
5. Run a request with temperature greater than `0.2`.

Expected:

- The first eligible request calls the provider and creates a row.
- The identical eligible request returns the same response without another provider call.
- Force refresh calls the provider even when a row exists.
- The higher-temperature request calls the provider every time and creates no exact-response cache entry.
- Switching provider or model produces a different cache key.

For a deterministic local validation without spending provider tokens, run:

```powershell
cd E:\repos\athenus\backend
venv\Scripts\python.exe -m pytest -q tests\test_caching.py -k deterministic_llm
```

Expected: `1 passed`.

## QA-4: Verify repeated RAG retrieval caching

1. Open a workspace containing indexed material.
2. Ask a non-conversational question about that material.
3. Immediately ask the identical question again with the same active media, page/timestamp, and selected text.
4. Ask the same question with a different active page, timestamp, or selected text.
5. Wait longer than two minutes and repeat the original question.

Expected:

- The immediate identical request is noticeably faster because dense search, FTS5, graph expansion, and reranking are reused.
- Changing page, timestamp, or selected text creates a miss and produces context appropriate to the new location.
- After two minutes the pipeline runs again.
- Citations and context provenance remain identical on a valid cache hit.

## QA-5: Verify RAG invalidation after indexing

1. Ask a question whose answer is not present in the current workspace.
2. Upload a document that directly answers the question.
3. Wait until its status reaches `completed` and `ChunksIndexedEvent` has run.
4. Ask the identical question again within two minutes of the first request.

Expected:

- The second answer can use the newly indexed document.
- It is not served from the earlier cached retrieval context.
- New citations reference the newly uploaded material when relevant.

## QA-6: Verify knowledge graph caching and invalidation

1. Open the Knowledge Graph view and allow it to load.
2. Navigate to another view, then return within ten minutes.
3. Upload material that creates new concepts or relations.
4. Wait for graph extraction to complete.
5. Return to or refresh the Knowledge Graph view.
6. Open concept neighbors and calculate a shortest path if the UI exposes those actions.

Expected:

- The repeated graph view loads without an unnecessary full graph database rebuild.
- Newly extracted concepts and relations appear immediately after the graph update event; they are not hidden for ten minutes.
- Neighbor traversal returns each concept once at the correct depth.
- Shortest paths reflect newly added relationships.

## QA-7: Verify concept merge vectorization remains correct

1. Ingest content containing a concept already present under the same name.
2. Ingest content containing a semantically equivalent alias.
3. Inspect the graph and concept count.

Expected:

- Exact names merge into the existing canonical concept.
- Strong semantic matches at or above the existing `0.88` threshold merge rather than create a duplicate.
- Provenance from both sources is retained.
- A genuinely distinct concept remains separate.
- A subsequent ingestion sees the newly created/updated concept, demonstrating matrix invalidation.

## QA-8: Verify progress snapshot lifecycle

1. Upload a file and watch its live ingestion progress.
2. Confirm progress updates continue through processing stages.
3. Confirm the terminal `completed` or `failed` snapshot remains visible immediately after processing.
4. Confirm `/api/v1/media/{media_id}/history` continues to show processing history independently of the in-memory snapshot.

Expected:

- SSE progress behavior is unchanged.
- Terminal state remains available for ten minutes.
- Historical processing logs remain available after the memory snapshot expires.
- The cache never retains more than 500 snapshots; automated coverage validates LRU/TTL mechanics.

## QA-9: Verify global settings caching

1. Open Settings and note the selected provider/model.
2. Navigate away and return within 30 seconds.
3. Change the provider or model and save.
4. Reload the page or restart the backend.

Expected:

- Repeated reads do not require repeated SQLite settings queries.
- A saved update appears immediately rather than showing the prior cached value.
- The updated value persists after restart.
- Provider/model changes naturally use new LLM and embedding cache namespaces.

## QA-10: Verify frontend request deduplication and stale-while-revalidate

1. Open browser developer tools and clear the Network log.
2. Open Graph, Flashcards, Quiz, Analytics, and Notes in turn.
3. Return to each view within 30 seconds.
4. Trigger two UI paths that request the same endpoint at nearly the same time, if available.
5. Wait more than 30 seconds and return to a previously viewed screen.
6. Perform a mutation such as creating/updating a note or generating a new deck, then revisit the relevant list.

Expected:

- Returning within 30 seconds renders from cache without a duplicate network request for the same GET URL.
- Concurrent identical GETs produce one backend network request.
- After 30 seconds, stale data can render immediately while one background request revalidates it.
- `/status` and `/jobs` requests continue to hit the backend on their polling interval.
- After a successful mutation, the next read fetches updated server data.

## QA-11: Verify media ETag and browser caching

Choose an existing media ID and run from the repository root:

```powershell
$mediaId = "REPLACE_WITH_MEDIA_ID"
$url = "http://127.0.0.1:8000/api/v1/media/$mediaId/file"
curl.exe -sS -D media-cache-headers.txt -o NUL $url
Get-Content media-cache-headers.txt
$etag = ((Select-String -Path media-cache-headers.txt -Pattern '^etag:' -CaseSensitive:$false).Line -replace '^etag:\s*','').Trim()
curl.exe -sS -D - -o NUL -H "If-None-Match: $etag" $url
```

Expected first response headers:

```text
ETag: "..."
Cache-Control: public, max-age=31536000, immutable
```

Expected second response: `304 Not Modified` with no media body.

Repeat against `/api/v1/media/{media_id}/info`.

Expected:

- An ETag is present.
- `Cache-Control` is `private, max-age=30, stale-while-revalidate=30`.
- A matching `If-None-Match` returns `304`.

Delete `media-cache-headers.txt` after the check if it is no longer needed.

## QA-12: Verify Ollama keep-alive

1. Select Ollama as the active provider.
2. Generate a chat response.
3. Run:

```powershell
ollama ps
```

4. Run it again several minutes later without sending another request.

Expected:

- The selected model remains loaded after generation.
- The model remains resident for up to approximately 30 minutes, subject to Ollama resource pressure and daemon policy.

## QA-13: Verify Anthropic prompt cache metadata

1. Select Anthropic as the active provider.
2. Use a request containing a system or user/context block of at least 4,096 characters.
3. Inspect the outgoing `/v1/messages` payload using a development proxy, adapter logging, or a mock transport.

Expected:

- Large blocks use Anthropic content-block form.
- The large block contains `"cache_control": {"type": "ephemeral"}`.
- Small prompts retain the normal string form.
- Streaming and non-streaming requests both apply the rule.

## QA-14: Verify workspace deletion invalidation

1. Create a temporary workspace.
2. Generate graph, retrieval, embedding, and eligible deterministic LLM cache activity in it.
3. Confirm matching cache keys exist where applicable.
4. Delete the workspace.
5. Query `app_kv_cache` again.

Expected:

- `llm:ws:{deleted_workspace_id}:*` rows are removed.
- Its graph and RAG memory entries are invalidated.
- Other workspaces continue functioning and retain their independent cache data.

## QA-15: Verify factory reset cleanup

Warning: this test deletes application data. Perform it only after backing up anything important.

1. Confirm `app_kv_cache` contains rows.
2. Use the application's Clear Data / Factory Reset action.
3. Query the cache table:

```powershell
cd E:\repos\athenus\backend
venv\Scripts\python.exe -c "from app.infrastructure.db.session import engine; from sqlalchemy import text; c=engine.connect(); print(c.execute(text('SELECT COUNT(*) FROM app_kv_cache')).scalar()); c.close()"
```

Expected:

- The result is `0`.
- Progress snapshots are cleared.
- The application creates a clean default workspace.
- The backend and frontend remain operational after reset.
- A later eligible operation recreates cache rows normally.

## QA-16: Regression smoke test

Complete one end-to-end learning flow:

1. Create or select a workspace.
2. Upload video, audio, or a document.
3. Wait for transcription/parsing, chunking, vector indexing, and graph extraction.
4. Ask a grounded question and verify citations.
5. Open the graph.
6. Generate notes, flashcards, and a quiz.
7. Review a flashcard and submit a quiz.
8. Restart the backend.
9. Repeat a grounded query and reopen each learning view.

Expected:

- No ingestion, chat, citation, graph, learning artifact, settings, or analytics regression.
- Previously persisted embedding/LLM cache rows survive restart until expiry or invalidation.
- UI view switches are faster after the first load.
- New content is visible after indexing and graph updates.

## QA-17: Verify cascading note-folder deletion

This check validates both the user-visible behavior and the foreign-key correction required by CI.

1. Create a temporary workspace and a folder named `Temporary QA`.
2. Upload or select transcribed media that can generate a note with at least one generated section.
3. Generate the note, move it into `Temporary QA`, and confirm the folder shows one note.
4. Rename the folder to `Temporary QA Renamed` and confirm the note remains in it.
5. Delete the folder and accept the normal confirmation prompt, if shown.
6. Refresh the Notes view and try to open the deleted note from any recent-history path.
7. Confirm the backend log contains no `FOREIGN KEY constraint failed` error.

Expected:

- Folder deletion succeeds rather than returning a server error.
- The folder, its note, and every generated section belonging to that note are gone.
- Other folders and notes are unchanged.
- The database remains referentially valid.

For a deterministic backend validation, run:

```powershell
cd E:\repos\athenus\backend
venv\Scripts\python.exe -m pytest -q tests\test_note_foreign_keys.py tests\test_note_endpoints.py::test_deleting_a_folder_cascades_to_notes_and_generated_sections
```

Expected: `2 passed`.

## Manual QA Sign-off

| Check | Result | Notes |
| --- | --- | --- |
| QA-1 SQLite table and PRAGMAs | ☐ Pass / ☐ Fail | |
| QA-2 Embedding persistence and speedup | ☐ Pass / ☐ Fail | |
| QA-3 Deterministic LLM caching | ☐ Pass / ☐ Fail | |
| QA-4 Repeated RAG retrieval | ☐ Pass / ☐ Fail | |
| QA-5 RAG invalidation after indexing | ☐ Pass / ☐ Fail | |
| QA-6 Knowledge graph cache/invalidation | ☐ Pass / ☐ Fail | |
| QA-7 Concept merge vectorization | ☐ Pass / ☐ Fail | |
| QA-8 Progress lifecycle | ☐ Pass / ☐ Fail | |
| QA-9 Settings cache | ☐ Pass / ☐ Fail | |
| QA-10 Frontend query cache/deduplication | ☐ Pass / ☐ Fail | |
| QA-11 Media ETag/304 behavior | ☐ Pass / ☐ Fail | |
| QA-12 Ollama keep-alive | ☐ Pass / ☐ Fail | |
| QA-13 Anthropic prompt cache | ☐ Pass / ☐ Fail | |
| QA-14 Workspace deletion invalidation | ☐ Pass / ☐ Fail | |
| QA-15 Factory reset cleanup | ☐ Pass / ☐ Fail | |
| QA-16 End-to-end regression smoke test | ☐ Pass / ☐ Fail | |
| QA-17 Cascading note-folder deletion | ☐ Pass / ☐ Fail | |

Validated by: ____________________

Date: ____________________

Overall result: ☐ Accepted / ☐ Rejected / ☐ Accepted with follow-up issues

---

# Transcript Reliability Remediation — Phase 1 Manual QA

## QA-18 Fresh Transcript Retrieval After Ingestion

Purpose: verify that a transcript which is empty while a video is processing is fetched again and displayed as soon as ingestion completes.

### Step-by-step validation

1. Start the backend and frontend using the normal local development workflow.
   - Expected: the dashboard opens without frontend or backend startup errors.
2. Open the default workspace, go to **Uploads**, and select a short MP4 containing clearly audible speech.
   - Expected: the upload is accepted and the ingestion job begins at the queued/uploaded stage.
3. Open the uploaded video in the Video Workspace before transcription completes.
   - Expected: the video is selectable; a temporary loading or no-transcript state is acceptable while processing continues.
4. Keep the Video Workspace open until the ingestion job reaches **Completed / 100%**.
   - Expected: the transcript panel refreshes automatically without a page reload, tab switch, or media reselection.
5. Confirm that at least one transcript row contains text from the uploaded video.
   - Expected: timestamped transcript rows replace the empty-state message.
6. Click a transcript timestamp.
   - Expected: playback seeks to that segment, the clicked segment becomes active, and transcript highlighting follows playback.
7. Reload the page and reopen the same completed video.
   - Expected: the persisted transcript renders immediately and contains the same segment text.

### Automated validation

Run `cd frontend; npm.cmd test -- --run src/services/apiClient.test.ts`.

Expected: one test passes, demonstrating that an empty processing response is followed by a fresh completed response.

QA-18 result: ☐ Pass / ☐ Fail

---

# Transcript Reliability Remediation — Phase 2 Manual QA

## QA-19 Explicit Transcript Cache Ownership

Purpose: verify that transcript caching is isolated by media and workspace, and that unrelated mutations do not invalidate or overwrite transcript state.

### Step-by-step validation

1. Start the application and open a completed video in workspace A.
   - Expected: its transcript renders and remains associated with that video.
2. Navigate to Notes, create or edit a note, then return to the same video.
   - Expected: the transcript is still present; the unrelated note mutation does not clear or replace it.
3. Select a second completed video in workspace A.
   - Expected: the second video's transcript is shown, with no rows from the first video.
4. Switch to workspace B and select a video there.
   - Expected: transcript state is isolated to workspace B even if media identifiers or titles are similar.
5. Upload a new short video and keep its Video Workspace open through completion.
   - Expected: only the completed video's transcript query refreshes, and its timestamped rows appear automatically.
6. Return to the earlier completed videos.
   - Expected: each video still shows its own persisted transcript without cross-workspace contamination.

### Automated validation

Run `cd frontend; npm.cmd test -- --run src/features/video/transcriptQueries.test.ts src/services/apiClient.test.ts`.

Expected: four tests pass, covering cache-neutral HTTP transport, workspace/media query-key isolation, and exact transcript refresh.

QA-19 result: ☐ Pass / ☐ Fail

---

# Transcript Reliability Remediation — Phase 3 Manual QA

## QA-20 Provider-independent Note Audio Transcription

Purpose: verify that note recordings use the process-wide speech-to-text capability selected by the AI routing configuration rather than constructing a private Whisper adapter.

### Step-by-step validation

1. Start the backend and confirm a speech-to-text provider/model is configured in Settings.
   - Expected: the configured STT provider is available without any note-specific provider setup.
2. Open Notes and create a manual note in the active workspace.
   - Expected: the note is created and remains selected.
3. Start note audio recording, speak a short distinctive sentence, and stop the recording.
   - Expected: the UI enters the transcribing state and the backend routes the audio through the configured STT capability.
4. Wait for transcription to finish.
   - Expected: timestamped segments containing the spoken sentence appear in the note Transcript view.
5. Switch to Notes view and back to Transcript view.
   - Expected: the same persisted segments are returned; the recording is attached only to the active note and does not appear as a library video.
6. Upload a short video and allow its transcription to complete.
   - Expected: video and note transcription both succeed under the same configured STT provider, while remaining separately persisted.
7. Temporarily configure an unavailable STT model/provider and retry a disposable note recording.
   - Expected: the request reports a clear transcription failure; it does not silently instantiate a different provider or attach an empty transcript.
8. Restore the working STT configuration.
   - Expected: subsequent note recording succeeds again without restarting or changing note-specific settings.

### Automated validation

Run `cd backend; python -m pytest tests/test_note_endpoints.py::test_note_audio_transcription_uses_injected_stt_capability -q`.

Expected: one test passes and the endpoint returns the transcript supplied by the injected STT capability without constructing Faster Whisper directly.

QA-20 result: ☐ Pass / ☐ Fail

---

# Transcript Reliability Remediation — Phase 4 Manual QA

## QA-21 Note Persistence Boundary

Purpose: verify that moving note persistence behind the repository interface preserves SQLite-backed folder, note, section, media, and transcript behavior.

### Step-by-step validation

1. Start the application, open a workspace, and create a folder named `Repository QA` in Notes.
   - Expected: the folder appears immediately with a note count of zero.
2. Create a manual note inside that folder, enter a distinctive title and body, then reload the application.
   - Expected: the folder and note survive the reload, and the title/body are unchanged.
3. Rename the note, edit its body, move it to Unorganized, and reload again.
   - Expected: all edits persist and the folder count returns to zero.
4. Move the note back to `Repository QA`, attach an existing audio/video media item from the same workspace, and generate note content.
   - Expected: the attachment succeeds, generated sections are persisted in timestamp order, and reopening the note returns the same sections.
5. Attempt to attach media belonging to a different workspace.
   - Expected: the operation is rejected with `Audio media not found in note workspace`, and the note keeps its prior media association.
6. Delete the generated note.
   - Expected: the note and its sections disappear, while the source media and transcript remain available.
7. Create two disposable notes in `Repository QA`, then delete the folder.
   - Expected: the folder and its two notes are removed together; unrelated folders, notes, media, and transcript chunks remain intact.
8. Restart the backend and revisit Notes and the source video's Transcript tab.
   - Expected: all non-deleted note data and the source transcript remain persisted and readable.

### Automated validation

Run `cd backend; python -m pytest tests/test_note_generation.py tests/test_note_endpoints.py tests/test_note_foreign_keys.py tests/test_note_repository_contract.py -q`.

Expected: 24 tests pass, covering both the pure repository contract and the production SQLite adapter through note generation and API behavior.

QA-21 result: ☐ Pass / ☐ Fail

---

# Transcript Reliability Remediation — Phase 5 Manual QA

## QA-22 Injected Cache Boundaries

Purpose: verify that domain services use injected cache ports while production composition retains cache reuse and workspace-scoped invalidation.

### Step-by-step validation

1. Start the application, open a workspace with a completed transcript, and open its Knowledge Graph twice.
   - Expected: both requests return the same nodes and relations; the second request may use the shared application cache without changing the response.
2. Add or reprocess media so that graph concepts are created or merged, then reopen the graph.
   - Expected: newly persisted concepts appear; stale graph cache entries do not hide the mutation.
3. Open Settings, change the active text or speech-to-text model, save, and reload Settings.
   - Expected: the saved selection is returned consistently through the injected settings cache.
4. Upload a short video, allow transcription to complete, and verify its transcript renders.
   - Expected: transcript ingestion and retrieval remain unaffected by the cache dependency refactor.
5. Create a disposable workspace, populate it with media, run one graph/search or AI operation, then delete that workspace.
   - Expected: the workspace is deleted and its `kg`, `rag`, and `llm` cache namespaces are invalidated through the injected cache ports.
6. Return to an unrelated workspace and reopen its transcript and Knowledge Graph.
   - Expected: unrelated cached data remains available and correct; deletion did not perform a global cache clear.
7. Restart the backend and reopen Settings plus the unrelated workspace.
   - Expected: persistent settings and workspace data load normally, demonstrating that no domain service depends on a concrete in-memory cache implementation.

### Automated validation

Run `cd backend; python -m pytest tests/test_domain_cache_boundaries.py tests/test_caching.py tests/test_knowledge_graph.py tests/test_settings_persistence.py tests/test_sqlite_repository.py -q`.

Expected: 26 tests pass, including an architecture guard against concrete cache imports and workspace-prefix invalidation through injected cache ports.

QA-22 result: ☐ Pass / ☐ Fail

---

# Transcript Reliability Remediation — Phase 6 Manual QA

## QA-23 Typed Transcript Contract and End-to-End Regression Coverage

Purpose: verify the typed transcript/note boundaries and the complete visible path from video ingestion through persisted rows, API response, rendering, highlighting, and seeking.

### Step-by-step validation

1. Start the application and upload a short video containing two clearly separated spoken phrases.
   - Expected: the media progresses through audio extraction and transcription without a provider or type-contract error.
2. Keep the Video Workspace open until processing completes.
   - Expected: the transcript refreshes automatically and displays at least two non-empty timestamped rows.
3. Compare the visible phrases with `GET /api/v1/media/{media_id}/transcript?workspace_id={workspace_id}`.
   - Expected: `full_text` is non-empty and every visible row corresponds to an ordered API segment with numeric `start_time` and `end_time` values.
4. Click the timestamp for the second phrase.
   - Expected: playback seeks to that segment's start and the second row becomes active.
5. Let playback cross from the first segment into the second.
   - Expected: highlighting moves at the exact segment boundary and remains on the final row after the final timestamp.
6. If a video longer than one hour is available, seek using a timestamp at or beyond `01:00:00`.
   - Expected: the timestamp is parsed as hours, minutes, and seconds and playback seeks to the correct position.
7. Reload the page and select the same completed video again.
   - Expected: persisted transcript rows render with the same ordering, speaker fallback, timestamps, and text.
8. Create and patch a manual note, including moving it into and out of a folder.
   - Expected: only supported typed patch fields are applied and note persistence remains unchanged.

### Automated validation

Run `cd backend; python -m pytest tests/test_ingestion_pipeline.py tests/test_video_ingestion_queue_regression.py tests/test_note_repository_contract.py tests/test_note_endpoints.py tests/test_caching.py tests/test_domain_cache_boundaries.py -q`.

Expected: 26 backend tests pass, including non-empty transcript persistence and API retrieval plus architecture boundary guards.

Run `cd frontend; npm.cmd test -- --run src/features/video/transcriptSegments.test.ts src/features/video/transcriptQueries.test.ts src/services/apiClient.test.ts`.

Expected: seven frontend tests pass, covering transcript refresh, query isolation, render-row mapping, active-row selection, and timestamp parsing.

Run `frontend\node_modules\.bin\tsc.cmd --noEmit --incremental false -p frontend\tsconfig.json` from the repository root.

Expected: TypeScript exits successfully with no diagnostics.

QA-23 result: ☐ Pass / ☐ Fail
