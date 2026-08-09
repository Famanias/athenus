# Manual QA Test Results — v5.1–5.4

**Summary:** 3 Passed / 9 Failed

---

## 5.1 Multi-Format Document Ingestion Tests

| # | Test Case | Result | Notes |
|---|-----------|--------|-------|
| 1 | Multi-Format Document Selection & Upload | ❌ FAILED | Document upload is not supported — only video uploads are currently available. |
| 2 | Document Ingestion Stage Stepper Progression | ❌ FAILED | Blocked — could not test since document upload is unavailable. |
| 3 | Oversized Document Safety Rejection | ❌ FAILED | Blocked — could not test since document upload is unavailable. |

---

## 5.2 RAG Chat Retrieval & Citation Tests

| # | Test Case | Result | Notes |
|---|-----------|--------|-------|
| 4 | Document-Aware Chat Query & Citation Badges | ❌ FAILED | Backend service unavailable. Test query `"this is a test. reply with hi"` returned: *"Unable to process... Please ensure the FastAPI backend is running at http://localhost:8000."* |
| 5 | PDF Page Jump & 2.5s Target Highlight | ❌ FAILED | Blocked by the same backend service unavailable error as Test 4. |
| 6 | Video Citation & Seek Regression Guarantee | ⚠️ FAILED on local model / PARTIAL PASS on cloud providers | Uploaded a video about LangChain, then asked the chat "what is LangChain?" using a cloud provider. AI response: *"LangChain is an open-source framework that helps develop applications using large language models or LLMs [00:00 - 01:53]. It provides a generic interface for LLMs, allowing developers to build and integrate applications into external data sets and workflows. LangChain also facilitates tools and ideas to customize the generated model, improve its accuracy, and provide relevant information [00:00 - 01:53]."* Citations returned: ⏱ 00:00–01:53, ⏱ 01:53–03:44, ⏱ 03:44–04:05 (Lecture Segments). **Partial pass:** clicking a citation redirects to the correct video, but not to the correct timestamp — e.g., clicking the 01:53–03:44 citation opens the video without seeking to 01:53. |

---

## 5.3 Workspace Modality & Library Integration Tests

| # | Test Case | Result | Notes |
|---|-----------|--------|-------|
| 7 | Library Grid Asset Modality Indicators | ❌ FAILED | A video item is incorrectly displayed with a document badge. |
| 8 | Dual-Modality Workspace Switching | ❌ FAILED | Blocked — cannot test since document upload is unavailable. |
| 9 | Workspace Switch State Isolation | ✅ PASSED | Creating a new workspace correctly produces an empty workspace library. |

---

## 5.4 Asynchronous Lifecycle & System Resilience Tests

| # | Test Case | Result | Notes |
|---|-----------|--------|-------|
| 10 | Navigation & Refresh Recovery During Ingestion | ❌ FAILED | Could not fully test since document upload is unavailable. Video upload queuing works correctly — uploaded 2 videos simultaneously and both processed successfully. |
| 11 | Docker Backend Container Restart Resilience | ❌ FAILED | Chat query could not be started — returned the same "Backend Service Unavailable" error (tested with `"hi"`). |
| 12 | 21-Table System Factory Reset | ✅ PASSED | — |

---

## Important Note: Chat Backend / Ollama Issue

The **Backend Service Unavailable** error only occurs when using **Ollama's local model**. Cloud-based providers return correct responses without issue.

Additionally, only **`llama3:8b`** is available as a local model, despite `qwen3.6` and `gpt-oss:20b` also being configured/expected as available local models.

### Reproduction Examples

**Ollama (Local Daemon) — `llama3:8b`**
- Input: `hi`
- Output: `Backend Service Unavailable: Unable to process "hi". Please ensure the FastAPI backend is running at http://localhost:8000.`

**OpenRouter API (Cloud Universal) — `poolside/laguna-s-2.1:free`**
- Input: `hi`
- Output: `Hello! How can I assist you today?`

**Groq API (Cloud LPU) — `llama-3.1-8b-instant`**
- Input: `hi`
- Output: `Hello. I'm Athenus AI, your intelligent learning assistant. How can I assist you today?`

**Conclusion:** The issue appears isolated to the local Ollama integration/daemon rather than the FastAPI backend itself, since cloud providers route through the same backend successfully.
