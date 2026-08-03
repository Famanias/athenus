Phase 1 — Establish a True Persistent Workspace (Highest Priority)

Goal: Make the knowledge base survive application restarts and become the source of truth.

Key Issues
Media metadata is not fully persistent (appears to rely on in-memory repositories).
Chat history is lost after restart.
The workspace cannot completely reconstruct itself after reopening.
Multiple storage layers (SQLite, Qdrant, filesystem) are not synchronized by a single source of truth.
Why this matters

A user expects this workflow:

Create Workspace
    ↓
Upload 10 lectures
    ↓
Close Athenus
    ↓
Reopen next week
    ↓
Everything is still there

Today, parts of that workflow appear to be missing or dependent on in-memory state.

Recommended Solution
Make SQLite the canonical metadata database.
Persist:
Workspaces
Videos
Transcripts
Processing status
Chat sessions
On application startup:
Load workspace metadata from SQLite.
Reconnect to existing Qdrant collections.
Restore the user's previous state.

Priority: 🔴 Critical

Phase 2 — Proper Workspace Isolation

Goal: Ensure every workspace behaves as an independent knowledge base.

Key Issues

Potential findings suggest retrieval may not always be scoped strongly enough.

If embeddings are searched without workspace filtering, knowledge leakage becomes possible.

Example:

Workspace A
Machine Learning

Workspace B
History

Question:

Explain gradient descent.

The assistant should never retrieve content from Workspace B.

Recommended Solution

Every embedding should include metadata such as:

workspace_id
video_id
chunk_id
document_type
embedding_version

Every retrieval query should filter by:

workspace_id

first.

This establishes proper knowledge isolation.

Priority: 🔴 Critical

Phase 3 — Unified Knowledge Lifecycle

Goal: Define one complete lifecycle for every uploaded resource.

Key Issues

The review highlights that the ingestion pipeline exists, but the lifecycle isn't fully formalized.

There should be a clearly defined flow:

Video
↓
Speech-to-Text
↓
Transcript
↓
Semantic Chunking
↓
Embedding
↓
Vector Store
↓
Metadata Database
↓
Retrieval
↓
Prompt Construction
↓
LLM

Currently, some stages appear loosely coupled.

Recommended Solution

Create a formal ingestion pipeline where every stage records:

status
timestamps
failures
retries

Each uploaded video should have a complete processing history.

Priority: 🟠 High

Phase 4 — Conversation & Memory Architecture

Goal: Separate different types of memory.

Key Issues

The current implementation appears to blur together:

UI state
Chat history
Workspace knowledge
Vector memory

These should be treated as different architectural concepts.

Recommended Solution

Define distinct memory layers:

UI Memory
    ↓
Conversation Memory
    ↓
Workspace Memory
    ↓
Knowledge Memory
    ↓
Vector Memory

Each layer should have:

storage location
persistence duration
ownership
retrieval strategy

This makes future features like long-term memory and conversation history much easier to implement.

Priority: 🟠 High

Phase 5 — Update & Deletion Consistency

Goal: Keep every storage layer synchronized.

Key Issues

The review raises questions such as:

What happens if a video is reprocessed?
What happens if embeddings change?
What happens when a workspace is deleted?
What happens when a transcript changes?

Without a clear strategy, orphaned vectors and stale metadata can accumulate.

Recommended Solution

Implement lifecycle operations for every resource:

Create
Update
Reindex
Delete
Restore

Deletion should remove:

metadata
vectors
cached files
transcripts
processing artifacts

in a single coordinated operation.

Priority: 🟠 High

Phase 6 — Scalability & Performance

Goal: Prepare for large knowledge bases.

Key Issues

The current architecture hasn't yet been evaluated for:

100 videos
1,000 videos
hundreds of thousands of chunks

Questions remain around indexing strategy, retrieval efficiency, and duplicate handling.

Recommended Solution

Introduce:

metadata indexing
efficient vector filtering
duplicate detection
embedding versioning
retrieval benchmarking

Define scalability targets so performance remains predictable as workspaces grow.

Priority: 🟡 Medium

Phase 7 — Operational Visibility & Diagnostics

Goal: Make the system observable and easier to debug.

Key Issues

As the ingestion and retrieval pipeline becomes more complex, diagnosing failures will become increasingly difficult without visibility into each stage.

Recommended Solution

Track and expose:

ingestion progress
embedding progress
retrieval metrics
prompt construction
processing errors
retry attempts
latency
storage synchronization

Provide this information in a developer or diagnostics view so issues can be identified quickly.

Priority: 🟡 Medium

Overall Assessment

The architecture already contains the essential building blocks of a modern RAG-based learning platform:

✅ Video ingestion
✅ Speech-to-text
✅ Semantic chunking
✅ Vector search
✅ LLM integration
✅ Workspace organization

The remaining work is less about adding new capabilities and more about strengthening the architecture around persistence, isolation, lifecycle management, and scalability.