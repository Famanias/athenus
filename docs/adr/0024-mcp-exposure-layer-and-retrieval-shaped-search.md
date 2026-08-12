# ADR 0024: MCP Exposure Layer & Retrieval-Shaped Search

- **Status**: Approved (design frozen — implementation pending)
- **Date**: 2026-08-12
- **Deciders**: Athenus Architecture Team

## Context & Problem Statement

Athenus is evolving from a standalone, local-first learning application into a personal knowledge system that AI agents can access. Today the only way an external agent can reach Athenus knowledge is through the REST/UI surface (an unauthenticated, human-oriented API). There is no stable, AI-facing protocol, no way for an external agent to search and retrieve the user's actual workspace knowledge with provenance, and no decision recorded for how the planned Agentic AI Suite (Phase 5, `architecture-review-842026.md`) would compose external tooling.

A prior Phase 5 plan proposed an `MCPToolAdapter` — Athenus *consuming* external MCP servers as tools. This ADR records the *inverse and complementary* decision: Athenus *exposes* an MCP server so external AI agents can access its knowledge.

## Decision Drivers

1. **Local-First & Offline Privacy**: The exposure layer must run 100% offline in Local Mode (Tauri desktop, native dev) and continue to honor the Docker/Hybrid/Cloud deployment modes without special-casing in business logic.
2. **No Architectural Duplication**: The MCP layer must call the same application/domain services the REST API uses. It must not re-implement RAG, retrieval, citation validation, ingestion, graph, or learning logic, and it must not call Athenus' own HTTP endpoints.
3. **Provenance Integrity**: Athenus' differentiator is "LLM-readable knowledge *with provenance*." The AI-facing contract must not flatten knowledge into anonymous text.
4. **Safety**: The MCP server is deliberately a new AI-facing attack surface (multiple agents, potentially remote). It must be read-heavy and safe by default, with explicit workspace authorization as a hard invariant.
5. **Backwards-Compatible Evolution**: The MCP catalogue is a stable public interface. Changes to tool names, parameters, or resource URIs must be explicit and controlled.

## Decided Architectural Choices

### 1. Athenus Exposes an MCP Server (Exposure Layer)
Athenus becomes an MCP server exposing real capabilities to external AI agents. MCP is an **exposure/interface layer** — not an application layer. Dependency direction is strictly:

```
MCP Transport
  → MCP Tool/Resource Registry (thin)
  → Application Services
  → Domain
  → Infrastructure
```

The same underlying application service must be usable by REST, MCP, Tauri, and (later) internal agents. The inverse direction (`MCPToolAdapter` consuming external MCP servers, Phase 5) is parked and distinct.

### 2. Local-First Implementation, Two Transports, One Catalogue
- **stdio** is implemented first (Claude Code, Cursor, local desktop integration). The process boundary is the trust boundary; no network auth.
- **Streamable HTTP** is a later transport over the *exact same* tool/resource registry (Claude Desktop, remote clients). Bearer-token auth required; reuse/extend the existing per-installation `IPC_BEARER_TOKEN` semantics (`core/config.py:77`); support token rotation; default to localhost-only exposure. OAuth 2.1 reserved for Cloud/remote.
- Legacy SSE is not implemented unless a concrete requirement appears.
- Transport must not determine business logic: both transports execute the same catalogue.

### 3. Iplementation: FastMCP on the Official MCP SDK
FastMCP (built on the official `mcp` Python SDK) provides decorator-based tool/resource registration, auto-generated JSON Schema from function signatures, and stdio + Streamable HTTP out of the box. The MCP layer stays **thin**: validate MCP input → resolve/inject the application service → call it → transform the application result into an MCP-compatible shape. No business logic lives in the MCP layer.

### 4. Tool + Read-Only Resource Catalogue
MCP primitives used in v1: **Tools** (search/discovery/analysis — `search_workspace`, `list_workspaces`, …) and **read-only Resources** (addressable knowledge — transcripts, concepts, …). Tools *discover or perform operations*; Resources *represent addressable knowledge*. **Prompts are deferred.**

### 5. Explicit Workspace Scope (No Implicit State)
MCP v1 has **no implicit active workspace**. Every workspace-scoped operation — Tool *or* Resource — must identify its workspace explicitly. Resource URIs therefore embed the workspace id:

```
athenus://workspace/{workspace_id}/media/{media_id}/transcript
```

Agents discover workspaces via `list_workspaces` and select explicitly. Convenience `set/get_active_workspace` tools are deferred.

### 6. Canonical Source Taxonomy
Athenus exposes exactly three source types: **`video | audio | document`**. A document is a `MediaItem` with `MediaType.DOCUMENT` (see ADR 0021). The legacy internal `"pdf"` sentinel is normalized to `"document"` at the application boundary. MCP never exposes `pdf` as a source type.

### 7. Search Is a Retrieval Capability, Distinct from Answer Synthesis
- `WorkspaceSearchService` (application layer) owns the search contract and answers "What relevant knowledge exists?"
- `MultiStageRetriever.search()` is a **retrieval-shaped** path: runs the information-gathering stages (query rewrite, hybrid FTS5 + dense vector, RRF fusion, rerank), returns `top_k` candidates with relevance and full provenance. It does **not** assemble a generation prompt, does **not** token-compress for synthesis, and does **not** run the conversational-query guard used by `execute_retrieval`.
- `query_workspace()` remains the synthesis capability ("Use relevant knowledge to answer this question."). The two are separate and must stay separate.
- The public search result contract is relevance + provenance: `workspace_id`, `source_id`, `source_type`, `chunk_id`, `title`, `text`, source-specific `location` (video/audio: start/end seconds; document: page/section), and a stable relative `relevance` value — internal RRF/rerank scores are not part of the public contract unless they carry a meaningful interpretation.

### 8. MediaQueryService Owns Transcript/Document Reads
Transcript, document, and segment reads are a distinct application capability, not a concern of the retrieval engine. `MediaQueryService` provides `get`, `get_transcript`, `get_segment`, `get_document_content` over `MediaRepository`. **Workspace ownership validation lives here**: every read verifies the requested media belongs to the requested workspace before returning content. The retriever's private timestamp/page-window query helpers are moved into this capability; the retriever may reuse them but does not own them.

### 9. Structured JSON Resources (Provenance-Preserving)
All MCP resources are `application/json` with a consistent envelope separating **resource identity URI**, **metadata/provenance** (workspace_id, source_id, source_type, title), and **structured content** (segments with `chunk_id`/timestamps; document pages with `page`/`section`/`chunk_id`; concept with definition/aliases/relationships/source references). Never flattened to `text/plain` — a client can always derive natural language from structured knowledge, but cannot reconstruct discarded provenance.

### 10. Explicit Error Semantics (Authorization Is Not "Not Found")
The protocol distinguishes three states that must not collapse:
1. **Unknown workspace / workspace cannot be accessed** → explicit error.
2. **Cross-workspace resource access** (media exists, but not in the requested workspace) → explicit error, leaking no content or metadata about the other workspace.
3. **Known workspace + missing item** → explicit not-found error.
4. **Legitimate search, zero matches** → `[]` (not an error).

The workspace identifier in a resource URI or tool argument is an explicit scope/authorization boundary.

### 11. Destructive Operations Excluded
Destructive capabilities (e.g., `POST /system/clear-data`, database reset, delete, filesystem/SQL access) are **excluded from the default catalogue**. Any future destructive tool requires explicit opt-in configuration plus an additional authorization/confirmation mechanism.

### 12. Composition Root Is Separated from Presentation
A dedicated `bootstrap/mcp.py` composition root constructs repositories, application services, the MCP registry, and the FastMCP server. Both entrypoints (stdio now, Streamable HTTP later) share it. `presentation/mcp/` stays logic-free. Dependency construction is never duplicated between entrypoints.

## Initial Catalogue (v1 Milestone)

**Tools:**

```
list_workspaces
search_workspace
search_concepts
get_transcript_segment
```

**Resources (read-only, structured JSON):**

```
athenus://workspace/{workspace_id}
athenus://workspace/{workspace_id}/media/{media_id}
athenus://workspace/{workspace_id}/media/{media_id}/transcript
athenus://workspace/{workspace_id}/media/{media_id}/document
athenus://workspace/{workspace_id}/graph/concept/{concept_id}
```

**Explicitly deferred from v1:** learning deck/quiz resources, analytics resource, `ask_agent` (until `AgentCoordinator` is production-real), MCP consumption (`MCPToolAdapter`), Prompts.

## Verification

Three required verification layers (all enforced in CI):

1. **Tool/application-level integration tests** — each MCP tool tested against real application services over temporary data: correct workspace scoping, correct results, provenance fields, invalid-workspace handling, missing media/document handling, limits, empty results, source-type filtering.
2. **Real MCP stdio round-trip test** — an official MCP client drives the FastMCP stdio server for a real operation (`search_workspace` → `WorkspaceSearchService` → retrieval → provenance-shaped hit; transcript resource read). Proves the protocol layer works, not merely that Python functions work.
3. **MCP catalogue contract test** — detects accidental changes to tool names, parameters, required/optional arguments, resource URI templates, and output envelope/schema. Non-negotiable, normalized (not a brittle per-SDK-version schema snapshot).

**Mandatory cross-workspace isolation tests:** workspace A content must never be returned by a `search_workspace(workspace_id=B, …)` call; a resource URI `athenus://workspace/A/media/{media_from_B}/transcript` must fail. Workspace scoping is treated as an explicit authorization boundary, never relying on media-id globality.

## Consequences

- **Positive**: Athenus gains a stable AI-facing public capability interface; the same application services serve REST and MCP (no duplication); cross-workspace isolation is enforced at the application layer; retrieval-shaped search is reusable groundwork for RAG reliability improvements independent of MCP; HTTP exposure can be added later without changing the catalogue.
- **Negative / Risks**: a new stable public interface requires backwards-compatible evolution of the catalogue from v1 onward (hence the contract test); moving the retriever's private timestamp/page-window helpers into `MediaQueryService` is a refactor with regression risk (mitigated by existing retrieval/citation tests); FastMCP/SDK version churn is possible (mitigated by pinned versions and the normalized contract test); Windows stdio event-loop behavior must be verified in the round-trip test.