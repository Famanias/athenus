# Resource-owned frontend query caching

Frontend cache policy belongs to resource-specific query modules, not the generic HTTP transport. Transcript queries therefore own workspace/media query keys, freshness, subscriptions, and exact invalidation after ingestion completes, while the API client remains cache-neutral. We rejected method-based caching inside the transport because it had no resource lifecycle context and could return a stale empty transcript after processing changed server state.

## Consequences

- Every cached resource defines its own identity and invalidation triggers.
- Components subscribe to query state instead of copying cached responses into parallel local state.
- Mutations invalidate only the affected resource key, preventing cross-workspace or unrelated-resource refreshes.
