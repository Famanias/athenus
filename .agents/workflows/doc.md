---
description: Generate or update the /doc folder that serves as the canonical source of truth for the entire system using Context Engineering principles.
---

# Architecture Source of Truth

  Your task is to create or maintain the documentation in this repository.

The document should enable both human developers and AI coding agents to understand the system's architecture, design decisions, and relationships without reading the entire codebase.

  ## Objective

Produce a living architecture document that captures **what the system is**, **why it is designed that way**, and **how its major components interact**. The document should prioritize architectural context over implementation details.

  ### Architectural Decision Records

  For each major architectural decision, document:

  - Decision
  - Context
  - Alternatives considered
  - Rationale
  - Trade-offs

  ### Known Limitations

  Document:

  - Current technical debt
  - Architectural limitations
  - Future improvements

  ## Documentation Standards

  - Focus on architecture rather than implementation.
  - Explain *why* decisions were made, not just *what* exists.
  - Prefer diagrams over long textual explanations when appropriate.
  - Use Mermaid diagrams for system topology, request flow, event flow, and dependencies.
  - Reference actual project components rather than hypothetical examples.
  - Organize content with clear headings and a logical hierarchy.
  - Keep explanations concise but comprehensive.

  ## Context Engineering Requirements

  Treat these documents as persistent context for future AI agents.

  It should provide enough architectural knowledge that an AI can:

  - Understand the overall system before making changes.
  - Identify where a feature belongs.
  - Trace request, data, and event flows.
  - Understand component ownership and boundaries.
  - Respect existing architectural constraints.
  - Avoid introducing inconsistent patterns.
  - Make implementation decisions consistent with the established architecture.

  The document should maximize signal while minimizing unnecessary implementation details.

  ## Source of Truth

  This document is the canonical architectural reference.

  Whenever the architecture changes, update this document so it always reflects the current state of the system.

  If information cannot be determined confidently from the codebase, explicitly mark the section as **Incomplete** and list the assumptions or missing information instead of inventing details.