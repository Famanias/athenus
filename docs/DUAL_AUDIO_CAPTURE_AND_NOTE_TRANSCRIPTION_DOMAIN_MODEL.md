# Dual-Source Audio Capture & Note Transcription Domain Model

This document defines the domain model, architecture, Web Audio API mixing topology, state machine, and error handling for capturing both microphone voice and computer/speaker audio (dual audio capture) within **Athenus Notes**.

---

## 1. Domain Entities & Value Objects

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Audio Capture Domain                               │
│                                                                             │
│  ┌───────────────────────┐         ┌─────────────────────────────────────┐  │
│  │    AudioSourceMode    │         │       AudioMixingTopology           │  │
│  │───────────────────────│         │─────────────────────────────────────│  │
│  │ • both (Mic + System) │         │ • AudioContext                      │  │
│  │ • mic (Microphone)    │ ──────► │ • micGainNode (1.0x)                │  │
│  │ • system (Speaker)    │         │ • sysGainNode (0.85x)               │  │
│  └───────────────────────┘         │ • masterGainNode / DynamicsCompressor│
│                                    │ • MediaStreamDestinationNode        │  │
│                                    └─────────────────────────────────────┘  │
│                                                       │                     │
│                                                       ▼                     │
│  ┌─────────────────────────────────┐       ┌─────────────────────────────┐  │
│  │    AudioCaptureSessionState     │       │        MediaRecorder        │  │
│  │─────────────────────────────────│ ◄──── │─────────────────────────────│  │
│  │ idle | requesting | capturing | │       │ • timeslice: 250ms          │  │
│  │ stopping | uploading | ready    │       │ • codec: audio/webm;opus    │  │
│  └─────────────────────────────────┘       └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1.1 `AudioSourceMode`
The capture strategy selected by the user:
- `both` (*Default*): Captures both the user's voice (via `getUserMedia`) and computer/speaker sound (via `getDisplayMedia` audio track).
- `mic`: Captures only the microphone input (standard dictation).
- `system`: Captures only computer audio (lecture, podcast, video, or meeting playback without voice input).

### 1.2 `AudioCaptureSessionState`
Finite state machine governing the recording lifecycle:
- `idle`: No active recording; resources released.
- `requesting_permissions`: Browser permission prompts active (`getUserMedia` and/or `getDisplayMedia`).
- `capturing`: Audio streams active, Web Audio graph routing samples, `MediaRecorder` collecting timeslices every 250ms, `AnalyserNode` driving UI audio level metering.
- `stopping`: Media streams stopping, remaining chunks flushed into `Blob`.
- `uploading`: Audio blob uploading to `POST /media/upload`.
- `transcribing`: Backend Faster-Whisper generating timestamped `transcript_segments` and `transcript_chunks`.
- `ready`: Transcript attached to note; note ready for AI synthesis.

---

## 2. Web Audio API Mixing Topology

When `AudioSourceMode === 'both'`, the browser captures two distinct `MediaStream` objects. They are mixed digitally in real-time using the Web Audio API without needing native external drivers.

```text
┌──────────────────────┐
│  getUserMedia()      │ ──► [ MediaStreamSourceNode ] ──► [ micGain: 1.0 ] ───┐
│  (Microphone)        │                                                       │
└──────────────────────┘                                                       ▼
                                                                        ┌───────────────┐
┌──────────────────────┐                                                │  Master Node  │
│  getDisplayMedia()   │ ──► [ MediaStreamSourceNode ] ──► [ sysGain: 0.85 ] ─►│  (Gain/Comp) │
│  (Speaker / System)  │                                                └───────┬───────┘
└──────────┬───────────┘                                                        │
           │                                                                    ▼
           │ Discard video track                                        ┌───────────────┐
           └─────────────────────► [ track.stop() ]                     │ AnalyserNode  │
                                                                        │ (Level Meter) │
                                                                        └───────┬───────┘
                                                                                │
                                                                                ▼
                                                                    [ MediaStreamDestination ]
                                                                                │
                                                                                ▼
                                                                        [ MediaRecorder ]
                                                                        (audio/webm;opus)
```

### 2.1 Gain Balancing & Ducking
- **Microphone Gain (`micGainNode`)**: Configured at `1.0` to preserve clear vocal capture.
- **System Audio Gain (`sysGainNode`)**: Scaled to `0.85` by default to prevent loud media or music from drowning out vocal dictation or clipping during mixing.
- **Dynamics Compressor / Master Gain**: Prevents digital clipping when both streams peak simultaneously.

### 2.2 Immediate Video Track Deallocation
`getDisplayMedia()` standard requires a video stream. To ensure minimal memory overhead and zero GPU video rendering load during notes recording:
1. Extract audio tracks: `const audioTrack = displayStream.getAudioTracks()[0];`
2. Immediately terminate video tracks: `displayStream.getVideoTracks().forEach(track => track.stop());`
3. Bind audio track to Web Audio graph.

---

## 3. Resilience & Fallback Behavior

| Scenario | Behavior | User Experience |
|---|---|---|
| **System audio prompt cancelled** | If the user cancels the `getDisplayMedia` screen-share dialog while in `both` mode, the recorder falls back immediately to `mic` mode. | Toast notification: *"System audio capture was cancelled; recording with microphone only."* |
| **No system audio checked** | If the user selects a screen/window without checking "Share system audio" checkbox, `displayStream.getAudioTracks()` will be empty. | Graceful fallback to microphone only + toast notification. |
| **User stops screen share during recording** | `audioTrack.onended` triggers. | Active recording does not crash; microphone continues capturing until the user clicks Stop. |
| **Unsupported browser mimeType** | Probe `audio/webm;codecs=opus` → `audio/webm` → `audio/mp4`. | Automatic selection of best supported audio codec. |

---

## 4. Component Architecture & UI Integration

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                             NotesWorkspace                                  │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ NoteTopToolbar (View Mode: Editor | Sections | Transcript)            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ Note Content Area (Manual Editor / Structured Sections / Transcript)  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │ NoteBottomBar                                                         │  │
│  │                                                                       │  │
│  │  ┌───────────────────────┐  ┌─────────────┐  ┌─────────────────────┐  │  │
│  │  │ [🎙️+🔊 All Audio ▼]    │  │ ⏺ Record   │  │ ⚡ Generate Notes    │  │  │
│  │  │  • Mic + Speaker      │  │ (00:14)     │  │ (AI synthesis)      │  │  │
│  │  │  • Mic Only           │  │ [Live Wave] │  │                     │  │  │
│  │  │  • Speaker Only       │  └─────────────┘  └─────────────────────┘  │  │
│  │  └───────────────────────┘                                            │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 UI Controls in `NoteBottomBar.tsx`
- **Source Mode Selector**: A compact pill selector dropdown next to the Record button offering:
  1. `🎙️+🔊 Mic & Speaker` *(All Audio / Meeting & Lecture Mode)*
  2. `🎙️ Mic Only` *(Dictation)*
  3. `🔊 Speaker Only` *(System / Media)*
- **Live Visual Meter**: Real-time pulsing glow driven by `audioLevel` computed from `AnalyserNode.getByteFrequencyData()`.
- **Duration Badge**: Shows elapsed recording time formatted as `MM:SS`.

---

## 5. End-to-End Execution Flow

```text
1. User selects "Mic & Speaker" mode (default) in NoteBottomBar.
2. User clicks "Record" button.
3. useAudioRecorder:
   a. Requests microphone via getUserMedia({ audio: true }).
   b. Requests system audio via getDisplayMedia({ video: true, audio: true }).
   c. Discards video tracks immediately.
   d. Connects both audio tracks to AudioContext gain nodes.
   e. Passes destination stream to MediaRecorder (flushing every 250ms).
4. User speaks or plays computer video/audio.
5. User clicks "Stop".
6. MediaRecorder flushes complete WebM/Opus Blob.
7. Blob is uploaded via mediaService.uploadMedia(blob, workspaceId, noteTitle).
8. FastAPI backend receives audio -> Faster-Whisper transcribes into timestamped chunks.
9. NotesWorkspace attaches media_id to active note and polls transcript.
10. Transcript appears in Transcript tab; user clicks "Generate Notes" to create structured study notes with clickable [MM:SS] citations.
```
