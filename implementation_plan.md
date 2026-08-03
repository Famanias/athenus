# Implementation Plan — Per-Message Grounded Citations Architecture Fix

Fix the issue where previously retrieved citations persist across subsequent responses or display stale evidence from prior turns. Ensure that every assistant response maintains its own independent citation set grounded strictly in the retrieval results for that specific question.

---

## 🔍 Investigation Findings & Root Cause Analysis

### 1. How Citations Are Stored
- **Backend Database (`backend/app/infrastructure/db/models.py`)**: `ChatMessageTable` includes a `citations_json` column. Each assistant message row stores its own JSON array of citations (`citations_json`).
- **Frontend State (`frontend/src/store/chatSlice.ts`)**:
  - Individual messages inside `messages: ChatMessage[]` contain a `citations?: Citation[]` array.
  - The Zustand `chat` state also retains a top-level `evidence: Citation[]` array intended for the right-hand `RetrievedEvidencePanel`.

### 2. Why Stale Citations Persisted Across Responses (Root Causes Identified)
1. **Guarded State Update Bug in `useChat.ts`**:
   Line 89 of `useChat.ts` previously checked:
   ```typescript
   if (mappedCitations.length > 0) {
     addEvidence(mappedCitations);
   }
   ```
   If a follow-up response returned an empty citations array (or 0 retrieved chunks), `addEvidence` was skipped. Consequently, `state.chat.evidence` was never updated to `[]` and retained the stale citations from the previous question!
2. **Missing Active Message Citation Binding in UI**:
   The right-hand `RetrievedEvidencePanel` rendered `state.chat.evidence` globally rather than deriving evidence from the currently selected or active assistant message. When scrolling up to read earlier responses, the panel did not reflect the specific citations for that earlier turn.
3. **History Re-Hydration Gap**:
   `loadHistory()` populated `messages` from SQLite but did not update the side panel's active evidence to match the latest message in history.

---

## 🛠️ Proposed Architectural Fix

### 1. Always Update / Clear Evidence in `useChat.ts`
Remove the `mappedCitations.length > 0` guard so every turn (and history load) explicitly sets `addEvidence(mappedCitations)`. If a response returns 0 citations, `evidence` resets to `[]`.

### 2. Message Selection & Active Citation Binding (`ChatWorkspace.tsx`)
- Introduce `selectedMessageId` state in `ChatWorkspace.tsx` (defaulting to the latest assistant message).
- Allow users to click any assistant message card to inspect its specific evidence in `RetrievedEvidencePanel`.
- Dynamically derive the panel's active evidence:
  ```typescript
  const selectedMessage = messages.find((m) => m.id === selectedMessageId);
  const displayedEvidence = selectedMessage?.citations ?? (latestAssistantMsg?.citations || []);
  ```

### 3. Clear Evidence on Conversation Reset & Workspace Switch
Ensure `clearConversation()` resets `evidence: []` and clearing chat history in SQLite resets all citation states cleanly.

---

## Proposed Changes

### Frontend Chat Subsystem (`frontend/src/features/chat/`)

#### [MODIFY] [useChat.ts](file:///e:/repos/athenus/frontend/src/features/chat/useChat.ts)
- Remove `mappedCitations.length > 0` guard in `sendMessage` so `addEvidence(mappedCitations)` runs unconditionally.
- Update `loadHistory()` to set `addEvidence` to the latest assistant message's citations.

#### [MODIFY] [ChatWorkspace.tsx](file:///e:/repos/athenus/frontend/src/features/chat/ChatWorkspace.tsx)
- Add `selectedMessageId` state.
- Pass `selectedMessageId` and `onSelectMessage` to `ChatMessageItem`.
- Compute active message evidence and pass to `RetrievedEvidencePanel`.

#### [MODIFY] [ChatMessageItem.tsx](file:///e:/repos/athenus/frontend/src/features/chat/ChatMessageItem.tsx)
- Add `isSelected?: boolean` styling (e.g. subtle ring/border highlight).
- Add `onClick` selector handler on assistant messages.

---

## Verification Plan

### Automated Tests
1. **Frontend Type Check**:
   ```bash
   cd frontend
   npx tsc --noEmit
   ```
2. **Backend Pytest Suite**:
   ```bash
   cd backend
   python -m pytest
   ```

### Manual QA Testing Guide
1. **Per-Message Citation Isolation**:
   - Ask Question 1: *"Summarize Lecture 1"* $\rightarrow$ Observe citations for Lecture 1 (e.g., `02:15`, `05:42`).
   - Ask Question 2: *"What is gradient descent?"* $\rightarrow$ Observe NEW citations for Question 2 (e.g., `18:44`, `19:12`). Question 1 citations must NOT be repeated on Question 2.
2. **Message Selection in History**:
   - Click on Question 1's assistant bubble $\rightarrow$ Right panel updates to show Question 1's evidence.
   - Click on Question 2's assistant bubble $\rightarrow$ Right panel updates to show Question 2's evidence.
3. **Empty Citation Response Handling**:
   - Ask a general question (e.g. *"What is 2 + 2?"*) $\rightarrow$ Assistant responds without citations, right panel updates to show `0 Sources`.
