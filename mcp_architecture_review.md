# Athenus MCP Implementation Plan — Architectural Review

**Reviewer**: Antigravity  
**Date**: 2026-08-12  
**Document Under Review**: [implementation_plan.md](file:///e:/repos/athenus/implementation_plan.md)  
**ADR**: [0024-mcp-exposure-layer-and-retrieval-shaped-search.md](file:///e:/repos/athenus/docs/adr/0024-mcp-exposure-layer-and-retrieval-shaped-search.md)

---

## 1. Executive Verdict

### APPROVE WITH CHANGES

The plan is **architecturally sound** and closely aligned with both the existing Athenus codebase and the decisions documented in ADR 0024. The layering is correct, the separation between retrieval and synthesis is well-conceived, and the thin-MCP-over-application-services principle is consistently honored. The v1 catalogue is deliberately scoped and read-heavy, which is appropriate.

However, there are **five issues that must be resolved** before implementation begins:

1. **`TranscriptSegmentTable` has no `workspace_id` column** — this is the table used for fine-grained transcript segment reads. The plan's `MediaQueryService` cannot enforce workspace ownership at the segment level via a simple join; it must route through `MediaItemTable` for ownership validation. The plan does not acknowledge this gap.

2. **`WorkspaceService` is a module-level singleton** using `__new__` and `_initialized`. The plan proposes constructing it inside `bootstrap/mcp.py`, but the codebase already instantiates it at import time in multiple presentation modules. The composition root must account for this singleton pattern or the result is a stale/duplicate instance.

3. **`KnowledgeGraphService` is also a stateless singleton** instantiated at module level in [graph.py](file:///e:/repos/athenus/backend/app/presentation/api/v1/graph.py#L11). The plan's `search_concepts` tool backs onto `KnowledgeGraphService` but the existing concept search in `graph.py` uses `ConceptMergingService.list_concepts()` + hybrid keyword/embedding scoring — an entirely different code path. The plan must clarify which path `search_concepts` uses and whether it reuses the existing search logic.

4. **The retriever directly imports `engine` from `session.py`** — a module-level global. The proposed `search()` method on `MultiStageRetriever` inherits this coupling. For the MCP composition root to use a separate test-DB or session, this import-time binding is a problem. The plan acknowledges temp-SQLite testing but doesn't address this concrete obstacle.

5. **`list_workspace_media` is called in `media.py` but does not exist** on `MediaRepository` or `SqliteMediaRepository`. This is a pre-existing bug. The plan proposes modifying this API call site (Phase 2), so it should acknowledge and fix this during the migration.

None of these are architectural rejections — the plan's direction is correct. But each creates either a correctness issue or an unacknowledged implementation obstacle.

---

## 2. Critical Findings

### FINDING 1 — `TranscriptSegmentTable` lacks `workspace_id`

| Attribute | Detail |
|-----------|--------|
| **Severity** | HIGH |
| **Location** | Plan §2 (catalogue), §4 (MediaQueryService), Phase 2 |
| **Evidence** | [models.py:58-64](file:///e:/repos/athenus/backend/app/infrastructure/db/models.py#L58-L64) — `TranscriptSegmentTable` has `id`, `media_id`, `start_time`, `end_time`, `text`. No `workspace_id`. |
| **Why it matters** | The plan states `MediaQueryService` will verify `media.workspace_id == workspace_id` before returning content. For transcript *segments*, this requires a join through `MediaItemTable` since the segment table itself carries no workspace. This is achievable but the plan doesn't acknowledge it, creating a risk that implementation assumes a direct workspace filter on the segment table. |
| **Correction** | Plan should document that workspace ownership for segments is validated via `MediaItemTable` lookup (which *does* carry `workspace_id`). The service should first confirm `media_id ∈ workspace`, then query segments by `media_id`. `TranscriptChunkTable` *does* have `workspace_id` (line 50), so document/chunk reads are fine. |

---

### FINDING 2 — `WorkspaceService` singleton pattern

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Location** | Plan §4 (`bootstrap/mcp.py`), Phase 4 |
| **Evidence** | [workspace_service.py:22-33](file:///e:/repos/athenus/backend/app/domain/workspace/workspace_service.py#L22-L33) — `__new__` singleton with `_initialized` guard. Already instantiated in [media.py:20](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py#L20) and [workspaces.py:8](file:///e:/repos/athenus/backend/app/presentation/api/v1/workspaces.py#L8). |
| **Why it matters** | `bootstrap/mcp.py` calling `WorkspaceService()` won't create a fresh instance — it returns the existing singleton. This is *actually fine* for production but potentially confusing for test isolation (you can't inject a mock). The plan should explicitly state it reuses the singleton and document how tests will handle this. |
| **Correction** | Acknowledge that `WorkspaceService()` in the composition root returns the existing singleton. For tests, either test against the real service with temp DB, or introduce an optional constructor param/factory for test injection. |

---

### FINDING 3 — `search_concepts` tool backing service ambiguity

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Location** | Plan §2, tool `search_concepts`, backing service listed as `KnowledgeGraphService` |
| **Evidence** | The existing concept search at [graph.py:156-214](file:///e:/repos/athenus/backend/app/presentation/api/v1/graph.py#L156-L214) uses `ConceptMergingService.list_concepts()` for retrieval, then hybrid keyword + semantic embedding scoring — *not* `KnowledgeGraphService`. `KnowledgeGraphService.get_concepts()` exists but performs no search scoring. |
| **Why it matters** | The plan says `search_concepts` is backed by `KnowledgeGraphService (existing hybrid concept search)`. The existing hybrid concept search lives in the *graph API handler*, not in `KnowledgeGraphService` itself. The scoring logic (keyword substring + cosine similarity) is inlined in the route handler, not in a reusable service method. |
| **Correction** | Either: (a) extract the hybrid concept search logic from `graph.py` into `KnowledgeGraphService.search_concepts()` so both the REST endpoint and MCP tool share it, or (b) create a small `ConceptSearchService` at the application layer. The plan must be explicit about this rather than claiming the method already exists. |

---

### FINDING 4 — Module-level `engine` import coupling in retriever

| Attribute | Detail |
|-----------|--------|
| **Severity** | MEDIUM |
| **Location** | Plan Phase 1 (`MultiStageRetriever.search()`), test plan |
| **Evidence** | [multi_stage_retriever.py:9](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py#L9) — `from app.infrastructure.db.session import engine`. Also [bm25_retriever.py:62](file:///e:/repos/athenus/backend/app/domain/knowledge/bm25_retriever.py#L62) — `search_fts5` imports `engine` at call time. |
| **Why it matters** | The `_extract_timestamp_context` and `_extract_document_page_context` methods in the retriever use `Session(engine)` directly. The proposed `search()` method reuses hybrid retrieval stages including FTS5, which also imports engine. Testing with a temp SQLite requires either monkeypatching `session.engine` or refactoring the retriever to accept a session factory. The plan says "temp SQLite engine/session" fixture but doesn't address this module-level binding. |
| **Correction** | Plan should document that test fixtures must monkeypatch `app.infrastructure.db.session.engine` to point to the temp engine. This is the pragmatic approach for v1. Long-term, session injection would be cleaner but is out of scope. |

---

### FINDING 5 — `list_workspace_media` does not exist

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Location** | Plan §4 (Phase 2), modifying `media.py` |
| **Evidence** | [media.py:162](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py#L162) calls `media_repository.list_workspace_media(workspace_id)` but this method doesn't exist on `MediaRepository` or `SqliteMediaRepository`. The interface has `list_by_workspace`. |
| **Why it matters** | Pre-existing bug. The plan proposes modifying this file in Phase 2. This should be fixed as part of the migration. |
| **Correction** | Fix `list_workspace_media` → `list_by_workspace` during Phase 2 changes. |

---

### FINDING 6 — `source_type == "pdf"` hardcoded in retriever

| Attribute | Detail |
|-----------|--------|
| **Severity** | LOW |
| **Location** | Plan §2 (source taxonomy), retriever |
| **Evidence** | [multi_stage_retriever.py:88](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py#L88) — `if source_type == "pdf" or document_id:`. Also [workspace_intelligence.py:87](file:///e:/repos/athenus/backend/app/application/services/workspace_intelligence.py#L87), [multi_stage_retriever.py:354](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py#L354). |
| **Why it matters** | The plan mandates normalizing `pdf` → `document` at the MCP boundary. The retriever internally uses `"pdf"` as a sentinel. `WorkspaceSearchService` must translate `"document"` to `"pdf"` when calling the retriever, or the retriever internals should be updated. |
| **Correction** | Plan should document the normalization boundary: `WorkspaceSearchService` maps MCP `"document"` → internal `"pdf"` when delegating to the retriever. Fixing the internal sentinel is desirable but optional for v1. |

---

## 3. Architecture Verification

| Planned Component | Exists? | Correct Location? | Reuse Existing? | Issues |
|---|---|---|---|---|
| `bootstrap/mcp.py` | No (new) | ✅ `bootstrap/` already exists with `event_subscribers.py` | Pattern matches existing `bootstrap/` convention | None |
| `WorkspaceSearchService` | No (new) | ✅ `application/services/` is correct | New service; delegates to existing retriever | None |
| `MediaQueryService` | No (new) | ✅ `application/services/` is correct | New service; wraps `MediaRepository` | Must handle `TranscriptSegmentTable` lacking `workspace_id` |
| `MultiStageRetriever` | ✅ Exists | ✅ `infrastructure/retrieval/` | Existing `execute_retrieval()` stays untouched; `search()` added | Module-level `engine` coupling for tests |
| `MediaRepository` (interface) | ✅ Exists | ✅ `application/repositories/` | Interface extended with scoped reads | Current `get_transcript` takes only `media_id`, no workspace scoping |
| `SqliteMediaRepository` | ✅ Exists | ✅ `application/repositories/` | Implementation extended | `list_workspace_media` call site has pre-existing bug |
| `WorkspaceService` | ✅ Exists | Domain layer (`domain/workspace/`) | Reused as singleton | Singleton pattern noted |
| `KnowledgeGraphService` | ✅ Exists | Domain layer (`domain/knowledge/`) | Reused | `search_concepts` hybrid search does NOT exist on this service — it's in `graph.py` handler |
| `FastMCP server` | No (new) | ✅ `presentation/mcp/` is correct layer | N/A | FastMCP not yet installed |
| `MCPToolAdapter` | ❌ Does not exist | N/A | Plan correctly defers this | The plan and ADR reference it as future — no code exists |
| `presentation/mcp/registry.py` | No (new) | ✅ Correct | N/A | None |
| `presentation/mcp/tools/` | No (new) | ✅ Correct | N/A | None |
| `presentation/mcp/resources.py` | No (new) | ✅ Correct | N/A | None |
| Existing tests (111) | ✅ Exist | ✅ `backend/tests/` (51 files) | Must remain passing | Plan acknowledges full-suite run |

---

## 4. Retrieval Review

### Current Retrieval Pipeline (`execute_retrieval`)

VERIFIED FROM CODE — [multi_stage_retriever.py](file:///e:/repos/athenus/backend/app/infrastructure/retrieval/multi_stage_retriever.py):

```
Stage 0: Conversational query guard (is_conversational_query)
Stage 1: Query rewrite (static expansion)
Stage 2-3: Active context extraction (timestamp window / document page window)
Stage 4: Knowledge graph triple retrieval
Stage 5a: Dense Qdrant vector search (workspace-filtered, limit=10)
Stage 5b: Sparse FTS5 BM25 search (workspace-filtered)
Stage 5c: RRF fusion (k=60, cap=15)
Stage 6: Cross-encoder reranking (top_k=3)
Stage 7-8: Token budget enforcement + prompt assembly
```

### Proposed `search()` Separation

The plan proposes `search()` runs Stages 1, 5a, 5b, 5c, 6 and returns candidates. It skips:
- Stage 0 (conversational guard)
- Stages 2-3 (active context — UI-oriented)
- Stage 4 (KG triples — mixed into prompt context)
- Stages 7-8 (prompt assembly / token compression)

**Assessment: This is the correct decomposition.**

The stages to include in `search()` are genuinely retrieval-shaped — they produce ranked candidates with provenance. The stages to exclude are synthesis-oriented — they produce a prompt.

### What Can Be Reused

| Component | Reusable? | Notes |
|---|---|---|
| Query rewrite (Stage 1) | ✅ Yes | Currently trivial: appends static string. Can be shared. |
| Dense Qdrant search | ✅ Yes | `vector_store.search()` already accepts `filter_workspace_id`, `filter_source_type` |
| FTS5 BM25 search | ✅ Yes | `bm25.search_fts5()` already workspace-scoped |
| RRF fusion logic | ⚠️ Copy or extract | Currently inline in `execute_retrieval`. Should be extracted into a helper method. |
| Cross-encoder reranker | ✅ Yes | `self.reranker.rerank()` is standalone |
| Embedding capability | ✅ Yes | `ai_service_bus.get_embedding_capability()` |

### What Must Be Refactored

1. **RRF fusion** — currently ~20 lines inline in `execute_retrieval`. Should be extracted to `_fuse_rrf(dense_docs, sparse_docs, k=60, cap=15)` so both `execute_retrieval` and `search()` call it.
2. **Score normalization** — the plan says "normalized relative `relevance`". Currently: RRF scores are unnormalized floats (sum of `1/(60+rank)`). Reranker scores are heuristic composites. The plan needs to define what "normalized" means — min-max over the result set? Raw rerank score? This affects the public contract.

### Risk to `execute_retrieval`

**Low.** If `search()` is a new method that calls the same components but assembles differently, `execute_retrieval` is untouched. The plan explicitly states this. The RRF extraction is a safe refactor guarded by existing tests ([test_retrieval_rag.py](file:///e:/repos/athenus/backend/tests/test_retrieval_rag.py)).

### Verdict

The `MultiStageRetriever.search()` → `WorkspaceSearchService` abstraction is **correct and clean**. The separation between retrieval and synthesis is well-defined.

---

## 5. Workspace Isolation Review

### Mental Model

```
Workspace A (workspace_id = "ws_a")
 └── Media 123 (MediaItemTable: workspace_id="ws_a", id="med_123")
       └── Segments (TranscriptSegmentTable: media_id="med_123")
       └── Chunks (TranscriptChunkTable: workspace_id="ws_a", media_id="med_123")
 └── Concepts (KnowledgeConceptTable: workspace_id="ws_a")

Workspace B (workspace_id = "ws_b")
 └── Media 456 (MediaItemTable: workspace_id="ws_b", id="med_456")
```

### Validation Points — Access Path Analysis

| Access Path | Workspace Filter Location | Isolation Status |
|---|---|---|
| **Qdrant vector search** | `filter_workspace_id` param on `vector_store.search()` | ✅ ENFORCED — Qdrant filter condition |
| **FTS5 BM25 search** | `WHERE fts.workspace_id = :ws` | ✅ ENFORCED — SQL WHERE clause |
| **KG concept retrieval** | `WHERE workspace_id = workspace_id` | ✅ ENFORCED — SQL WHERE clause |
| **KG relation retrieval** | `WHERE workspace_id = workspace_id` | ✅ ENFORCED |
| **Media item lookup** | `MediaItemTable.workspace_id` checked by `MediaQueryService` | ⚠️ NOT YET ENFORCED — `MediaRepository.get(media_id)` has no workspace filter. `MediaQueryService` must add this check. |
| **Transcript segment read** | `TranscriptSegmentTable` has NO `workspace_id` | ⚠️ REQUIRES INDIRECT VALIDATION — must verify `media_id` belongs to workspace via `MediaItemTable` first |
| **Transcript chunk read** | `TranscriptChunkTable.workspace_id` exists | ✅ CAN BE ENFORCED directly |
| **Concept lookup by ID** | `KnowledgeConceptTable.workspace_id` exists | ⚠️ `get_concept(concept_id)` does NOT filter by workspace — returns any matching concept globally |
| **Resource URI resolution** | Workspace embedded in URI | Enforcement depends on handler implementation |

### Critical Isolation Gaps

> [!CAUTION]
> **Gap 1**: `KnowledgeGraphService.get_concept(concept_id)` performs a global lookup by primary key — no workspace filter. The MCP resource `athenus://workspace/{workspace_id}/graph/concept/{concept_id}` must validate `concept.workspace_id == requested_workspace_id` after retrieval. The plan's `MediaQueryService` handles media ownership but the concept resource handler must do its own workspace validation.

> [!CAUTION]
> **Gap 2**: `MediaRepository.get(media_id)` returns any media item regardless of workspace. This is by design (media IDs are globally unique) but the MCP layer must validate `item.workspace_id == workspace_id` for every media-scoped resource.

> [!IMPORTANT]
> **Gap 3**: `TranscriptSegmentTable` has no `workspace_id`. Segment queries (`get_transcript_segment` tool, `/transcript` resource) must validate workspace membership through the parent `MediaItemTable`.

### Concrete Attack Scenario

```
Agent requests: athenus://workspace/ws_a/media/med_456/transcript
med_456 belongs to ws_b
```

**Current code path** (without MCP changes): `SqliteMediaRepository.get_transcript("med_456")` returns all segments for med_456 regardless of workspace. The workspace in the URI is decorative.

**Required enforcement**: `MediaQueryService.get_transcript(workspace_id="ws_a", media_id="med_456")` must:
1. Call `MediaRepository.get("med_456")` → `MediaItem`
2. Check `item.workspace_id == "ws_a"` → FAIL → raise cross-workspace error
3. Only if check passes, query `TranscriptSegmentTable` by `media_id`

The plan describes this pattern but doesn't acknowledge that `TranscriptSegmentTable` is the one table where the join is unavoidable.

---

## 6. MCP Catalogue Review

### Tools

| Tool | Approve? | Concern | Recommendation |
|---|---|---|---|
| `list_workspaces` | ✅ Approve | `WorkspaceService.list_workspaces()` exists and works. `include_archived` param matches existing method signature. | None |
| `search_workspace` | ✅ Approve | Correctly backed by new `WorkspaceSearchService`. Source type filter and limit cap are appropriate. | Clarify that `source_type` must normalize `"document"` → `"pdf"` internally |
| `search_concepts` | ⚠️ Approve with changes | Backing service listed as `KnowledgeGraphService` but the existing hybrid search is in the `graph.py` handler, not the service | Must extract search logic into a service method or create a new one |
| `get_transcript_segment` | ✅ Approve | Clean capability. `start_seconds`/`end_seconds` windowing matches existing segment table schema. | Ensure workspace ownership validation via `MediaItemTable` join |

### Resources

| Resource URI | Approve? | Concern | Recommendation |
|---|---|---|---|
| `athenus://workspace/{workspace_id}` | ✅ Approve | Lightweight metadata + inventory. `WorkspaceService.get_workspace()` exists. | Consider capping media inventory size (e.g., exclude file paths) |
| `athenus://workspace/{workspace_id}/media/{media_id}` | ✅ Approve | Media metadata. `MediaRepository.get()` exists. | Must validate workspace ownership |
| `athenus://workspace/{workspace_id}/media/{media_id}/transcript` | ⚠️ Approve with caution | **Size concern**: a 2-hour lecture has thousands of segments. Full transcript as JSON could be very large. | Consider: (a) document the size risk, (b) plan for pagination in v2, (c) for v1, accept the full dump with a documented maximum |
| `athenus://workspace/{workspace_id}/media/{media_id}/document` | ⚠️ Approve with caution | Same size concern for large documents. Document pages/sections via `TranscriptChunkTable` (which overloads chunk table for documents). | Plan should acknowledge this uses `TranscriptChunkTable` filtered by `media_id` with `start_time`/`end_time` repurposed as page ranges |
| `athenus://workspace/{workspace_id}/graph/concept/{concept_id}` | ✅ Approve | `KnowledgeGraphService.get_concept()` exists. Includes aliases via `ConceptAliasTable`. | Must validate `concept.workspace_id == workspace_id` — the service's `get_concept` does global lookup |

### URI Scheme Assessment

The `athenus://` scheme is clean and hierarchical. Workspace-first nesting enforces the mental model that workspace is the authorization boundary. No issues with the scheme itself.

---

## 7. Dependency / Runtime Review

### Verified Environment

| Dependency | Installed Version | Required | Status |
|---|---|---|---|
| Python | 3.11.5 | ≥3.10 for FastMCP | ✅ Compatible |
| Pydantic | 2.13.4 | ≥2.0 for FastMCP | ✅ Compatible |
| pydantic-settings | 2.14.2 | — | ✅ |
| FastAPI | 0.141.1 (venv) | — | ✅ |
| sqlmodel | 0.0.39 (venv) | — | ✅ |
| qdrant-client | 1.18.0 (venv) | — | ✅ |
| uvicorn | 0.52.1 (venv) | — | ✅ |
| FastMCP | **NOT INSTALLED** | Required | ⚠️ Phase 0 dependency |
| `mcp` SDK | **NOT INSTALLED** | Transitive via FastMCP | ⚠️ Phase 0 dependency |

### FastMCP Compatibility

- **FastMCP ≥2.2** requires Python ≥3.10 — ✅ Python 3.11.5 is compatible.
- FastMCP 2.x uses Pydantic v2 for schema generation — ✅ Pydantic 2.13.4 is compatible.
- FastMCP supports both stdio and Streamable HTTP from the same server object — VERIFIED from FastMCP documentation, consistent with the plan.

### Windows stdio Concerns

> [!WARNING]
> **Event loop on Windows**: Python 3.11 on Windows defaults to `ProactorEventLoop`. The MCP SDK's stdio transport uses `asyncio.StreamReader`/`StreamWriter` which may require `SelectorEventLoop` on Windows. FastMCP 2.x handles this internally (sets `WindowsSelectorEventLoopPolicy` if needed), but this MUST be verified in the Phase 4 round-trip test as the plan states.

### Dependency Management

The project uses a flat `requirements.txt` (no `pyproject.toml`, no Poetry). Adding `fastmcp>=2.2,<3` is consistent with the existing pattern. The `mcp` SDK is a transitive dependency of FastMCP and should not be listed separately.

---

## 8. Testing Review

### Proposed Test Suite Assessment

| Test | Phase | Realistic? | Concerns |
|---|---|---|---|
| `test_mcp_workspace_search.py` | 1 | ✅ Yes | Needs monkeypatching of `engine` for temp SQLite. Qdrant can use in-memory via `path=":memory:"`. |
| `test_mcp_media_query.py` | 2 | ✅ Yes | Same engine monkeypatch concern. |
| `test_mcp_tools.py` | 3 | ✅ Yes | Can test via FastMCP's `call_tool()` method directly. |
| `test_mcp_isolation.py` | 5 | ✅ Yes, critical | Must cover both search paths AND resource reads. |
| `test_mcp_stdio_roundtrip.py` | 4 | ⚠️ Needs care | Spawning a subprocess on Windows with stdio pipes. Python's `subprocess.Popen` + asyncio can be finicky. The `mcp` SDK client should handle this, but Windows-specific flakiness is possible. |
| `test_mcp_catalogue_contract.py` | 5 | ✅ Yes | Golden JSON comparison is stable. Must normalize ordering. |

### Test Infrastructure Gaps

1. **Qdrant in tests**: The existing [test_workspace_isolation.py](file:///e:/repos/athenus/backend/tests/test_workspace_isolation.py) uses a persistent path `./data/test_qdrant_isolation`. For MCP tests, in-memory Qdrant (`:memory:`) is cleaner. The plan mentions "in-memory Qdrant adapter" in Phase 0 — this is correct and the adapter supports it ([qdrant_adapter.py:31-32](file:///e:/repos/athenus/backend/app/infrastructure/adapters/qdrant_adapter.py#L31-L32)).

2. **SQLite in tests**: Requires monkeypatching `app.infrastructure.db.session.engine`. The existing test suite seems to work against the real DB (no fixture isolation visible). New MCP tests should establish the pattern of temp DB + teardown.

3. **Embedding model in tests**: The retriever requires `ai_service_bus.get_embedding_capability()` which loads `sentence-transformers` (heavy). Tests should either mock this or accept the model load time. Existing tests ([test_workspace_isolation.py](file:///e:/repos/athenus/backend/tests/test_workspace_isolation.py)) load the real model — so the precedent is real model, not mock.

### Missing Test Coverage

| Gap | Priority | Rationale |
|---|---|---|
| Concept resource workspace validation | HIGH | `get_concept()` is a global lookup — test that cross-workspace concept access is refused |
| Large transcript resource | LOW | Verify that a multi-thousand-segment transcript doesn't OOM or timeout in MCP serialization |
| Source type normalization | MEDIUM | Test that `source_type="document"` in MCP maps correctly to internal `"pdf"` and returns expected results |
| `list_workspaces` with `include_archived=False` | LOW | Verify archived workspaces are excluded |

---

## 9. Scope Review

### Items Correctly In Scope

- 4 tools, 5 resources — right-sized for v1
- stdio transport only — correct
- Read-only resources — correct
- No destructive operations — correct
- Learning/quiz/analytics deferred — correct

### Items That Should Be Deferred

| Item | Currently In Plan | Recommendation |
|---|---|---|
| `http_entrypoint.py` (Phase 6) | Listed as "deferred" file in layout | ✅ Already deferred — but remove from §4 file layout to avoid confusion. It's listed as "NEW" in the layout but described as Phase 6. |
| Moving retriever's `_extract_timestamp_context` / `_extract_document_page_context` into `MediaQueryService` (Phase 2) | In scope | ⚠️ **SHOULD DEFER** to Phase 2.5 or later. The refactor has regression risk (acknowledged in §10) and is not strictly required for MCP v1. `MediaQueryService` can implement fresh workspace-scoped read methods without moving the retriever's private helpers. The retriever can continue to use its own helpers for `execute_retrieval`. |

### Items Missing From Scope

No missing items. The scope is deliberately minimal and correct.

---

## 10. Required Changes Before Implementation

### MUST CHANGE

1. **Document `TranscriptSegmentTable` workspace gap**: Explicitly state in Phase 2 that segment ownership validation requires `MediaItemTable` join because `TranscriptSegmentTable` has no `workspace_id` column. Specify the validation flow: look up media → check workspace → query segments.

2. **Resolve `search_concepts` backing service**: Change the plan to either (a) extract the hybrid concept search from `graph.py` into `KnowledgeGraphService.search_concepts()`, or (b) create a dedicated `ConceptSearchService` and back both the REST endpoint and MCP tool onto it.

3. **Document `engine` monkeypatch strategy for tests**: Phase 0 fixtures must monkeypatch `app.infrastructure.db.session.engine` and `app.infrastructure.db.session.init_db` to use a temp SQLite engine. This is the only practical approach given the module-level binding.

4. **Add concept resource workspace validation**: The plan must specify that the concept resource handler validates `concept.workspace_id == requested_workspace_id` after calling `KnowledgeGraphService.get_concept()`.

5. **Document `source_type` normalization boundary**: Specify that `WorkspaceSearchService` normalizes MCP's `"document"` to internal `"pdf"` when delegating to the retriever, and normalizes `"pdf"` back to `"document"` in search results.

### SHOULD CHANGE

6. **Defer the retriever helper move** (Phase 2 `_extract_timestamp_context` / `_extract_document_page_context` → `MediaQueryService`): Implement fresh methods in `MediaQueryService` for MCP reads without moving the retriever's private helpers. This eliminates the regression risk to `execute_retrieval` and the citation pipeline.

7. **Fix `list_workspace_media` bug**: Rename to `list_by_workspace` in [media.py:162](file:///e:/repos/athenus/backend/app/presentation/api/v1/media.py#L162) during Phase 2 modifications.

8. **Remove `http_entrypoint.py` from §4 file layout**: It's listed as "NEW" but is Phase 6 / deferred. Listing it in the file layout implies it's part of v1.

9. **Define "normalized relevance"**: Specify how `relevance` in `SearchHit` is calculated — raw rerank score, min-max normalized, or percentile. This affects the public contract stability.

10. **Address `WorkspaceService` singleton in composition root**: Add a note that `WorkspaceService()` returns the process singleton and is not independently constructable. For tests, explain how workspace test data is managed.

### OPTIONAL

11. **Add size warning for transcript/document resources**: Note that full transcripts and documents can be large. Consider adding a `max_segments` or `max_chunks` guard with a truncation indicator in the response envelope for v1 safety.

12. **Consider `concept_aliases` in concept resource**: The `ConceptAliasTable` exists and could enrich the concept resource response. The plan mentions "aliases" in the resource content but doesn't reference the table.

---

## 11. Final Recommendation

> **Would you approve this plan for implementation right now?**

**Not yet.** The plan is architecturally correct and well-structured, but the five MUST CHANGE items above represent real implementation obstacles or correctness gaps:

1. The `TranscriptSegmentTable` workspace gap could lead to a security bypass if implementers assume a direct workspace filter exists.
2. The `search_concepts` service ambiguity could lead to duplicated search logic.
3. Without the `engine` monkeypatch strategy documented, Phase 0 test setup will stall.
4. Without concept workspace validation, the concept resource could leak cross-workspace data.
5. Without source type normalization documented, the `"pdf"` → `"document"` mapping will be ad-hoc.

**After addressing these five items, the plan is ready for implementation.** The SHOULD CHANGE items would improve the plan but are not blockers.

The overall direction — thin MCP layer over existing application services, explicit workspace scoping, retrieval-shaped search separate from synthesis, structured JSON resources with provenance — is **architecturally sound and consistent with the Athenus codebase**.
