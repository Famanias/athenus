# APPLICATION_ARCHITECTURE.md — Desktop & UI Application Architecture

This document specifies the canonical frontend, studio features, background workers, and desktop architecture for **Athenus**.

---

## 1. Desktop Shell Architecture (Tauri + FastAPI Sidecar)

```text
┌─────────────────────────────────────────────────────────────┐
│                     Tauri Desktop Shell                     │
│                                                             │
│  ┌───────────────────────┐       Internal REST & SSE        │
│  │ Next.js 16 (Turbopack) │ ─────────────────────────────┐   │
│  └───────────────────────┘   Bearer Token Authorization │   │
│                                                         │   │
│  ┌──────────────────────────────────────────────────┐   │   │
│  │ FastAPI Backend Sidecar (Python Executable)      │ ◄─┘   │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

- **Desktop Shell**: Tauri (`src-tauri/`) manages windowing, native OS file pickers, GPU hardware access, and sidecar process lifecycle.
- **Sidecar Spawning**: On launch, Tauri spawns the FastAPI Python backend executable on port `8000`.
- **Zero-Detachment Media Player**: `<VideoWorkspace />` is mounted inside a persistent container in [`DesktopShell.tsx`](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx) with CSS `display: none` when switching views. This guarantees zero DOM re-parenting and keeps PiP media playing smoothly.

---

## 2. Core Feature Studios & Views (`frontend/src/features/`)

1. **Video Workspace (`view-video` — `VideoWorkspace.tsx`)**:
   - Synchronized transcript reader with timestamp click-to-seek navigation (`seekToSeconds`).
   - Workspace video asset selector dropdown populated **only** with videos belonging to the active workspace.
   - Resizable side panel (draggable split handle from 260px to 650px) with embedded context-aware AI assistant widget.

2. **Interactive Knowledge Graph Canvas (`view-graph` — `KnowledgeGraphCanvas.tsx`)**:
   - Interactive SVG canvas with zoom, pan, force-directed layout, node inspector, shortest-path calculation between concepts, and timestamp jump links to lecture videos.

3. **Active Recall Flashcard Studio (`view-flashcards` — `FlashcardGrid.tsx`)**:
   - 3D flip card reader with SuperMemo-2 (SM-2) rating buttons (Again/Hard/Good/Easy).
   - In-Studio Toolbar controls: Inline `⚡ Auto-Evolve` toggle and `Target Budget` dropdown (10-50 items).
   - Instant Anki `.apkg` and CSV export.

4. **Adaptive Quiz Studio (`view-quiz` — `QuizStudio.tsx`)**:
   - Timed quiz runner with concept-balanced question sampling.
   - Immediate answer grading (green/red feedback), detailed explanations, provenance timestamp links, and attempt score summary.
   - In-Studio Toolbar controls: Inline `⚡ Auto-Evolve` toggle and `Target Budget` dropdown.

5. **Precomputed Analytics Dashboard (`view-analytics` — `AnalyticsDashboard.tsx`)**:
   - Real-time stat cards (study time, review streaks, quiz averages, total reviews).
   - Concept mastery progress bars computed from active recall accuracy and review coverage.
   - Priority revision plan recommendations with direct jump links to low-mastery concepts.

6. **Unified Learning Pipeline (`view-ingestion` — `UnifiedLearningPipeline.tsx`)**:
   - Drag-and-drop video upload zone with real-time SSE progress telemetry and downstream studio stage links.

7. **System Settings (`view-settings` — `SystemSettings.tsx`)**:
   - Provider settings, hardware acceleration GPU toggles, local Ollama directory path inspection, and **CLEAR MY DATA** (21-table atomic factory reset).

---

## 3. Background Workers & Event Subscribers (`backend/app/services/workers/`)

- **`GraphExtractionWorker`**: Listens for `ChunksIndexedEvent` and extracts concepts/relations via LLM (with heuristic fallback). Publishes `ConceptGraphUpdatedEvent`.
- **`LearningEvolutionWorker`**: Listens for `ConceptGraphUpdatedEvent`. If auto-evolution is enabled for the workspace, calculates delta concepts using `ConceptImportanceAllocator` and automatically generates evolved `vN+1` decks and quizzes.
- **`AnalyticsService` Event Handler**: Subscribes to `QuizAttemptEvent`, `FlashcardReviewedEvent`, and `ConceptGraphUpdatedEvent` to maintain real-time precomputed counters in `WorkspaceAnalyticsTable` and `ConceptMasteryTable`.
