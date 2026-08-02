# WORKSPACE_ARCHITECTURE.md

# Athenus Knowledge OS — Workspace & Multi-Media Architecture

---

## Overview

Workspaces serve as the primary organizational and security boundary within Athenus Knowledge OS.

A **Workspace** isolates:
* Uploaded content & transcripts (`media_items`)
* Vector indices & payload partitions
* User Memory & learning history
* Conversation history & notes

```text
                       ┌─────────────────────────┐
                       │     Workspace Context   │
                       └────────────┬────────────┘
                                    │
    ┌───────────────────────┬───────┴───────────────┬───────────────────────┐
    │                       │                       │                       │
┌───▼───────────────┐   ┌───▼───────────────┐   ┌───▼───────────────┐   ┌───▼───────────────┐
│ Media Collection  │   │ Knowledge Storage │   │ Structured Memory │   │ Active Learning   │
│ (Videos/Audio/PDF)│   │(Vectors & Chunks) │   │(Progress/Mastery) │   │ (Quizzes/Cards)   │
└───────────────────┘   └───────────────────┘   └───────────────────┘   └───────────────────┘
```

---

## Workspace REST API

* **Create Workspace**: `POST /api/v1/workspaces`
* **List Workspaces**: `GET /api/v1/workspaces`
* **Get Workspace**: `GET /api/v1/workspaces/{workspace_id}`
