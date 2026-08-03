# ADR 0005: Zero DOM Re-Parenting Video Player & Per-Message Grounded Citations

## Context
1. **Picture-in-Picture (PiP) Player Duplication**: In modern web engines (Chromium, Edge), if an HTML5 `<video>` element enters Picture-in-Picture mode (`document.pictureInPictureElement`) and its parent DOM container is unmounted or moved via `createPortal`, the browser detaches the old DOM node to keep the floating PiP window playing. When React subsequently mounts a new player component, a second `<video>` element is instantiated on screen, resulting in two active video players and overlapping audio.
2. **Conversation vs Turn Grounded Citations**: Previously, grounded citations were handled at global conversation level, causing follow-up questions to retain stale evidence badges from prior turns.

## Decision
1. **Zero DOM Re-parenting Single Video Player**:
   - Mount `<VideoWorkspace />` persistently inside `DesktopShell.tsx` using CSS display `hidden` (`activeView === 'view-video' ? '' : 'hidden'`).
   - The HTML5 `<video>` element is instantiated once; its DOM parent node never changes, React never invokes `removeChild()`, and the browser never detaches the node during PiP tab switching.
2. **Per-Message Grounded Citations**:
   - Assistant citations are stored per-turn in SQLite `ChatMessageTable.citations_json` and React state `ChatMessage.citations`.
   - Clicking historical assistant message bubbles sets `selectedMessageId` in `ChatWorkspace.tsx`, dynamically updating `RetrievedEvidencePanel` to inspect that specific turn's evidence.
3. **Backend-Owned Context Extraction**:
   - Frontend passes `{ workspace_id, media_id, current_timestamp }`. Backend Stage 8 RAG prompt assembly queries SQLite `TranscriptSegmentTable` within a ±30s window and prepends playback context with provenance metadata.

## Rationale
- Prevents DOM node detachment and eliminates duplicate audio/video playback without introducing complex portal mounting side-effects or un-scoped background timers.
- Maintains strict evidence grounding per response turn for factual accuracy and observable AI engineering standards.

## Trade-offs
- Keeping `<VideoWorkspace />` mounted with CSS `hidden` consumes minimal React DOM memory, but eliminates component remount overhead, player re-instantiation, and PiP audio duplication completely.
