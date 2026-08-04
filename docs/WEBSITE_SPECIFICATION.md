# Product Specification & Requirements: Athenus Official Website

**Document Version:** 1.0.0  
**Status:** Canonical Product & Design Specification  
**Target Audience:** Frontend Developers, UI/UX Designers, Product Managers, Technical Writers  
**Project:** Athenus Knowledge OS — Official Marketing Website & Product Discovery Platform

---

## Executive Summary

This document serves as the canonical **Product Specification and Requirements Document** for designing and building the official marketing website for **Athenus Knowledge OS**.

Athenus is a **local-first, offline-capable AI Learning Operating System** designed to transform video lectures, audio recordings, and educational media into grounded, interactive AI conversations with instant timestamp citations, concept graphs, and spaced-repetition flashcards.

The website must establish Athenus as a flagship open-source AI project, communicate its unique local-first value proposition, drive desktop downloads across Windows, macOS, and Linux, encourage GitHub community engagement, and provide a world-class, interactive product showcase.

---

## 1. Product Positioning

### 1.1 Product Definition
Athenus is a private, local-first **AI Learning Operating System (Knowledge OS)**. It converts unstructured video/audio lectures into searchable, explainable knowledge through an 8-stage hybrid RAG engine, automatic concept graph extraction, and active recall learning tools (quizzes and Anki flashcards).

### 1.2 Target Users
- **Students & Academics:** Students tackling hours of video lectures, online courses, and exam preparation.
- **Self-Learners & Lifelong Students:** Learners consuming technical tutorials, Coursera courses, and YouTube lectures.
- **Researchers & Developers:** Technical professionals indexing lecture content and studying cutting-edge local RAG architectures.
- **Educators & Instructors:** Teachers generating quizzes, concept prerequisite maps, and study materials from course recordings.

### 1.3 Problems Solved
- **Video Information Overload:** Watching hours of video passively is slow, inefficient, and difficult to reference.
- **Missing Timestamp Citations:** Generic AI chatbots hallucinate or provide vague text answers without proof of where the information was spoken.
- **Privacy & Cloud Lock-In:** Traditional AI tools require uploading personal study materials to third-party servers with recurring subscription fees.
- **Fragmented Learning Workflow:** Note-taking, flashcard creation, quiz building, and concept mapping usually require 4–5 separate applications.

### 1.4 Unique Value Proposition (UVP)
> *"Turn hours of video lectures into grounded AI conversations with clickable timestamp citations, visual concept graphs, and automatic flashcards—running 100% offline on your desktop."*

### 1.5 Key Differentiators
1. **Local-First & Offline-Capable:** Runs 100% locally using Faster-Whisper, BGE Embeddings, Embedded Qdrant, SQLite, and Ollama model scanning. Zero cloud dependency.
2. **8-Stage Grounded RAG with Timestamp Citations:** Hybrid vector + BM25 search + Cross-Encoder reranking delivering exact clickable time badges (`[12:34 - 15:20]`) that seek the video player automatically.
3. **Active Playback Context Extraction:** Real-time extraction of surrounding spoken transcripts ($\pm 30\text{s}$) around the user's active video timestamp.
4. **All-in-One Active Recall Suite:** Built-in Quiz Studio and Spaced Repetition Flashcard Studio with native Anki (`.apkg`) export.
5. **Zero DOM Re-Parenting Desktop Shell:** Tauri-native video player state preservation allowing seamless switching between Chat, Knowledge Graph, and Video views without video reloads.

### 1.6 Elevator Pitch
> "Athenus is your private, local-first AI Learning Operating System. Transform video lectures into interactive AI conversations with instant timestamp citations, visual concept maps, and spaced-repetition flashcards. 100% free, open-source, and private on your machine."

### 1.7 Brand Personality
- **Academic & Rigorous:** Deeply committed to grounded truth and verifiable sources.
- **Empowering & Private:** Respectful of user sovereignty and data ownership.
- **Cutting-Edge & Sleek:** High-performance desktop feel with dark-mode aesthetic.
- **Accessible & Open:** Free, open-source, community-driven.

### 1.8 Core Messaging Hierarchy
- **Primary Tagline:** *"Learn Faster. Remember Everything. Own Your Data."*
- **Secondary Headline:** *"The Local-First AI Learning Operating System for Video Lectures & Course Material."*
- **Call to Action:** *"Download Athenus for Desktop"* / *"Star on GitHub"*.

---

## 2. Website Goals

| Goal Category | Primary Objective | Metric / KPI |
|---|---|---|
| **Product Discovery** | Clearly articulate what Athenus is within 5 seconds of arriving on the site. | < 25% Bounce Rate, > 2 min Avg Session Duration |
| **Desktop Downloads** | Drive desktop app downloads for Windows, macOS, and Linux. | Download Conversion Rate > 15% |
| **Open Source Engagement** | Encourage GitHub stars, forks, and open-source contributions. | GitHub Star Growth & Fork Count |
| **Interactive Showcase** | Allow users to experience the UI, 8-stage RAG, and timestamp citations interactively in the browser. | Showcase Demo Engagement Rate > 60% |
| **Documentation Access** | Provide clear navigation to installation guides, architecture docs, and API specs. | Docs Traffic & Low Support Ticket Ratio |
| **Community & Trust** | Showcase local-first privacy guarantees, security model, and open-source license. | Trust Signal Impressions & Community Joins |

---

## 3. Target Audience Personas

### Persona 1: Alex — The Computer Science Student
- **Goal:** Pass university exams and synthesize 40 hours of lecture recordings.
- **Frustration:** Re-watching full 2-hour lectures just to find a 3-minute explanation of Gradient Descent.
- **Website Need:** Quick download button, clear visual proof of timestamp citations, and flashcard export feature demo.

### Persona 2: Maya — The Self-Taught ML Developer
- **Goal:** Learn deep learning fundamentals from online video series.
- **Frustration:** Cloud AI chatbots hallucinate concepts and don't provide source provenance.
- **Website Need:** Deep dive into the 8-Stage Hybrid RAG architecture, vector search details, and local Ollama model support.

### Persona 3: Prof. David — Educational Content Creator
- **Goal:** Generate quizzes and concept prerequisite maps for students from lecture audio.
- **Frustration:** Manual quiz creation takes hours; existing tools require uploading proprietary course materials to cloud vendors.
- **Website Need:** Privacy & offline guarantees, Quiz Studio preview, and Knowledge Graph workflow demonstration.

---

## 4. Complete Site Map & Navigation Architecture

```text
Athenus Marketing Website
 ├── Header Navigation (Global)
 │    ├── Logo & Identity (Athenus Knowledge OS)
 │    ├── Features
 │    ├── How It Works
 │    ├── Showcase
 │    ├── Roadmap
 │    ├── Docs (External / Subdomain)
 │    ├── GitHub Star Badge (Live counter)
 │    └── Download Button (Auto-detect OS)
 │
 ├── Landing Page (/)
 │    ├── 1. Hero Section
 │    ├── 2. Proof & Trust Banner
 │    ├── 3. Core Feature Highlights (3-Column Grid)
 │    ├── 4. Interactive Product Showcase (Tabbed Desktop App Sandbox)
 │    ├── 5. Learning Workflows (3-Step Lifecycle)
 │    ├── 6. Local-First & Privacy Sovereign Matrix
 │    ├── 7. Deep Dive: 8-Stage Layered RAG Pipeline
 │    ├── 8. Deep Dive: Knowledge Graph & Active Recall
 │    ├── 9. Local & Cloud Model Ecosystem
 │    ├── 10. Multi-Platform Download Matrix
 │    ├── 11. Open Source & Community Hub
 │    ├── 12. Frequently Asked Questions (FAQ)
 │    └── 13. Final CTA & Footer
 │
 ├── Download Hub (/download)
 │    ├── Windows (.exe / .msi)
 │    ├── macOS (.dmg / Apple Silicon & Intel)
 │    ├── Linux (.AppImage / .deb)
 │    ├── Build from Source (Git + Cargo + Node)
 │    └── Checksums & Release Notes
 │
 ├── Architecture & RAG Explainer (/how-it-works)
 │    ├── Multimodal Ingestion Pipeline
 │    ├── 8-Stage Retrieval Sequence Diagram
 │    ├── Vector Search & Qdrant Payload Isolation
 │    └── Benchmark & Evaluation Metrics
 │
 └── Legal & Open Source (/license)
      ├── MIT License
      └── Privacy Statement (100% Telemetry-Free Guarantee)
```

---

## 5. Landing Page Structure (Section-by-Section Specification)

### 5.1 Section 1: Hero Section
- **Purpose:** Make an immediate impact, state the UVP clearly, showcase the product UI visually, and convert visitors into downloads or GitHub stargazers.
- **Key Content:**
  - Badge: `✨ Version 1.0 Released — 100% Local & Open Source`
  - Main Headline: *"Learn Faster. Remember Everything. Own Your Data."*
  - Subtitle: *"Athenus is the private, local-first AI Learning Operating System. Transform video lectures into grounded conversations with instant timestamp citations, concept graphs, and spaced-repetition flashcards."*
  - Primary CTA: `Download for Desktop (v1.0)` [Auto-detects OS with fallback dropdown]
  - Secondary CTA: `View on GitHub ⭐️ [Stars]`
  - Hero Asset: High-resolution interactive mockup of the Athenus Tauri Desktop Shell showing the Video Player, Grounded RAG Chat turn, and clickable timestamp badge `[12:34 - 15:20]`.
- **Suggested Layout:** Center-aligned text block above a floating, glassmorphic desktop app mockup with glowing gold ambient backdrop highlights.
- **User Interaction:**
  - Hovering over timestamp badges in the screenshot triggers a glowing animation and seeking effect.
  - OS Download button automatically reflects the user's OS (`Windows`, `macOS`, or `Linux`).
- **Visual Hierarchy:** Level 1 Headline (H1) $\rightarrow$ Subtitle $\rightarrow$ Action Buttons $\rightarrow$ Interactive Hero Mockup.

---

### 5.2 Section 2: Proof & Trust Banner
- **Purpose:** Establish immediate technical credibility and open-source trust.
- **Key Content:**
  - Key Pillars: `100% Local & Offline`, `Zero Data Tracking`, `8-Stage Grounded RAG`, `Anki Export Ready`, `Tauri Native Desktop`.
  - Stats Counters: `50/50 Automated Tests Passing`, `8 Retrieval Stages`, `0 Server Uploads Needed`.
- **Suggested Layout:** Horizontal ticker / icon strip with subtle border separators.

---

### 5.3 Section 3: Core Feature Highlights (3-Column Grid)
- **Purpose:** Introduce the 6 core pillars of Athenus Knowledge OS.
- **Key Content:**
  1. **Multimodal Ingestion:** Upload MP4/MKV video or WAV audio. Local Faster-Whisper transcribes with word-level timestamps.
  2. **8-Stage Layered RAG:** Hybrid dense Qdrant vector search + sparse BM25 + Cross-Encoder reranking for pinpoint retrieval.
  3. **Timestamp Citations:** Every AI answer includes clickable `[MM:SS]` badges that instantly jump to the exact video frame.
  4. **Active Playback Context:** The AI reads spoken transcripts $\pm 30\text{s}$ around your current playback position in real time.
  5. **Knowledge Graph Engine:** Auto-extracts concept nodes and prerequisite relationships for visual knowledge mapping.
  6. **Active Recall Suite:** Generate structured chapter summaries, interactive quizzes, and Anki SM-2 flashcards in seconds.
- **Suggested Layout:** 3-column card grid with hover-elevating frosted glass cards, gold icon borders, and crisp descriptive copy.

---

### 5.4 Section 4: Interactive Product Showcase (Tabbed Desktop Sandbox)
- **Purpose:** Allow visitors to explore all 6 major views of the desktop app without downloading first.
- **Key Content:**
  - Interactive Tabs: `🎥 Video Workspace`, `💬 Grounded RAG Chat`, `🕸️ Knowledge Graph`, `🧠 Quiz Studio`, `🎴 Flashcard Grid`, `⚙️ Local Models`.
  - Preview Frame: High-definition interactive screenshot/video loop showing that specific view in action.
  - Side Description Panel: Detailed walkthrough of what happens in that view.
- **Suggested Layout:** Left/Top tab navigation with a large interactive preview container and feature breakdown sidebar.
- **User Interaction:** Clicking tabs smoothly cross-fades between interface views with micro-animations.

---

### 5.5 Section 5: Learning Workflows (3-Step Lifecycle)
- **Purpose:** Demystify how a user transforms raw video into long-term knowledge.
- **Key Content:**
  - **Step 1: Import & Index (Seconds):** Drag-and-drop lecture video. Local Faster-Whisper & BGE Small chunk and index content offline.
  - **Step 2: Converse & Explore (Minutes):** Ask complex questions. Get grounded answers with clickable timestamp citations and active playback context.
  - **Step 3: Master & Retain (Forever):** Traversal prerequisite concept maps, take auto-generated quizzes, and export SM-2 flashcards to Anki.
- **Suggested Layout:** Horizontal step connector diagram with step numbers (`01`, `02`, `03`), visual arrows, and animated progress connectors.

---

### 5.6 Section 6: Local-First & Privacy Sovereign Matrix
- **Purpose:** Contrast Athenus against cloud-based AI tools (ChatGPT, Notion AI, Cloud Notebooks).
- **Key Content:**
  - Feature Comparison Table:

| Feature | Athenus Knowledge OS | Cloud AI Chatbots | Traditional Video Players |
|---|---|---|---|
| **Data Privacy** | 🔒 100% Local (On-Device) | ❌ Cloud Upload Required | 🔒 Local |
| **Offline Capability** | ✅ Fully Functional Offline | ❌ Internet Required | ✅ Local |
| **Timestamp Citations** | ✅ Exact `[MM:SS]` Video Seeks | ❌ Vague Text Snippets | ❌ None |
| **Vector Isolation** | ✅ Strict Workspace Payload Filter | ❌ Shared Model Context | ❌ None |
| **Knowledge Graph** | ✅ Prerequisite Concept Map | ❌ None | ❌ None |
| **Anki SM-2 Export** | ✅ Native `.apkg` Export | ❌ Manual Copy-Paste | ❌ None |
| **Pricing** | 💚 100% Free & Open Source | 💳 $20/mo Subscription | 💚 Free |

- **Suggested Layout:** Clean, readable comparison table with checkmarks (`✅`), crossmarks (`❌`), and gold highlight column for Athenus.

---

### 5.7 Section 7: Deep Dive: 8-Stage Layered RAG Pipeline
- **Purpose:** Show technical depth and satisfy developers, researchers, and AI enthusiasts.
- **Key Content:**
  - Interactive Pipeline Diagram showing the 8 stages:
    1. Query Rewrite & HyDE Expansion
    2. Intent Detection
    3. Active Playback Context Injection ($\pm 30\text{s}$)
    4. Knowledge Graph Traversal
    5. Hybrid Search (Qdrant Dense + BM25 Sparse)
    6. Cross-Encoder Re-Ranking
    7. Context Compression
    8. Grounded Prompt Assembly
- **Suggested Layout:** Interactive horizontal flowchart / sequence diagram with clickable nodes revealing technical specs.

---

### 5.8 Section 8: Local & Cloud Model Ecosystem
- **Purpose:** Highlight local-first freedom while showing flexibility to use cloud providers when desired.
- **Key Content:**
  - Local Models: Pure local scanning via `OllamaModelScanner` (`Llama 3.1`, `Qwen 2.5`, `Mistral`, `DeepSeek-R1`).
  - Local ASR & Embeddings: Faster-Whisper (CPU/GPU) & SentenceTransformers (`bge-small-en-v1.5`).
  - Optional Cloud Providers: Groq, OpenRouter, Google Gemini, Anthropic Claude via provider-agnostic `AIServiceBus`.
- **Suggested Layout:** Grid of logos and model badges showcasing local vs cloud flexibility.

---

### 5.9 Section 9: Multi-Platform Download Matrix
- **Purpose:** Drive desktop binary installation.
- **Key Content:**
  - Platform Cards:
    - **Windows:** `.msi` Installer & Portable `.exe` (x64)
    - **macOS:** `.dmg` (Universal — Apple Silicon M1/M2/M3 & Intel)
    - **Linux:** `.AppImage` & `.deb` (x64)
    - **Developer:** `git clone` & `npx tauri dev` command snippet.
  - Release metadata: Version `v1.0.0`, SHA-256 checksum link, Release Notes link.
- **Suggested Layout:** 3-column download cards with OS icons, prominent download buttons, and quick command copy blocks.

---

### 5.10 Section 10: Open Source & Community Hub
- **Purpose:** Build open-source community around Athenus.
- **Key Content:**
  - GitHub Repository statistics (Stars, Forks, Issues, License: MIT).
  - Call to contribute code, report bugs, or request features.
  - Architectural documentation links (`ARCHITECTURE.md`, `AI_PIPELINE.md`, `WORKSPACE_ARCHITECTURE.md`).
- **Suggested Layout:** Dark code container with GitHub avatar grid, live star count, and contribution guidelines link.

---

### 5.11 Section 11: Frequently Asked Questions (FAQ)
- **Purpose:** Address user objections and technical questions.
- **Key Questions & Answers:**
  - *Q: Does Athenus require internet access?*  
    A: No. Athenus runs 100% offline using local Faster-Whisper, local embeddings, embedded Qdrant, and local Ollama LLMs.
  - *Q: What video formats are supported?*  
    A: MP4, MKV, AVI, MOV, WEBM, WAV, and MP3 audio files.
  - *Q: Do I need a high-end GPU?*  
    A: No. Athenus is optimized for CPU execution out of the box, with optional CUDA/GPU acceleration for faster Whisper transcription and vector embedding.
  - *Q: How does Anki flashcard export work?*  
    A: Athenus generates `.apkg` files natively using the SM-2 algorithm, which you can double-click to import directly into Anki.
  - *Q: Is my data safe?*  
    A: Yes. All transcripts, vector indexes, knowledge graphs, and chat histories remain strictly in your local SQLite database (`./data/athenus.db`). Zero telemetry is sent to any cloud server.
- **Suggested Layout:** Expandable accordion list with clear search filter.

---

### 5.12 Section 12: Call-to-Action (CTA Banner)
- **Purpose:** Final conversion push before footer.
- **Key Content:**
  - Headline: *"Transform How You Learn Today."*
  - Subtitle: *"Join thousands of students, researchers, and developers mastering complex topics with local AI."*
  - Buttons: `Download Athenus Free` | `Star on GitHub`
- **Suggested Layout:** High-contrast gradient card with gold CTA buttons and ambient particle glow.

---

### 5.13 Section 13: Global Footer
- **Purpose:** Secondary site navigation, legal links, and social connections.
- **Key Content:**
  - Brand identity statement & copyright (`© 2026 Famanias`).
  - Columns: Product (Features, Download, Roadmap), Architecture (RAG Engine, Graph, Local AI), Documentation (Getting Started, API, ADRs), Community (GitHub, Discord, License).
- **Suggested Layout:** Clean 4-column footer with muted typography and social icon links.

---

## 6. Content Copy Specifications

The frontend developer must implement the exact copy hierarchy defined below:

```text
HERO HEADLINE:
"Learn Faster. Remember Everything. Own Your Data."

HERO SUBTITLE:
"Athenus is the private, local-first AI Learning Operating System. Transform video lectures into interactive AI conversations with instant timestamp citations, concept graphs, and spaced-repetition flashcards."

HERO CTA PRIMARY:
"Download for Desktop (v1.0)"

HERO CTA SECONDARY:
"View Repository on GitHub"

SECTION 3 HEADLINE:
"Engineered for Deep Learning & Total Privacy"

SECTION 3 SUBTITLE:
"Everything you need to master video lectures, course series, and complex educational media in one unified desktop operating system."

SECTION 6 HEADLINE:
"Why Local-First Matters for Learning"

SECTION 6 SUBTITLE:
"Your study notes, video transcripts, and knowledge graphs belong to you—not a cloud vendor."

SECTION 7 HEADLINE:
"Under the Hood: 8-Stage Grounded Retrieval"

SECTION 7 SUBTITLE:
"Combining dense vector search, sparse keyword ranking, concept graph traversal, and active video playback context for zero-hallucination answers."
```

---

## 7. Visual & Brand Direction System

### 7.1 Design Philosophy: "Athena Academic Cyberpunk"
A modern, sleek dark mode theme that combines academic rigor with a high-performance desktop software aesthetic. Uses deep midnight navy backgrounds, rich surface containers, subtle glassmorphic borders, and striking gold/amber accents inspired by Athena's owl of wisdom.

### 7.2 Color Palette Tokens

```css
:root {
  /* Surface & Background Colors */
  --bg-background: #051424;         /* Deep Midnight Navy */
  --bg-surface-low: #0c1a2c;        /* Dark Surface Container Low */
  --bg-surface-container: #122238;  /* Card & Panel Surface */
  --bg-surface-high: #1a2d47;       /* Elevated Surface / Hover */

  /* Brand Accent Colors */
  --color-primary: #e9c349;         /* Athena Gold / Secondary Accent */
  --color-primary-hover: #f5d466;   /* Bright Gold Hover */
  --color-secondary: #38bdf8;       /* Tech Cyan Accent */
  --color-accent-green: #34d399;    /* Success / Active Status */

  /* Text & Typography Colors */
  --text-on-background: #f8fafc;    /* High Contrast White Text */
  --text-on-surface-variant: #94a3b8;/* Muted Subtitle Text */
  --text-disabled: #64748b;         /* Disabled / Subtle Text */

  /* Borders & Dividers */
  --border-outline-variant: #1e3a5f;/* Subtle Card Border */
  --border-active: #e9c349;         /* Focused Gold Border */
}
```

### 7.3 Typography Hierarchy
- **Display & Headlines:** `TT Carvist` / `Outfit` / `Geist Display` (Bold, tracking-tight, geometric academic feel).
- **Body Copy:** `Geist Sans` / `Inter` (Clean, highly readable, optimized for long technical descriptions).
- **Code, Timestamps & Badges:** `JetBrains Mono` (Monospaced, crisp timestamp display `[12:34]`).

### 7.4 Iconography & Illustration Style
- **Icons:** Lucide Icons (`lucide-react`) rendered with thin 1.5px stroke width in `--color-primary` or `--text-on-surface-variant`.
- **Illustrations:** Sleek vector schematics, glowing node graphs, frosted glass UI window mockups with dark drop-shadows (`box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5)`).

### 7.5 Motion & Micro-Animations
- **Scroll Reveal:** Smooth fade-in + slide-up transition (`transform: translateY(20px)` $\rightarrow$ `0px`, `duration: 0.5s`).
- **Card Hover:** Subtle elevation (`transform: translateY(-4px)`) and border glow (`border-color: var(--color-primary)`).
- **Tab Swap:** Smooth cross-fade transition using Framer Motion `AnimatePresence`.

---

## 8. Interactive Components Specification

1. **Interactive Timestamp Badge Demo:**  
   Clicking a timestamp badge (`[04:15 - 05:30]`) in the live preview updates an embedded video mock player to 04:15 and displays the exact corresponding transcript segment in a highlighted sidebar.
2. **Interactive 8-Stage RAG Slider:**  
   A step-by-step interactive stepper allowing visitors to click through Stages 1 through 8 (Query Rewrite $\rightarrow$ Graph Traversal $\rightarrow$ Hybrid Search $\rightarrow$ Citation Assembly) and watch candidate chunks get scored and filtered in real time.
3. **Live Ollama Model Scanner Simulator:**  
   An interactive dropdown simulating how Athenus scans local `./data/models` to discover installed Ollama models (`llama3.1`, `qwen2.5`, `deepseek-r1`) without manual config.
4. **Interactive Flashcard Flip Component:**  
   A 3D flip card component demonstrating SM-2 Spaced Repetition (clicking "Show Answer" flips the card to reveal answer, keyframe image, and Anki rating buttons `Again`, `Hard`, `Good`, `Easy`).

---

## 9. Technical & Architecture Recommendations

### 9.1 Recommended Tech Stack
- **Framework:** Next.js 16 (App Router, SSG / Static Export configuration for hosting on GitHub Pages, Vercel, or Netlify).
- **Styling:** Vanilla CSS Modules or Tailwind CSS with standardized CSS Variables matching `globals.css` in Athenus.
- **Animation:** `framer-motion` for smooth UI transitions, layout animations, and tab swaps.
- **Icons:** `lucide-react`.
- **Code Block Highlighting:** `prismjs` or `shiki` with custom Athena dark theme.

### 9.2 Performance Target Requirements
- **Lighthouse Score:** 100 Performance, 100 Accessibility, 100 Best Practices, 100 SEO.
- **First Contentful Paint (FCP):** < 0.8s.
- **Total Blocking Time (TBT):** 0ms.
- **Image Optimization:** All screenshot assets converted to WebP / AVIF formats with responsive `srcset` and explicit `width`/`height` bounds.

### 9.3 SEO & Open Graph Requirements
- **Title Tag:** `Athenus — Local-First AI Learning Operating System`
- **Meta Description:** `Transform video lectures into interactive AI conversations with instant timestamp citations, concept graphs, and Anki flashcards. 100% local, offline, and private.`
- **Open Graph Image:** Custom 1200x630 social preview image featuring the Athenus logo, dark desktop UI mockup, and tagline.
- **JSON-LD Schema:** `SoftwareApplication` structured data specifying `operatingSystem: "Windows, macOS, Linux"`, `applicationCategory: "EducationalSoftware"`, `offers: { price: "0.00" }`.

---

## 10. Future Expansion Roadmap for Marketing Site

| Phase | Marketing Site Addition | Objective |
|---|---|---|
| **Phase 1 (Current)** | Core Landing Page & Download Hub | Product positioning, features, 8-stage RAG, desktop downloads. |
| **Phase 2** | Interactive Docs & Architecture Hub | Web version of `docs/` (`ARCHITECTURE.md`, `AI_PIPELINE.md`, `API.md`). |
| **Phase 3** | Agent Mode Showcase | Interactive workflow preview for Phase 6 Agentic Workflows & Multi-Step Planning. |
| **Phase 4** | Community Prompt & Workflow Gallery | User-submitted study workflows, custom prompt templates, and subject concept maps. |
| **Phase 5** | PDF & Multimodal Research Paper Hub | Showcase support for PDFs, eBooks, and GitHub repo indexing. |

---

## Conclusion & Hand-off Instructions

This document provides a complete, production-ready specification for the **Athenus Marketing Website**. A frontend developer can implement the site using Next.js 16 and Framer Motion by adhering strictly to the sitemap, section hierarchy, content copy specifications, visual design tokens, and performance guidelines outlined above.
