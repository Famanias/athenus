# Chat State Persistence — Implementation Plan

## Root Cause

The problem is in [DesktopShell.tsx](file:///e:/repos/athenus/frontend/src/components/layout/DesktopShell.tsx), lines 37–45:

```tsx
{activeView === 'view-chat' && <ChatWorkspace />}
```

Each view is **conditionally rendered using `&&`**. When `activeView` is not `'view-chat'`, `<ChatWorkspace />` is **unmounted from the React tree entirely**. React destroys the component instance, tearing down all local `useState` hooks inside [useChat.ts](file:///e:/repos/athenus/frontend/src/features/chat/useChat.ts):

```ts
const [messages, setMessages] = useState<ChatMessage[]>(INITIAL_MESSAGES);
const [inputQuery, setInputQuery] = useState<string>('');
// ...
```

When you navigate back to Chat, React mounts a **fresh new component instance** — all accumulated messages, agent logs, and citations are gone.

> This affects **every** view that stores local `useState`, but Chat is the most noticeable since conversations are long-lived.

---

## Fix Strategy: Lift Chat State into Zustand (Slice Pattern)

Move chat state from local `useState` in `useChat.ts` into a dedicated **chat slice** within the Zustand store. The chat slice groups all related state and domain actions together, keeping the root store clean and making future enhancements (multiple conversations, long-term persistence) painless.

`useChat.ts` becomes a thin hook that reads from and writes to the store — all logic stays the same, only the state storage mechanism changes.

This is the minimal, correct solution:
- No layout restructuring required.
- No CSS `display: none` hacks.
- No structural risk to other views.
- Naturally extendable to add more slices later (e.g., `createVideoSlice`, `createIngestionSlice`).

---

## Proposed Changes

### [MODIFY] [useAppStore.ts](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts)

Adopt the **slice pattern**. The root store is composed from independent slices:

```ts
export const useAppStore = create<AppState>()(
  devtools(
    (...args) => ({
      ...createUISlice(...args),
      ...createChatSlice(...args),
      ...createVideoSlice(...args),
      ...createIngestionSlice(...args),
    })
  )
)
```

#### Chat slice shape

All chat-related state is grouped under a single `chat` key — no flat `chatMessages`, `chatEvidence`, etc. polluting the root store:

```ts
chat: {
  messages: ChatMessage[];       // initialized with welcome message
  citations: Citation[];
  logs: AgentLog[];
  input: string;
  isGenerating: boolean;
  backendUnavailable: boolean;
}
```

#### Domain actions (not setters)

Expose **business actions** instead of low-level setters:

- `addMessage(message)` — append a new message
- `replaceMessages(messages)` — replace the entire message list
- `clearConversation()` — reset messages, citations, and logs
- `addCitation(citation)` — append a citation
- `addLog(log)` — append an agent log
- `updateInput(input)` — update the input field
- `setGenerating(isGenerating)` — toggle generation state
- `setBackendUnavailable(unavailable)` — toggle backend status

#### Selectors (avoid full-state destructuring)

Components should select only the state they need:

```ts
// ✅ Good — only rerenders when chat.messages changes
const messages = useAppStore(state => state.chat.messages)

// ❌ Bad — rerenders on every store update
const { chatMessages, chatEvidence } = useAppStore()
```

### [MODIFY] [useChat.ts](file:///e:/repos/athenus/frontend/src/features/chat/useChat.ts)

- Remove all local `useState` calls.
- Read/write state through `useAppStore` selectors/actions.
- All async `sendMessage` logic stays untouched.

---

## What Will NOT Change

- `ChatWorkspace.tsx` — zero changes; it only uses the `useChat()` hook API.
- `DesktopShell.tsx` — zero changes; the `&&` conditional rendering pattern stays.
- `ChatMessage`, `Citation`, `AgentLog` type definitions — moved to a shared types file or kept in `useChat.ts`.

---

## Conversation Lifecycle Support

The slice includes actions to handle **New Chat** and **Clear Conversation** from day one:

| Action | Behavior |
|---|---|
| `clearConversation()` | Resets `messages`, `citations`, `logs` to initial state |
| `startConversation()` | Alias for `clearConversation()` + any future setup logic |

This avoids a refactor when these UI buttons are added.

---

## Future-Proofing: Multi-Conversation Support

The plan names things so migration to multiple conversations is straightforward:

**Today (single conversation):**
```ts
chat: {
  messages: [],
  citations: [],
  logs: [],
  input: "",
  isGenerating: false,
  backendUnavailable: false,
}
```

**Tomorrow (multiple conversations):**
```ts
chat: {
  conversations: Map<string, { messages, citations, logs }>,
  activeConversationId: string,
  input: "",
  isGenerating: false,
  backendUnavailable: false,
}
```

The `chat` group is already a natural boundary — just swap `messages` → `conversations[activeId].messages`.

---

## Open Questions

None — this is a straightforward state lift with no design ambiguity.