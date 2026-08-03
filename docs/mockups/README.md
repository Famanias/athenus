# Athenus — Product UX Architecture Prototype

> **Single-File Interactive Desktop UX Prototype & Design Specification**

---

## Executive Summary & Product Vision

This directory contains the self-contained, interactive **Product UX Prototype** for **Athenus**.

Designed from the perspective of a **Senior Product Designer & UX Architect**, this prototype visualizes what Athenus Version 1.0 looks and feels like when running as a flagship local-first desktop application.

---

## Athena Design System & Color Palette

The interface enforces the official **Athena Theme**:

* **Background Navy (`#051424`)**: Deep, focused midnight blue.
* **Surface Container Dark Blue (`#0d1c2d`, `#122131`, `#1c2b3c`)**: Layered slate containers providing subtle visual depth.
* **Athena Gold Accent (`#e9c349`)**: High-contrast gold highlighting active tabs, timestamps, concept badges, and mastery progress.
* **Ice Blue Text (`#d4e4fa` & `#c6c6cc`)**: High-contrast text readability.

---

## Categorized Sidebar Architecture

The left navigation sidebar is structured into **3 Mythological & Functional Domain Categories** derived directly from Athena's identity:

```text
🦉 Wisdom (Νοῦς / Sophia) — Highest Reasoning & Search
 ├── AI Research Assistant
 ├── Ask & Explain Concepts
 └── AI Synthesis Insights

📚 Knowledge (Episteme) — Intellectual Mastery & Content Processing
 ├── Workspace Library
 ├── Video Learning Workspace
 ├── Transcript Reader
 └── Concept Knowledge Graph

⚔️ Strategy (Metis) — Active Learning & Recall Operations
 ├── Active Recall Flashcards (Anki SM-2)
 ├── Adaptive Quizzes
 └── Memory & Progress Analytics

⚙️ Infrastructure
 ├── Ingestion Pipeline
 └── AI Models & Providers
```

---

## Interactive Features & View Navigation

* **Single-File Architecture**: Self-contained inside `docs/mockups/index.html`. Open directly in any browser.
* **View Switching**: Clean sidebar navigation showing only **one view at a time** (no clutter).
* **Click-to-Seek Transcript Sync**: Clicking any timestamp (e.g. `12:40`) switches to the Video Workspace and updates playback.
* **3D Flashcard Flips**: Click any flashcard to flip between Question and Answer.
* **Adaptive Quiz Scoring**: Interactive option selection with instant correctness evaluation and explanation feedback.
* **Command Palette Modal (`Ctrl + K` / `Cmd + K`)**: Keyboard shortcut opening global search and view switcher overlay.

---

## How to View

Open [docs/mockups/index.html](file:///e:/repos/athenus/docs/mockups/index.html) directly in any web browser.
