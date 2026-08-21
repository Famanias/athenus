'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadMedia, MediaUploadDTO } from '@/services/mediaService';

export type AudioSourceMode = 'both' | 'mic' | 'system';

export interface UseAudioRecorderReturn {
  isRecording: boolean;
  recordingDuration: number;
  audioLevel: number;
  isUploading: boolean;
  sourceMode: AudioSourceMode;
  error: string | null;
  warning: string | null;
  setSourceMode: (mode: AudioSourceMode) => void;
  startRecording: (mode?: AudioSourceMode) => Promise<boolean>;
  stopRecording: () => Promise<Blob | null>;
  uploadRecordedAudio: (
    blob: Blob,
    workspaceId: string,
    title?: string
  ) => Promise<MediaUploadDTO | null>;
}

export function useAudioRecorder(): UseAudioRecorderReturn {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingDuration, setRecordingDuration] = useState(0);
  const [audioLevel, setAudioLevel] = useState(0);
  const [isUploading, setIsUploading] = useState(false);
  const [sourceMode, setSourceMode] = useState<AudioSourceMode>('both');
  const [error, setError] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const micStreamRef = useRef<MediaStream | null>(null);
  const sysStreamRef = useRef<MediaStream | null>(null);
  const combinedStreamRef = useRef<MediaStream | null>(null);
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const animFrameRef = useRef<number | null>(null);

  const cleanupAudioLevel = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current);
      animFrameRef.current = null;
    }
    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {});
      audioContextRef.current = null;
    }
    setAudioLevel(0);
  }, []);

  const stopAllStreamTracks = useCallback(() => {
    if (micStreamRef.current) {
      micStreamRef.current.getTracks().forEach((t) => t.stop());
      micStreamRef.current = null;
    }
    if (sysStreamRef.current) {
      sysStreamRef.current.getTracks().forEach((t) => t.stop());
      sysStreamRef.current = null;
    }
    if (combinedStreamRef.current) {
      combinedStreamRef.current.getTracks().forEach((t) => t.stop());
      combinedStreamRef.current = null;
    }
  }, []);

  const startRecording = useCallback(
    async (modeOverride?: AudioSourceMode): Promise<boolean> => {
      const mode = modeOverride || sourceMode;
      setError(null);
      setWarning(null);
      audioChunksRef.current = [];
      setRecordingDuration(0);

      try {
        if (!navigator.mediaDevices) {
          throw new Error('Audio recording is not supported in this browser environment.');
        }

        let micStream: MediaStream | null = null;
        let sysStream: MediaStream | null = null;

        // 1. Acquire Microphone Stream if mode requires it ('both' | 'mic')
        if (mode === 'both' || mode === 'mic') {
          if (!navigator.mediaDevices.getUserMedia) {
            throw new Error('Microphone access is not supported in this browser.');
          }
          try {
            micStream = await navigator.mediaDevices.getUserMedia({
              audio: {
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true,
              },
            });
            micStreamRef.current = micStream;
          } catch (micErr: unknown) {
            const msg =
              micErr instanceof Error
                ? micErr.message
                : 'Microphone permission was denied or is unavailable.';
            if (mode === 'mic') {
              throw new Error(msg);
            }
            // In 'both' mode, failure to get mic is critical
            throw new Error(`Microphone error: ${msg}`);
          }
        }

        // 2. Acquire System Audio Stream if mode requires it ('both' | 'system')
        if (mode === 'both' || mode === 'system') {
          if (!navigator.mediaDevices.getDisplayMedia) {
            if (mode === 'system') {
              throw new Error('System audio capture (getDisplayMedia) is not supported in this browser.');
            } else {
              setWarning('System audio capture is not supported; recording with microphone only.');
            }
          } else {
            try {
              const displayStream = await navigator.mediaDevices.getDisplayMedia({
                video: true,
                audio: true,
              });

              const audioTracks = displayStream.getAudioTracks();
              if (audioTracks.length > 0) {
                // Discard video tracks immediately to eliminate CPU & GPU rendering load
                displayStream.getVideoTracks().forEach((track) => track.stop());

                // Gracefully handle user ending share from browser bar
                audioTracks[0].onended = () => {
                  // Audio track ended naturally; recording continues with remaining streams
                };

                sysStream = displayStream;
                sysStreamRef.current = sysStream;
              } else {
                // User didn't check "Share audio"
                displayStream.getTracks().forEach((t) => t.stop());
                if (mode === 'system') {
                  throw new Error(
                    'No system audio was shared. Please check "Share audio" in the browser dialog.'
                  );
                } else {
                  setWarning(
                    'No system audio track selected. Recording will continue with microphone only.'
                  );
                }
              }
            } catch (sysErr: unknown) {
              if (mode === 'system') {
                const msg =
                  sysErr instanceof Error
                    ? sysErr.message
                    : 'System audio capture was cancelled or failed.';
                throw new Error(msg);
              } else {
                // Graceful fallback to mic only in 'both' mode
                setWarning('System audio capture was cancelled; recording with microphone only.');
              }
            }
          }
        }

        // Ensure we have at least one active audio stream
        if (!micStream && !sysStream) {
          throw new Error('No audio sources available to record.');
        }

        // 3. Setup Web Audio API Context & Mixing Graph
        const AudioContextClass =
          window.AudioContext ||
          (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioContextClass();
        audioContextRef.current = ctx;

        if (ctx.state === 'suspended') {
          await ctx.resume();
        }

        const dest = ctx.createMediaStreamDestination();
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        analyserRef.current = analyser;

        // Connect Microphone Stream if available
        if (micStream && micStream.getAudioTracks().length > 0) {
          const micSource = ctx.createMediaStreamSource(micStream);
          const micGain = ctx.createGain();
          micGain.gain.value = 1.0; // Vocal priority
          micSource.connect(micGain);
          micGain.connect(dest);
          micGain.connect(analyser);
        }

        // Connect System Audio Stream if available
        if (sysStream && sysStream.getAudioTracks().length > 0) {
          const sysSource = ctx.createMediaStreamSource(sysStream);
          const sysGain = ctx.createGain();
          // Balanced gain to prevent loud computer audio from drowning out vocal speech
          sysGain.gain.value = 0.85;
          sysSource.connect(sysGain);
          sysGain.connect(dest);
          sysGain.connect(analyser);
        }

        // Stream to record is the mixed destination stream
        const recordingStream = dest.stream;
        combinedStreamRef.current = recordingStream;

        // Setup real-time audio level analyser
        const dataArray = new Uint8Array(analyser.frequencyBinCount);
        const checkLevel = () => {
          if (!analyserRef.current) return;
          analyserRef.current.getByteFrequencyData(dataArray);
          let sum = 0;
          for (let i = 0; i < dataArray.length; i++) {
            sum += dataArray[i];
          }
          const avg = sum / dataArray.length;
          setAudioLevel(Math.min(1, avg / 128));
          animFrameRef.current = requestAnimationFrame(checkLevel);
        };
        checkLevel();

        // 4. Determine supported mimeType & initialize MediaRecorder
        let mimeType = 'audio/webm;codecs=opus';
        if (!MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
          if (MediaRecorder.isTypeSupported('audio/webm')) {
            mimeType = 'audio/webm';
          } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
            mimeType = 'audio/mp4';
          } else {
            mimeType = '';
          }
        }

        const recorder = mimeType
          ? new MediaRecorder(recordingStream, { mimeType })
          : new MediaRecorder(recordingStream);
        mediaRecorderRef.current = recorder;

        recorder.ondataavailable = (e) => {
          if (e.data && e.data.size > 0) {
            audioChunksRef.current.push(e.data);
          }
        };

        recorder.start(250); // flush every 250ms
        setIsRecording(true);

        timerRef.current = setInterval(() => {
          setRecordingDuration((prev) => prev + 1);
        }, 1000);

        return true;
      } catch (err: unknown) {
        const msg =
          err instanceof Error
            ? err.message
            : 'Failed to start audio recording. Check permissions and devices.';
        setError(msg);
        setIsRecording(false);
        cleanupAudioLevel();
        stopAllStreamTracks();
        return false;
      }
    },
    [cleanupAudioLevel, sourceMode, stopAllStreamTracks]
  );

  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        setIsRecording(false);
        cleanupAudioLevel();
        stopAllStreamTracks();
        resolve(null);
        return;
      }

      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }

      recorder.onstop = () => {
        const mime = recorder.mimeType || 'audio/webm';
        const blob = new Blob(audioChunksRef.current, { type: mime });
        audioChunksRef.current = [];

        stopAllStreamTracks();
        setIsRecording(false);
        cleanupAudioLevel();
        resolve(blob);
      };

      recorder.stop();
    });
  }, [cleanupAudioLevel, stopAllStreamTracks]);

  const uploadRecordedAudio = useCallback(
    async (
      blob: Blob,
      workspaceId: string,
      title = 'Live Audio Note'
    ): Promise<MediaUploadDTO | null> => {
      setIsUploading(true);
      setError(null);
      try {
        const ext = blob.type.includes('mp4') ? 'mp4' : 'webm';
        const filename = `recording_${Date.now()}.${ext}`;
        const file = new File([blob], filename, { type: blob.type });
        const res = await uploadMedia(file, workspaceId, title);
        return res;
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'Failed to upload recorded audio.';
        setError(msg);
        return null;
      } finally {
        setIsUploading(false);
      }
    },
    []
  );

  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      stopAllStreamTracks();
      cleanupAudioLevel();
    };
  }, [cleanupAudioLevel, stopAllStreamTracks]);

  return {
    isRecording,
    recordingDuration,
    audioLevel,
    isUploading,
    sourceMode,
    error,
    warning,
    setSourceMode,
    startRecording,
    stopRecording,
    uploadRecordedAudio,
  };
}
