# Implementation Plan — Comprehensive UX/UI Improvements & Video Learning Experience

Implement grounded citation navigation with auto-seek and auto-scroll, consolidate redundant transcript reader views, build a resizable video/transcript layout, implement real-time video transcript synchronization with scroll-lock resume, add playback controls/keyboard shortcuts, and implement complete video playback state restoration across app restarts.

---

## User Review Required

> [!IMPORTANT]
> **Key Design Decisions & Enhancements Incorporated:**
> 1. **Video Learning State Restoration**:
>    - Persists the following learning state parameters in `localStorage` across app restarts and tab closes:
>      - `activeMediaId`: Last watched video asset.
>      - `playbackSeconds`: Exact video timestamp resume position (e.g., `14:52`).
>      - `playbackSpeed`: User preferred playback rate (`0.75x`, `1x`, `1.25x`, `1.5x`, `2x`).
>      - `transcriptPanelWidth`: User preferred transcript panel width (e.g., `350px`).
>      - `isTranscriptCollapsed`: Transcript panel open/collapsed toggle state.
> 2. **Deep Grounded Citation Navigation**:
>    - Clicking a citation badge in Chat automatically sets `activeMediaId` (switches video if necessary), seeks `<video>` to exact timestamp seconds, auto-scrolls transcript panel to the matching segment, and highlights the card with a gold-bordered pulse animation.
> 3. **Consolidation of Redundant Transcript Reader (`view-transcript`)**:
>    - *Rationale*: The `VideoWorkspace` already embeds the complete, synchronized transcript alongside the video player. Consolidating into `VideoWorkspace` eliminates duplicate tab clutter while preserving all transcript features (search, copy, seek, timestamp badges).
> 4. **Resizable & Collapsible Video Workspace Layout**:
>    - Replaces static 60/40 grid with a resizable divider handle.
>    - Includes a one-click collapse/expand toggle button for distraction-free full video viewing.
> 5. **Smart Video Transcript Sync & Scroll-Lock Protection**:
>    - Tracks `timeupdate` on `<video>` to highlight current spoken segment.
>    - Auto-scrolls active segment into view.
>    - Detects manual user scroll in transcript container to temporarily pause auto-scrolling; presents a floating **"↓ Resume Sync"** button to re-engage auto-follow.
> 6. **Keyboard Shortcuts & Playback Speed Controls**:
>    - Add playback speed selector and keyboard shortcuts (`Space` = Play/Pause, `←/→` = ±5s, `M` = Mute, `F` = Fullscreen).

---

## State Restoration Matrix

| State Parameter | Storage Target | Default | Resumed Behavior |
|---|---|---|---|
| `activeMediaId` | `localStorage["athenus_active_media_id"]` | `null` | Automatically re-selects last watched video |
| `playbackSeconds` | `localStorage["athenus_playback_pos_<mediaId>"]` | `0` | Auto-seeks `<video>` to exact resume timestamp (e.g. `14:52`) |
| `playbackSpeed` | `localStorage["athenus_playback_speed"]` | `1.0` | Restores video `playbackRate` |
| `transcriptPanelWidth` | `localStorage["athenus_transcript_width"]` | `350` | Restores transcript panel width in pixels |
| `isTranscriptCollapsed` | `localStorage["athenus_transcript_collapsed"]` | `false` | Restores transcript panel open/collapsed state |

---

## Proposed Changes

### Navigation & Routing (`frontend/src/`)

#### [MODIFY] [navigation.ts](file:///e:/repos/athenus/frontend/src/config/navigation.ts)
- Remove `view-transcript` from `NAVIGATION_CONFIG` under Knowledge category.

#### [MODIFY] [AppLayout.tsx](file:///e:/repos/athenus/frontend/src/components/layout/AppLayout.tsx)
- Remove `view-transcript` rendering branch and route directly to `VideoWorkspace` (`view-video`).

---

### Store & Citation State (`frontend/src/store/`)

#### [MODIFY] [useAppStore.ts](file:///e:/repos/athenus/frontend/src/store/useAppStore.ts)
- Add state restoration properties:
  - `targetSeekSeconds: number | null`
  - `playbackSpeed: number`
  - `setTargetSeekSeconds(seconds: number | null)`
  - `setPlaybackSpeed(speed: number)`
  - Re-hydrate `activeMediaId` and settings from `localStorage` on initial mount.

#### [MODIFY] [ChatMessageItem.tsx](file:///e:/repos/athenus/frontend/src/features/chat/ChatMessageItem.tsx)
- Update `handleCitationClick`: set `activeMediaId` (if citation contains `mediaId`), set `targetSeekSeconds` (converted from `startTime`), set `currentTime`, and switch `activeView` to `view-video`.
- Add hover tooltip displaying citation passage preview text (`cit.text`).

---

### Video Workspace & Synchronization (`frontend/src/features/video/`)

#### [MODIFY] [useVideo.ts](file:///e:/repos/athenus/frontend/src/features/video/useVideo.ts)
- Update `useVideo` hook to:
  - Restore last playback position (`athenus_playback_pos_<mediaId>`) on load.
  - Continuously save `currentTime` seconds to `localStorage` during playback.
  - Track active transcript segment based on `videoRef.current.currentTime` range (`seg.start_time <= currentTime < seg.end_time`).
  - Listen to `targetSeekSeconds` store state and seek `<video>` automatically.

#### [MODIFY] [VideoWorkspace.tsx](file:///e:/repos/athenus/frontend/src/features/video/VideoWorkspace.tsx)
- Re-architect layout into resizable flex container with draggable resize handle and collapse button.
- Add `timeupdate` sync and smooth auto-scrolling to active transcript card.
- Add user scroll detection: display floating **"↓ Resume Auto-Scroll"** button when user scrolls manually.
- Add keyboard shortcuts event listener (`Space`, `←`, `→`, `M`, `F`).
- Add playback speed selector toolbar (`0.75x`, `1x`, `1.25x`, `1.5x`, `2x`).
- Add text search filter input inside transcript panel header.

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

### Manual Testing Guide (Step-by-Step UI Verification)
1. **State Restoration Across App Restarts**:
   - Play a video to `14:52` at `1.5x` speed with transcript width set to `400px`.
   - Refresh browser or restart application.
   - *Expected Result*: App resumes the exact video at `14:52`, at `1.5x` playback speed, with transcript panel width at `400px`.
2. **Grounded Citation Navigation**:
   - In **Chat**, click a citation badge (`⏱ 01:15`).
   - *Expected Result*: App navigates to **Video** workspace, seeks video to `01:15`, auto-scrolls transcript to matching segment, and highlights segment card in gold.
3. **Transcript Synchronization & Scroll Resume**:
   - Press play on video $\rightarrow$ transcript highlights in real-time and auto-scrolls.
   - Scroll transcript manually $\rightarrow$ auto-scroll pauses and **"↓ Resume Auto-Scroll"** button appears. Clicking it re-engages auto-follow.
4. **Resizable Layout & Keyboard Controls**:
   - Drag divider handle or press `Space` (Play/Pause) / `Left/Right` (±5s).
   - *Expected Result*: Panel resizes smoothly and video controls respond instantly to keyboard hotkeys.
