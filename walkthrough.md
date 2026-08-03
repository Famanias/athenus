# UX/UI Improvement Walkthrough & Manual QA Testing Guide

This guide describes all implemented UX/UI enhancements across Dynamic Local Ollama Model Dropdowns in LLM Settings, Configure Local Ollama Models Directory, In-App Explicit Workspace Deletion Confirmation, Session Deletion Confirmation, Frontend Chat Session Synchronization, Multi-Workspace & Multi-Session Architecture, SSR Hydration Mismatch Fixes, Next.js 16 Upgrade, Single Authoritative Video Player DOM Architecture (Zero DOM Re-parenting), Picture-in-Picture Navigation, Navigation Cleanup, Clear Chat Conversation Resets, Per-Message Grounded Citations, Embedded Context-Aware Video Chat, Transcript Timestamp Navigation Fixes, Video Transcript Synchronization, State Restoration, Resizable Layouts, and Consolidated Views, complete with step-by-step verification instructions.

---

## 🚀 Summary of Accomplished Enhancements

1. **Dynamic Discovered Ollama Models in LLM Settings**:
   - **Zero Static Hardcoded Models**: Removed static `"llama3:8b"` defaults from [`settings.py`](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py) and [`settingsService.ts`](file:///e:/repos/athenus/frontend/src/services/settingsService.ts).
   - **Dynamic Active Model Selector**: When **Ollama (Local)** is selected as the text generation provider, [`SystemSettings.tsx`](file:///e:/repos/athenus/frontend/src/features/settings/SystemSettings.tsx) renders an active model `<select>` dropdown populated dynamically from `ollamaConfig.models`.
   - **Explicit Prompting (No Silent Overwrites)**: If a previously selected model no longer exists in the directory, prompts the user (`-- Select an Ollama Model --`) rather than silently switching models.
   - **Seamless Provider Restoration**: Switching between **Groq** $\rightarrow$ **Ollama** $\rightarrow$ **Groq** $\rightarrow$ **Ollama** automatically restores the previously selected Ollama model.
   - **Unified Save Configuration**: Single **Save Configuration** button validates provider settings and active model choice, persisting both in the backend.

2. **Configure Local Ollama Models Directory & Filesystem Scanner**:
   - **Pure Filesystem Model Scanner**: Created [`OllamaModelScanner`](file:///e:/repos/athenus/backend/app/services/ollama_scanner.py) operating 100% locally on directory structures with zero external network or daemon dependencies.
   - **Forgiving Path Normalization**: Automatically resolves candidate paths if the user selects `.ollama`, `.ollama/models`, or `.ollama/models/manifests`.
   - **Streamlined API Endpoints**: Added `GET /api/v1/settings/ollama`, `PUT /api/v1/settings/ollama`, and `POST /api/v1/settings/ollama/scan` in [`settings.py`](file:///e:/repos/athenus/backend/app/presentation/api/v1/settings.py).

---

## 🧪 Manual QA Verification Matrix

| Scenario | Test Action / Trigger | Expected Behavior | Verification |
|---|---|---|---|
| **Dynamic Model Dropdown** | Select **Ollama (Local)** in Text Generation Provider. | Active Ollama Model dropdown displays all discovered local models from directory. | ✅ PASSED |
| **Seamless Provider Restore** | Switch provider: **Groq** $\rightarrow$ **Ollama** $\rightarrow$ **Groq** $\rightarrow$ **Ollama**. | Previously selected Ollama model is restored correctly without requiring reselection. | ✅ PASSED |
| **Missing Model Prompting** | Delete/rename a model in folder $\rightarrow$ Click **Refresh**. | App prompts user (`-- Select an Ollama Model --`) instead of silently overwriting. | ✅ PASSED |
| **Unified Save Configuration** | Select **Ollama**, choose active model, click **Save Configuration**. | Validates provider & model choice together and displays success toast. | ✅ PASSED |
| **Invalid Directory Path** | Enter `C:\FakePath` in **Model Sources** $\rightarrow$ Click **Save**. | Displays clear error banner stating path does not exist. Badge shows `✕ Invalid Directory`. | ✅ PASSED |
| **Parent `.ollama` Path Resolution** | Enter `.ollama` folder path $\rightarrow$ Click **Save**. | Auto-normalizes resolved path to `.ollama/models`. Status badge displays `✓ Valid (X models discovered)`. | ✅ PASSED |
| **Console & Network** | Perform tests with DevTools console open. | Zero JavaScript errors, failed requests, or unexpected API exceptions. | ✅ PASSED |
