# Athenus MCP Exposure Layer — Implementation Plan

> **Status**: Design frozen (ADR 0024 approved, `docs/adr/0024-mcp-exposure-layer-and-retrieval-shaped-search.md`). This plan is for **review — no code has been written**. Implementation starts only after approval here.

---

## 1. Goal & v1 Success Criterion

Prove that an external AI agent can reliably **discover and retrieve Athenus knowledge** with explicit workspace scoping and authoritative provenance:

```
External MCP Client
  → Athenus MCP Server (stdio)
  → search_workspace(workspace_id, query)
  → WorkspaceSearchService
  → MultiStageRetriever.search()
  → Qdrant / FTS5 / KG
  → Provenance-rich result
  → External AI
```

and then:

```
External AI
  → athenus://workspace/{w}/media/{m}/transcript
  → Authoritative transcript (structured JSON + provenance)
  → Source-aware answer
```

If that works reliably, the core concept is proven. Learning/analytics resources, `ask_agent`, MCP *consumption* (ToolAdapter), and Cloud HTTP deployment all build on this foundation later.

---

## 2. v1 Catalogue

**Tools (4)** — thin registrations over application services:

| Tool | Args | Backing service |
|---|---|---|
| `list_workspaces` | `include_archived: bool = False` | `WorkspaceService` |
| `search_workspace` | `workspace_id`, `query`, `source_type? ∈ {video,audio,document}`, `limit? = 5 (≤10)` | `WorkspaceSearchService` |
| `search_concepts` | `workspace_id`, `query`, `limit? = 10 (≤20)` | `KnowledgeGraphService` (existing hybrid concept search) |
| `get_transcript_segment` | `workspace_id`, `media_id`, `start_seconds`, `end_seconds?` | `MediaQueryService` |

**Resources (5)** — read-only, `application/json`, provenance-preserving envelope `{ uri, metadata, content }`:

| URI template | Content |
|---|---|
| `athenus://workspace/{workspace_id}` | lightweight workspace metadata + inventory (media items, learning artifacts, concept count) — **not** the full workspace |
| `athenus://workspace/{workspace_id}/media/{media_id}` | media metadata + ingestion status + provenance |
| `athenus://workspace/{workspace_id}/media/{media_id}/transcript` | video/audio segments: `{segment_id, start_seconds, end_seconds, text}` + source identity |
| `athenus://workspace/{workspace_id}/media/{media_id}/document` | document pages/sections: `{page, section, text, chunk_id}` + location |
| `athenus://workspace/{workspace_id}/graph/concept/{concept_id}` | concept identity, definition, aliases, relationships, source references |

**Deferred from v1**: learning deck/quiz/analytics resources; `ask_agent`; Prompts; MCP consumption; Streamable HTTP.

---

## 3. Architecture

```
                MCP Client
                    │
             stdio (v1)   Streamable HTTP (later, same catalogue)
                    │
                    ▼
   MCP Server: FastMCP (on official mcp SDK)
   ┌─────────────────────────────┐
   │ presentation/mcp/            │  ← thin: validate → inject service → call → transform
   │  registry.py  resources.py  │
   │  tools/ workspace, search,   │
   │       media, graph           │
   └──────────────┬──────────────┘
                  │
                  ▼
        bootstrap/mcp.py  (composition root shared by stdio + http entrypoints)
                  │
                  ▼
   ┌─────────────┬──────────────┬──────────────┐
   │ WorkspaceSearchService │ MediaQueryService │ KnowledgeGraphService / WorkspaceService │
   └──────┬──────────────────┴──────┬─────────┘
          ▼                         ▼
   MultiStageRetriever.search()   MediaRepository ── SQLite
          │  (retrieval-shaped)    │
      Qdrant / FTS5 / KG          (workspace-ownership validation)
```

Rules (mandatory):
- MCP layer never re-implements retrieval, media access, graph, or learning logic.
- MCP never calls Athenus' own HTTP endpoints.
- Same application object can be used by REST, MCP, Tauri, and future internal agents.

---

## 4. Target File Layout

```
backend/app/
├── bootstrap/mcp.py                          NEW — composition root (build_mcp_server())
├── application/services/
│   ├── workspace_search_service.py           NEW — WorkspaceSearchService + SearchHit DTO
│   └── media_query_service.py                NEW — MediaQueryService (reads + ownership)
├── application/repositories/
│   ├── media_repository.py                   MOD — interface: workspace-scoped read methods
│   └── sqlite_media_repository.py            MOD — implement range/page reads
├── infrastructure/retrieval/
│   └── multi_stage_retriever.py              MOD — add retrieval-shaped search(); delegate active-context reads to MediaQueryService
├── presentation/
│   ├── mcp/
│   │   ├── __init__.py                       NEW
│   │   ├── registry.py                       NEW — FastMCP server, registers tools
│   │   ├── resources.py                      NEW — registers 5 resource templates
│   │   ├── tools/
│   │   │   ├── __init__.py                   NEW
│   │   │   ├── workspace.py                  NEW — list_workspaces
│   │   │   ├── search.py                     NEW — search_workspace
│   │   │   ├── media.py                      NEW — get_transcript_segment
│   │   │   └── graph.py                      NEW — search_concepts
│   │   ├── stdio_entrypoint.py               NEW — python -m app.presentation.mcp.stdio_entrypoint
│   │   └── http_entrypoint.py                NEW — (Phase 6, deferred)
│   └── api/v1/media.py                       MOD — migrate get_transcript call to workspace-scoped repository method
backend/tests/
│   ├── test_mcp_workspace_search.py          NEW
│   ├── test_mcp_media_query.py               NEW
│   ├── test_mcp_tools.py                     NEW
│   ├── test_mcp_isolation.py                 NEW
│   ├── test_mcp_stdio_roundtrip.py           NEW
│   ├── test_mcp_catalogue_contract.py        NEW
│   └── fixtures/mcp_catalogue_contract.json  NEW — golden contract snapshot
backend/requirements.txt                      MOD — add fastmcp (+ official mcp SDK)
scripts/mcp_demo.py                           NEW — QA demo client (official mcp SDK)
```

---

## 5. Dependency Changes

`backend/requirements.txt`:

```text
fastmcp>=2.2,<3             # brings the official `mcp` SDK transitively; pin exact on install
```

- No new runtime infra (SQLite + in-memory Qdrant already in place).
- No new test-only dependencies (`pytest` + `pytest-asyncio` present today).

---

## 6. Phased Plan

### Phase 0 — Dependencies & test scaffolding
- Add `fastmcp` to `requirements.txt`.
- Create `presentation/mcp/` package skeleton + `bootstrap/mcp.py` stub.
- Add shared pytest fixtures: temp SQLite engine/session, in-memory Qdrant adapter, `MediaRepository` fake, seeded workspace + media factories. Reuse existing test conventions (see `test_workspace_isolation.py`, `test_retrieval_rag.py`).
- **Tests**: a trivial "fixtures importable" smoke test.

### Phase 1 — Retrieval-shaped search
- `MultiStageRetriever.search(query, workspace_id, media_id=None, document_id=None, source_type=None, top_k=5)`:
  - runs the information-gathering stages: query rewrite → hybrid dense+FTS5+RRF → rerank to `top_k`.
  - returns candidates with provenance + a **normalized relative `relevance`**; **no** prompt assembly, **no** token compression for generation, **no** conversational guard.
  - existing `execute_retrieval()` unchanged.
- `WorkspaceSearchService.search(query, workspace_id, source_type=None, limit=5) -> WorkspaceSearchResult`:
  - canonical `SearchHit` DTO: `workspace_id`, `source_id`, `source_type`, `chunk_id`, `title`, `text`, `location` (video/audio `{start_seconds,end_seconds}` · document `{page,section}`), `relevance`.
  - validates workspace existence; honors `source_type` filter + `limit` cap.
- **Tests** (`test_mcp_workspace_search.py`): retriever.search returns ≥ requested top_k, includes provenance, skips guard; service: hit shape, empty result → `[]`, source-type filter, limit cap, unknown workspace → typed error.

### Phase 2 — MediaQueryService + ownership
- Extend `MediaRepository` interface with workspace-scoped read methods (e.g. `get_transcript(workspace_id, media_id)`, `list_segments_in_range(workspace_id, media_id, start, end)`, `list_chunks_for_page(workspace_id, media_id, page)`); implement in `SqliteMediaRepository` + in-memory fake. Migrate the `media.py` REST call site.
- Move the retriever's private `_extract_timestamp_context` / `_extract_document_page_context` query logic into `MediaQueryService` (canonical owner); retriever delegates (behavior preserved — existing retrieval/citation tests guard this).
- `MediaQueryService`: `get`, `get_transcript`, `get_segment`, `get_document_content` — **every method verifies `media.workspace_id == workspace_id` before returning content**.
- **Tests** (`test_mcp_media_query.py` + isolation cases): segment window boundary, page coverage, empty range, **cross-workspace read → error** (media exists in B, requested under A → refusal, no content leak).

### Phase 3 — MCP registry, tools, resources, error semantics
- `registry.py`: build FastMCP server; register the 4 tools (thin; inject services via bootstrap).
- `resources.py`: register the 5 resource templates → `application/json` envelope `{uri, metadata, content}`; each handler enforces workspace ownership.
- **Error semantics (Q17)** — typed errors throughout:
  - unknown workspace → explicit error; cross-workspace access → explicit error (no leak); in-scope missing → not-found error; legitimate zero-result search → `[]`.
- **Tests** (`test_mcp_tools.py`): each tool via direct registry call — correct results, provenance present, error matrix, limits.

### Phase 4 — stdio transport + round-trip
- `bootstrap/mcp.py`: `build_mcp_server()` — `init_db()`, construct repositories/services, build registry.
- `stdio_entrypoint.py`: `if __name__ == "__main__": mcp.run()` (stdio). Adjust import path so `python -m app.presentation.mcp.stdio_entrypoint` works from `backend/`.
- **Tests** (`test_mcp_stdio_roundtrip.py`): official `mcp` ClientSession over stdio → `tools/list` (4 tools), `resources/list` (5 templates), real `search_workspace`, transcript resource read; assert provenance-shaped results; verify Windows stdio event-loop path.

### Phase 5 — Catalogue contract + isolation hardening + close-out
- `test_mcp_catalogue_contract.py`: render normalized contract (tool names, param names, required/optional, resource URI templates, envelope keys) → compare to `fixtures/mcp_catalogue_contract.json`. Regenerate via an explicit flag/script. Intentional-failure on any public-interface change.
- `test_mcp_isolation.py`: full matrix — search under B never returns A content; `athenus://workspace/A/media/{from_B}/transcript` refuses; owned-by-requested-workspace resource succeeds.
- Final: run full `backend/tests/` (expect existing 111 + new to pass), update `README`/`AGENTS.md` if needed, close out.

### Phase 6 — Deferred: Streamable HTTP transport + auth
- `http_entrypoint.py` + HTTP serve over the **same** `build_mcp_server()`.
- Bearer auth reusing/extending `IPC_BEARER_TOKEN` semantics; localhost-only default; token provisioning + rotation (SettingsService-backed); OAuth 2.1 note for Cloud.
- Out of scope for the v1 milestone; documented to prevent rework.

---

## 7. Test Plan (summary)

| Test file | Phase | Verifies |
|---|---|---|
| `test_mcp_workspace_search.py` | 1 | retrieval-shaped `search()`; `WorkspaceSearchService` contract; empty/filter/limit/unknown-ws |
| `test_mcp_media_query.py` | 2 | segment window, page coverage, empty range, cross-workspace refusal |
| `test_mcp_tools.py` | 3 | every tool end-to-end via registry; error semantics matrix |
| `test_mcp_isolation.py` | 5 | cross-workspace isolation invariant (search + resources) — mandatory |
| `test_mcp_stdio_roundtrip.py` | 4 | real stdio round-trip via official MCP client |
| `test_mcp_catalogue_contract.py` | 5 | public-catalogue stability (golden JSON) — non-negotiable |

---

## 8. Manual QA Walkthrough (the v1 success scenario)

1. **Preconditions**: `backend/venv` active; backend running (`uvicorn app.main:app`). Workspace **A** contains an ingested lecture video; a media from workspace **B** exists for negative testing.
2. **Install**: `pip install fastmcp` (pinned as per Phase 0).
3. **Run the server**: `cd backend && python -m app.presentation.mcp.stdio_entrypoint`.
4. **Drive it** — either a QA client (`python scripts/mcp_demo.py`, uses official mcp SDK `ClientSession`, prints a conversation transcript), or a real client config:

```json
{
  "mcpServers": {
    "athenus": {
      "command": "python",
      "args": ["-m", "app.presentation.mcp.stdio_entrypoint"],
      "cwd": "C:/.../athenus/backend"
    }
  }
}
```

5. **Verify the happy path**:
   - `list_workspaces` → returns A and B.
   - `search_workspace(workspace_id=A, query="gradient descent")` → hits carry `workspace_id`, `media_id`, `source_type`, `chunk_id`, `title`, `text`, `location`, `relevance`.
   - Read `athenus://workspace/A/media/{m}/transcript` → `{uri, metadata, content:{segments:[...]}}` with timestamps and text.
6. **Verify the safety path**:
   - `search_workspace(workspace_id=does-not-exist, ...)` → explicit error, **not** `[]`.
   - `athenus://workspace/A/media/{media_from_B}/transcript` → explicit cross-workspace error; nothing from B leaked.
7. **Verify value**: prompt an AI agent to summarize the transcript citing timestamps → source-aware answer.
8. Cleanup: stop the demo client.

---

## 9. Affected Files & Modules

**New**
- `backend/app/bootstrap/mcp.py`
- `backend/app/application/services/workspace_search_service.py`
- `backend/app/application/services/media_query_service.py`
- `backend/app/presentation/mcp/*` (registry, resources, tools/, stdio_entrypoint, http_entrypoint)
- `backend/tests/test_mcp_*.py` + `backend/tests/fixtures/mcp_catalogue_contract.json`
- `scripts/mcp_demo.py`

**Modified**
- `backend/app/application/repositories/media_repository.py` (+ `sqlite_media_repository.py`) — workspace-scoped read methods
- `backend/app/infrastructure/retrieval/multi_stage_retriever.py` — add `search()`; delegate active-context reads
- `backend/app/presentation/api/v1/media.py` — adopt workspace-scoped transcript read
- `backend/requirements.txt`

**Docs (already done this session)**
- `docs/adr/0024-mcp-exposure-layer-and-retrieval-shaped-search.md`
- `docs/CONTEXT.md` (glossary + decisions + status)

---

## 10. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| Moving retriever's window/page helpers regresses citations | Existing retrieval/citation tests guard it; isolated Phase 2 change with full-suite run |
| Cross-workspace leak through a forgotten path | Mandatory isolation test suite (Phase 5); ownership check centralized in `MediaQueryService` |
| FastMCP / mcp-SDK version churn changes auto-schema | Pinned versions + normalized catalogue contract test |
| Windows stdio event-loop behavior | Verified explicitly in the Phase 4 round-trip test |
| Catalogue becomes a "large contract" before core path proven | Hard-scoped 4 tools + 5 resources; anything else is deferred |
| In-place FastAPI app ever needs process isolation | `bootstrap/mcp.py` keeps composition server-shaped so a sidecar is a thin extraction |

---

## 11. Out of Scope / Deferred (explicitly)

- `ask_agent` / agent-layer tools (until `AgentCoordinator` is production-real)
- Learning deck/quiz/analytics resources
- MCP Prompts
- MCP consumption (`MCPToolAdapter`, Phase 5 plan)
- Destructive tools (require opt-in + confirmation mechanism, future)
- Streamable HTTP + bearer auth (Phase 6)