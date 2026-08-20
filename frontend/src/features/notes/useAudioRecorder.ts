'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { uploadMedia, MediaUploadDTO } from '@/services/mediaService';

export interface UseAudioRecorderReturn {
  isRecording: boolean;
  recordingDuration: number;
  audioLevel: number;
  isUploading: boolean;
  error: string | null;
  startRecording: () => Promise<boolean>;
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
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
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

  const startRecording = useCallback(async (): Promise<boolean> => {
    setError(null);
    audioChunksRef.current = [];
    setRecordingDuration(0);

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error('Audio recording is not supported in this browser.');
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      streamRef.current = stream;

      // Setup audio level analyser for live pulse
      try {
        const AudioContextClass = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext;
        const ctx = new AudioContextClass();
        const src = ctx.createMediaStreamSource(stream);
        const analyser = ctx.createAnalyser();
        analyser.fftSize = 256;
        src.connect(analyser);
        audioContextRef.current = ctx;
        analyserRef.current = analyser;

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
      } catch {
        // AudioContext level check is non-fatal
      }

      // Determine supported mimeType
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

      const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
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
      const msg = err instanceof Error ? err.message : 'Microphone permission denied or unavailable.';
      setError(msg);
      setIsRecording(false);
      cleanupAudioLevel();
      return false;
    }
  }, [cleanupAudioLevel]);

  const stopRecording = useCallback((): Promise<Blob | null> => {
    return new Promise((resolve) => {
      const recorder = mediaRecorderRef.current;
      if (!recorder || recorder.state === 'inactive') {
        setIsRecording(false);
        cleanupAudioLevel();
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

        // Stop media stream tracks
        if (streamRef.current) {
          streamRef.current.getTracks().forEach((t) => t.stop());
          streamRef.current = null;
        }

        setIsRecording(false);
        cleanupAudioLevel();
        resolve(blob);
      };

      recorder.stop();
    });
  }, [cleanupAudioLevel]);

  const uploadRecordedAudio = useCallback(
    async (
      blob: Blob,
      workspaceId: string,
      title = 'Live Voice Recording'
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
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      cleanupAudioLevel();
    };
  }, [cleanupAudioLevel]);

  return {
    isRecording,
    recordingDuration,
    audioLevel,
    isUploading,
    error,
    startRecording,
    stopRecording,
    uploadRecordedAudio,
  };
}
