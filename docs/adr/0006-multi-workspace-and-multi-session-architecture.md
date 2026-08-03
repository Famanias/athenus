# ADR 0006: Multi-Workspace & Multi-Session Architecture

## Status
Accepted

## Context
As users build knowledge bases in Athenus Knowledge OS, a single flat chat timeline per workspace becomes cluttered when exploring multiple distinct questions or topics within the same domain (e.g., lecture course). Furthermore, workspace context restoration needs to be deterministic without splitting source-of-truth authority between client local storage and database schemas.

## Decision
1. **Two-Tier Hierarchy**: We establish a parent-child container relationship: **Workspace** (parent learning boundary holding videos, vector index, and knowledge graphs) $\rightarrow$ **Chat Sessions** (child conversations).
2. **Backend as Canonical Source of Truth**: The SQLite database (`athenus.db`) maintains active workspace context and session metadata. Upon app launch, the frontend hydrates state via `GET /api/v1/workspaces/active`.
3. **Lazy Chat Session Creation**: Clicking "+ New Chat" opens an in-memory draft UI state. A database session row is created only when the user submits their first query turn, avoiding empty database clutter.
4. **Deterministic 9-Step Switching Lifecycle**: Workspace switching cancels active LLM generation, clears transient inputs, updates global `WorkspaceContext`, swaps session messages in memory, refreshes library assets and concept graphs, and preserves hidden video DOM nodes without re-parenting (ADR 0005).
5. **Active Workspace Safe Deletion**: Deleting the active workspace automatically switches active context to an available remaining workspace before executing target deletion.

## Rationale
- Prevents embedding duplication across multiple chats in the same workspace while keeping vector search efficient.
- Matches student workflows where a single workspace represents a course, and multiple chat sessions explore specific lecture topics.
- Keeps client memory lean by storing in-memory message history only for the active session.

## Consequences
- **Positive**: Clean context restoration, scalable sidebar rendering via lightweight session preview metadata (`preview_text`, `message_count`, `last_message_at`), and strict vector boundary isolation.
- **Negative**: Requires explicit session ID parameter passing in RAG chat query contracts.
