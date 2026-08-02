# ML_DL_ARCHITECTURE.md

# Athenus Knowledge OS — Machine Learning & Deep Learning Technical Review Guide

---

## Executive Overview

**Athenus Knowledge OS** is an AI-native Knowledge Operating System designed to transform multimodal educational content (video, audio, keyframes, document text) into an interactive, searchable, explainable, and personalized learning companion.

This document serves as a comprehensive **Technical Reviewer Reference**, detailing every Subsystem, Machine Learning (ML) & Deep Learning (DL) technique, Mathematical formulation, Pre-trained Model, and Library utilized throughout the platform.

---

## Subsystem to ML/DL Mapping Matrix

| Subsystem | Primary Function | Machine Learning / Deep Learning Technique | Pre-trained Models & Engines | Core Libraries & Frameworks |
| :--- | :--- | :--- | :--- | :--- |
| **Speech Processing & Ingestion** | Video audio extraction & timestamped transcription | Automatic Speech Recognition (ASR), Log-Mel Spectrogram Conversion, Dynamic Time Warping (DTW) | `Faster-Whisper` (`whisper-base`) | `faster-whisper`, `FFmpeg`, `torch`, `ctranslate2` |
| **Representation Learning** | Semantic vector embedding generation | Bi-Encoder Transformer Embeddings, Metric Learning, Semantic Chunking | `bge-small-en-v1.5` (384-d) | `sentence-transformers`, `huggingface/transformers` |
| **Knowledge Indexing & Storage** | High-dimensional vector indexing & payloads | Hierarchical Navigable Small World (HNSW) Graph Indexing, Cosine Similarity | Embedded Vector Database | `qdrant-client` (Embedded Qdrant) |
| **Information Retrieval (IR)** | 8-Stage Hybrid Search & Re-ranking | Hybrid Search (Dense + BM25 Lexical), Cross-Encoder Passage Re-ranking, HyDE | `cross-encoder/ms-marco-MiniLM-L-6-v2` | `rank_bm25`, `qdrant-client`, `numpy` |
| **Generative LLM Reasoning** | Grounded explanation & citation generation | Autoregressive Decoder Transformers, In-Context Learning (ICL), Temperature/Top-$P$ Sampling | `Llama-3-8B-Instruct`, `Groq Llama-3-8192` | `ollama`, `openai` SDK |
| **Agentic AI Suite** | Task decomposition & factual agreement validation | Multi-Agent Coordination, Intent Classification, Groundedness Verification | Specialized Agent Sub-routines | Custom Python Agent Suite |
| **Knowledge Graph Engine** | Concept prerequisite extraction & graph traversal | Directed Acyclic Graph (DAG) Traversal, Entity & Relation Extraction | LLM-based Concept Extractor | Custom Network Graph Module |
| **Active Learning & Memory** | Flashcards, quizzes, and spaced repetition | SuperMemo-2 (SM-2) Cognitive Spaced Repetition Algorithm | Mathematical Cognitive Model | Custom Anki SM-2 Export Service |

---

## Detailed ML / DL Techniques & Theoretical Foundations

### 1. Automatic Speech Recognition (ASR) & Signal Processing
* **Technique**: Encoder-Decoder Speech Transformer with Cross-Attention.
* **Process**:
  1. **Audio Resampling**: Input video audio is extracted and resampled to 16kHz 16-bit mono PCM `.wav` format using `FFmpeg`.
  2. **Log-Mel Spectrogram**: Audio signals are transformed into an 80-channel log-Mel spectrogram using 25ms windows with a 10ms shift.
  3. **Acoustic Encoding & Decoding**: The Whisper encoder processes spectrogram frames; the decoder autoregressively emits text tokens with cross-attention over encoder output.
  4. **Word-Level Timestamp Alignment**: Dynamic Time Warping (DTW) over decoder cross-attention matrices extracts exact timestamp boundaries (`[start_time, end_time]`).
* **Libraries & Models**: `faster-whisper` backed by `ctranslate2` using FP16/INT8 quantization for CPU/GPU inference.

---

### 2. Dense Representation Learning & Vector Embeddings
* **Technique**: Dense Bi-Encoder Transformer Embeddings & Semantic Boundary Chunking.
* **Process**:
  1. **Semantic Chunking**: Transcript segments are grouped into ~250-word windows with sliding overlap to preserve context while respecting exact time bounds `[start_time, end_time]`.
  2. **Bi-Encoder Forward Pass**: Each text chunk $x$ is mapped to a 384-dimensional vector embedding $\vec{e} \in \mathbb{R}^{384}$ using `bge-small-en-v1.5`.
  3. **Cosine Metric**: Similarity between query vector $\vec{q}$ and document chunk vector $\vec{d}$ is computed via:
     $$\text{CosineSimilarity}(\vec{q}, \vec{d}) = \frac{\vec{q} \cdot \vec{d}}{\|\vec{q}\| \|\vec{d}\|}$$
* **Libraries & Models**: `sentence-transformers`, `bge-small-en-v1.5`, PyTorch.

---

### 3. 8-Stage Hybrid Information Retrieval (IR) Engine
* **Technique**: Multi-Stage Retrieval with Hybrid Search (Dense + Sparse) & Cross-Encoder Re-Ranking.
* **Process**:
  1. **Stage 1 — Query Rewriting & HyDE**: Generates a hypothetical response document to query vector space accurately.
  2. **Stage 2 — Intent Detection**: Classifies user query intent (timestamp lookup, concept explanation, quiz, or summary).
  3. **Stage 3 — Workspace Context Filtering**: Restricts search space via metadata payloads (`workspace_id`, `media_id`).
  4. **Stage 4 — Knowledge Graph Traversal**: Traverses prerequisite concept nodes for dependency context.
  5. **Stage 5 — Hybrid Search**:
     * **Dense Vector Search**: HNSW graph traversal in Embedded Qdrant using Cosine similarity.
     * **Sparse Lexical Search**: BM25 scoring ($k_1=1.5, b=0.75$) via `rank_bm25` for exact token matches.
     * **Reciprocal Rank Fusion (RRF)**: Merges dense and sparse rank lists:
       $$RRF(d) = \sum_{m \in M} \frac{1}{k + r_m(d)}$$
  6. **Stage 6 — Cross-Encoder Re-Ranking**: Candidate top-$K$ passages are jointly evaluated with the query using `cross-encoder/ms-marco-MiniLM-L-6-v2` to compute fine-grained relevance scores.
  7. **Stage 7 — Context Compression**: Eliminates redundant token spans while retaining exact timestamp bounds `[MM:SS - MM:SS]`.
  8. **Stage 8 — Grounded Prompt Assembly**: Assembles system instructions, evidence snippets, and timestamp citations for the LLM.

---

### 4. Generative LLM Reasoning & Retrieval-Augmented Generation (RAG)
* **Technique**: Autoregressive Decoder Transformers with In-Context Learning (ICL) and Grounding Constraints.
* **Process**:
  1. **Provider Abstraction**: Interacts with local models (`llama3:8b` via Ollama) or cloud providers (Groq, OpenRouter) through unified `AIServiceBus` interfaces (`ITextGenerationCapability`).
  2. **Grounded Prompt Construction**: System instructions mandate that the LLM answer *only* using provided context snippets and attach timestamp badges `[MM:SS - MM:SS]`.
  3. **Decoding Parameters**: Configurable temperature ($\sim 0.2$ for factual Q&A; $\sim 0.7$ for creative active recall generation) and Top-$P$ sampling.

---

### 5. Agentic AI Suite & Multi-Agent Coordination
* **Technique**: Specialized Agent Orchestration & Hallucination Verification.
* **Architecture**:
  * **AgentCoordinator**: Coordinates agent execution workflow.
  * **PlannerAgent**: Deconstructs complex educational queries into structured sub-tasks.
  * **RetrieverAgent**: Executes 8-Stage retrieval and handles fallback strategies.
  * **CitationValidatorAgent**: Verifies generated timestamp citations against raw transcript text to prevent hallucinated time ranges.

---

### 6. Knowledge Graph & Cognitive Memory Systems
* **Technique**: Directed Acyclic Graph (DAG) Relationship Mining & SuperMemo-2 (SM-2) Spaced Repetition.
* **Algorithms**:
  * **Knowledge Graph Engine**: Mines prerequisite relationships ($A \rightarrow B$) between concepts.
  * **SuperMemo-2 (SM-2)**: Computes review schedules for active recall flashcards:
    $$EF' = EF + (0.1 - (5 - q) \times (0.08 + (5 - q) \times 0.02))$$
    where $q \in [0, 5]$ is user quality response, $EF$ is Ease Factor (default $2.5$), and interval days increase exponentially.

---

## Technical Stack & Library Summary Table

| Library / Tool | Category | Technical Role in Athenus |
| :--- | :--- | :--- |
| `fastapi` | Web Framework | High-performance asynchronous REST & SSE endpoints |
| `faster-whisper` | ASR Model Runner | Fast C++ Whisper transcription with word timestamps |
| `ctranslate2` | Inference Engine | Optimized FP16/INT8 matrix multiplication for ASR |
| `sentence-transformers` | Neural Embeddings | Dense text vector embedding generation |
| `qdrant-client` | Vector Database | Embedded Qdrant vector database client |
| `rank_bm25` | Sparse IR | Lexical BM25 keyword retrieval engine |
| `sqlmodel` / `sqlite3` | Relational Metadata | Persistence store for workspaces and media metadata |
| `ollama` | Local LLM Engine | Offline local LLM inference runner (`llama3:8b`) |
| `pydantic` | Data Validation | Strict DTO schema validation across Bounded Contexts |
| `tauri` | Desktop Shell | Cross-platform Rust desktop wrapper around Next.js frontend |

---

## Technical Reviewer Q&A Cheat Sheet

### Q1: Why use Hybrid Search (Vector + BM25) instead of pure Vector Search?
> **Answer**: Vector embeddings excel at capturing broad semantic intent (e.g., matching "machine learning" with "statistical AI"), but struggle with exact technical terms, mathematical formulas, variable names, or acronyms (e.g., "sqrt(d_k)", "HNSW", "BGE"). Combining HNSW dense vector search with sparse BM25 keyword matching via Reciprocal Rank Fusion (RRF) delivers both high semantic recall and high lexical precision.

### Q2: Why use a Cross-Encoder after Bi-Encoder retrieval?
> **Answer**: Bi-encoders compute query and document embeddings independently so they can be pre-indexed into Qdrant for fast ANN search ($O(\log N)$). However, bi-encoders lose fine-grained token-to-token interactions. The Cross-Encoder takes the top 20 candidate passages and processes the Query and Passage *jointly* through full self-attention layers ($O(K \cdot L^2)$), yielding significantly higher re-ranking precision before passing evidence to the LLM.

### Q3: How does Athenus ensure local-first, offline execution?
> **Answer**: All core ML capabilities are backed by local models: `Faster-Whisper` for speech-to-text, `bge-small-en-v1.5` via `sentence-transformers` for embeddings, `Embedded Qdrant` stored on disk (`./data/qdrant`), `SQLite` for relational metadata, and `Ollama` (`llama3:8b`) for local LLM inference.

---

*Document maintained as part of the official Athenus Knowledge OS Documentation Suite ([docs/CONTEXT.md](file:///e:/repos/athenus/docs/CONTEXT.md), [docs/AI_PIPELINE.md](file:///e:/repos/athenus/docs/AI_PIPELINE.md)).*
