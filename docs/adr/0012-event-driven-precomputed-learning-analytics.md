# ADR 0012: Event-Driven Precomputed Learning Analytics

* **Status**: Accepted & Implemented
* **Date**: 2026-08-06
* **Context**: Traditional analytics dashboards perform expensive dynamic SQL aggregations on every dashboard view, or display superficial metrics like "hours studied" that do not reflect true knowledge retention.
* **Decision**: Implement **Event-Driven Precomputed Learning Analytics** (`AnalyticsService`). The subsystem subscribes to domain events (`QuizAttemptEvent`, `FlashcardReviewedEvent`, `ConceptGraphUpdatedEvent`) on the event bus and updates denormalized counter tables (`WorkspaceAnalyticsTable`, `ConceptMasteryTable`, `StudySessionTable`) in real time. Dashboard queries perform fast single-row primary key reads.
* **Alternatives Considered**:
  - *On-the-Fly SQL Aggregation*: Slow query response times as study history grows.
  - *Superficial Video Watch-Time Counters*: Low pedagogical value.
* **Rationale**: Derived analytics based on active recall accuracy, review intervals, and quiz performance reflect genuine concept mastery. Event-driven precomputation ensures sub-10ms dashboard loads.
* **Trade-offs**: Requires event bus handlers to maintain denormalized tables, but provides instant UI responsiveness.
