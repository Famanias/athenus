# APPLICATION_ARCHITECTURE.md

# Athenus Knowledge OS — Desktop & UI Application Architecture

---

## Desktop Shell Architecture (Tauri + FastAPI Sidecar)

The desktop application is built as a **Desktop-First application powered by a local web architecture**:

```text
┌─────────────────────────────────────────────────────────────┐
│                     Tauri Desktop Shell                     │
│                                                             │
│  ┌───────────────────────┐       Internal REST & SSE        │
│  │ Next.js Frontend (UI) │ ─────────────────────────────┐   │
│  └───────────────────────┘   Bearer Token Authorization │   │
│                                                         │   │
│  ┌──────────────────────────────────────────────────┐   │   │
│  │ FastAPI Backend Sidecar (Python Executable)      │ ◄─┘   │
│  └──────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────┘
```

* **Desktop Shell**: Tauri (`src-tauri/`) manages windowing, local OS permissions, GPU hardware access, and process lifecycle.
* **Sidecar Launch**: On launch, Tauri spawns the FastAPI Python sidecar executable, passing an ephemeral bearer token (`IPC_BEARER_TOKEN`) for local IPC request security.
* **Dynamic Port Assignment**: FastAPI automatically binds to available local ports (default `8000`), emitting its port to Tauri stdout during startup.

---

## Presentation Layer Component Breakdown (`frontend/`)

Built with React, Next.js, TypeScript, and Tailwind CSS:

1. **Main Layout (`app/page.tsx`)**: Responsive 12-column grid layout organizing video player, interactive transcript, and RAG chat.
2. **Media Player (`MediaPlayer.tsx`)**: Custom HTML5 video player component with programmatic seek-to-timestamp capability.
3. **Interactive Transcript Viewer (`TranscriptViewer.tsx`)**: Real-time auto-scrolling transcript synced with video playback position, with click-to-seek timestamp navigation.
4. **Chat Interface (`ChatInterface.tsx`)**: Interactive RAG chat UI rendering assistant responses and clickable timestamp citation badges `[MM:SS - MM:SS]`.
5. **Worker Progress Monitor (`WorkerMonitor.tsx`)**: Real-time status indicator showing active background ingestion and worker job progress.
