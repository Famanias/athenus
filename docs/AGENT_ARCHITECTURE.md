# AGENT_ARCHITECTURE.md

# Athenus Knowledge OS — Agentic AI Suite Architecture

---

## Overview

Specialized AI Agents in Athenus Knowledge OS operate as autonomous services managed by the `AgentCoordinator`:

```text
                        ┌───────────────────┐
                        │  AgentCoordinator │
                        └─────────┬─────────┘
                                  │
      ┌───────────────────────────┼───────────────────────────┐
      │                           │                           │
┌─────▼───────┐             ┌─────▼───────┐             ┌─────▼───────┐
│PlannerAgent │             │RetrieverAgent│             │CitationValidatorAgent
└─────────────┘             └─────────────┘             └─────────────┘
```

All specialized agents implement the standard `BaseAgent` protocol:
* `is_applicable(task: TaskContext) -> bool`
* `required_tools() -> List[str]`
* `async execute(input_data: AgentInput) -> AgentOutput`

---

## Agent Suite

1. **PlannerAgent**: Decomposes high-level learning goals into actionable execution steps.
2. **RetrieverAgent**: Coordinates multi-stage context retrieval across workspaces.
3. **CitationValidatorAgent**: Validates timestamp citation accuracy and groundedness.
