# APPLICATION_ARCHITECTURE.md — Desktop & UI Application Architecture

This document specifies the canonical frontend and desktop architecture for **Athenus**.

---

## 1. Desktop Shell Architecture (Tauri + FastAPI Sidecar)

The desktop application is built as a **Local-First Desktop Application**:

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

- **Desktop Shell**: Tauri (`src-tauri/`) manages desktop windowing, native OS file pickers, GPU hardware access, and sidecar process lifecycle.
- **Sidecar Spawning**: On launch, Tauri spawns the FastAPI Python backend executable, supplying an ephemeral authorization token for local IPC request verification.
- **Dynamic Port Assignment**: FastAPI automatically binds to local ports (default `8000`), communicating health state to Tauri.

---

## 2. Presentation Layer Component Architecture (`frontend/src/`)

Built with React 18, Next.js 16 (Turbopack), TypeScript, Vanilla CSS design tokens, and Zustand state management:

### 2.1 Single Authoritative Video Player Architecture
- **Persistent DOM Container**: To prevent browser Picture-in-Picture (PiP) node detachment, `<VideoWorkspace />` is mounted inside a persistent container in [`DesktopShell.tsx`](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx) with CSS `display: none` (`hidden`) when navigating between workspace views.
- **Zero DOM Re-parenting**: The HTML5 `<video>` DOM element's parent container **never changes**, React **never invokes `removeChild()`**, and the browser **never detaches the player node**, guaranteeing strictly 1 active video player and 0 duplicate audio instances.

### 2.2 Core Feature Modules
1. **Video Workspace (`VideoWorkspace.tsx`)**:
   - Synchronized transcript reader with card-level timestamp click-to-seek navigation (`seekToSeconds`).
   - Resizable side panel (draggable split handle from 260px to 650px) and one-click collapse toggle (`◀ Panel` / `▶ Hide`).
   - Embedded Context-Aware AI Chat Widget ([`EmbeddedChatWidget.tsx`](file:///e:/repos/athenus/frontend/src/features/chat/EmbeddedChatWidget.tsx)).
2. **Interactive RAG Chat Workspace (`ChatWorkspace.tsx`)**:
   - Per-message grounded citations: Assistant responses carry turn-specific evidence badges (`citations`).
   - Interactive evidence inspection: Clicking any historical assistant response bubble updates `selectedMessageId` and inspects that turn's evidence in `RetrievedEvidencePanel`.
   - Clear Conversation Action: Invokes `DELETE /api/v1/chat/history` to purge SQLite session records and resets local chat state.
3. **Workspace Library (`LibraryGrid.tsx`)**:
   - Workspace asset grid displaying indexed video assets, transcript status badges, and asset selection handlers.
4. **Ingestion Pipelines (`UploadDropzone.tsx`)**:
   - Drag-and-drop video upload zone with real-time SSE stage progress telemetry.
5. **System Settings (`SystemSettings.tsx`)**:
   - **Persistent Settings Management**: Interfaces with `SettingsService` via `GET/PUT /api/v1/settings/providers` and `GET/PUT /api/v1/settings/ollama`.
   - **Local Model Sources & Discovery**: Displays configured and resolved Ollama directory paths (`.ollama` $\rightarrow$ `.ollama/models`), scan status badges (`✓ Valid (X models)` / `✕ Invalid Directory`), and interactive **Save** and **Refresh** controls.
   - **Dynamic Model Selection**: Renders a dynamic `<select>` dropdown populated from discovered local models with seamless provider restoration across Groq and Ollama.
   - **System Clear Data**: Triggers atomic system reset (`POST /api/v1/system/clear-data`) purging SQLite records and vector collections while restoring a clean single default workspace.
