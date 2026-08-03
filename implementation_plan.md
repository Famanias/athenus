# Implementation Plan — Picture-in-Picture & Multiple Video Playback Bug Fix

Diagnose and permanently resolve the issue where opening a video in Picture-in-Picture (PiP) mode and subsequently closing the PiP window or clicking "Back to Tab" causes multiple copies of the same video to play simultaneously with overlapping audio.

---

## User Review Required

> [!IMPORTANT]
> **Key Architecture Decisions & Enhancements Incorporated:**
> 1. **Stage 1 — Diagnostic Lifecycle Investigation**:
>    - Add diagnostic logging to `useVideo.ts` and `VideoWorkspace.tsx` to record:
>      - Count of `<video>` elements in the DOM (`document.getElementsByTagName('video').length`).
>      - Component mount/unmount timestamps.
>      - Active `videoRef` instance ID.
>      - PiP events (`enterpictureinpicture`, `leavepictureinpicture`).
>    - Verify the exact mechanism creating duplicate playback before applying code changes.
> 2. **Elimination of DOM Scanning Hacks**:
>    - Removed all arbitrary DOM-wide scanning (`document.querySelectorAll('video')`).
>    - Ensures clean lifecycle control so duplicate players cannot be instantiated by design.
> 3. **Seamless Playback State Preservation**:
>    - When exiting PiP or clicking "Back to Tab", preserve `currentTime`, `playbackRate`, `volume`, and `muted` state so transitions back to the workspace are smooth and uninterrupted.
> 4. **PiP Lifecycle Synchronization**:
>    - Bind `enterpictureinpicture` and `leavepictureinpicture` event listeners to sync `isPipActive` state and clean up media resources on unmount.

---

## Stage 1 — Diagnostic Investigation Workflow

```text
  Mount VideoWorkspace
        │
        ▼
  Log Component Instance ID & Video Element Count
        │
        ▼
  Trigger Picture-in-Picture (enterpictureinpicture)
        │
        ▼
  Log PiP Window Active & Reference Identity
        │
        ▼
  Close PiP / Click "Back to Tab" / Switch View Tab
        │
        ▼
  Log Unmount vs Remount Lifecycle & Active Audio Media Count
```

---

## Stage 2 — Proposed Changes

### Frontend Video Subsystem (`frontend/src/features/video/`)

#### [MODIFY] [useVideo.ts](file:///e:/repos/athenus/frontend/src/features/video/useVideo.ts)
- Add diagnostic lifecycle logging (`componentId`, mount/unmount timestamps, DOM video count).
- Add `isPipActive: boolean` state.
- Add unmount cleanup effect:
  - Check `document.pictureInPictureElement === videoEl`.
  - Exit PiP cleanly if active.
  - Save current `currentTime` and `playbackRate` to `localStorage` before pausing.
  - Remove `src` attribute and call `load()` to release browser media decoders.
- Bind `enterpictureinpicture` and `leavepictureinpicture` event listeners.

#### [MODIFY] [VideoWorkspace.tsx](file:///e:/repos/athenus/frontend/src/features/video/VideoWorkspace.tsx)
- Expose PiP toggle button in video control bar.
- Re-hydrate `currentTime` and `playbackRate` seamlessly when restoring from PiP.

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
1. **Stage 1 Diagnostic Logging Verification**:
   - Open browser developer console $\rightarrow$ navigate to **Video** workspace.
   - Observe log output: `[useVideo] Mounted instance #1 | DOM Video Count: 1`.
2. **PiP Entry & Exit**:
   - Click PiP button $\rightarrow$ observe log: `[useVideo] Enter PiP`.
   - Close PiP window $\rightarrow$ observe log: `[useVideo] Leave PiP`. Verify **single audio stream** and seamless playback continuation.
3. **"Back to Tab" Navigation**:
   - Enter PiP $\rightarrow$ switch to **Chat** tab $\rightarrow$ click "Back to Tab" in floating PiP window.
   - Observe log: `[useVideo] Unmount instance #1 | Exit PiP` followed by `[useVideo] Mounted instance #2`. Verify **zero duplicate audio**.
4. **Consecutive PiP Toggles**:
   - Enter and exit PiP mode 5 consecutive times $\rightarrow$ verify DOM video count remains 1 and no memory leaks occur.
