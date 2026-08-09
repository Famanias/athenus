import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getTranscript, getMediaUrl, BackendTranscriptSegmentDTO } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';
import { persistentVideoRef } from './PersistentMediaPlayer';

export interface TranscriptSegment {
  id: string;
  timestamp: string;
  start_seconds: number;
  end_seconds: number;
  speaker: string;
  text: string;
  isHighlighted?: boolean;
}

import { useJob } from '@/features/pipeline/useJob';

export function useVideo() {
  const {
    activeWorkspaceId,
    activeMediaId,
    setActiveMediaId,
    currentTime,
    setCurrentTime,
    targetSeekSeconds,
    setTargetSeekSeconds,
    playbackSpeed,
    setPlaybackSpeed,
  } = useAppStore();

  const { isComplete: isJobComplete } = useJob(activeMediaId);

  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number>(-1);
  const [loading, setLoading] = useState<boolean>(false);
  const [hasTranscript, setHasTranscript] = useState<boolean>(false);
  const [mediaSrc, setMediaSrc] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isPipActive, setIsPipActive] = useState<boolean>(false);

  // Persistent reference pointing to the single authoritative HTMLVideoElement in PersistentMediaPlayer
  const videoRef = persistentVideoRef;

  const mediaUrl = activeMediaId ? getMediaUrl(activeMediaId, activeWorkspaceId) : '';

  const fetchTranscript = useCallback(async () => {
    if (!activeMediaId) {
      setSegments([]);
      setHasTranscript(false);
      setMediaSrc('');
      return;
    }

    setMediaSrc(mediaUrl);

    try {
      setLoading(true);
      const data = await getTranscript(activeMediaId, activeWorkspaceId);
      if (data && data.segments && data.segments.length > 0) {
        const mapped: TranscriptSegment[] = data.segments.map((seg: BackendTranscriptSegmentDTO, idx: number) => ({
          id: `seg_${idx}`,
          timestamp: formatSecondsToTimestamp(seg.start_time),
          start_seconds: seg.start_time,
          end_seconds: seg.end_time,
          speaker: seg.speaker || 'Lecturer',
          text: seg.text,
        }));
        setSegments(mapped);
        setHasTranscript(true);
      } else {
        setSegments([]);
        setHasTranscript(false);
      }
    } catch (_err) {
      // If asset does not belong to this workspace, reset state
      setSegments([]);
      setHasTranscript(false);
      setMediaSrc('');
      setActiveMediaId(null);
    } finally {
      setLoading(false);
    }
  }, [activeMediaId, activeWorkspaceId, mediaUrl, setActiveMediaId]);

  // Fetch transcript segments on activeMediaId change
  useEffect(() => {
    fetchTranscript();
  }, [fetchTranscript]);

  // State-driven transcript re-fetching on job completion transition
  useEffect(() => {
    if (isJobComplete) {
      fetchTranscript();
    }
  }, [isJobComplete, fetchTranscript]);

  // Listen for ingestion completion event to re-fetch transcript dynamically (fallback)
  useEffect(() => {
    const handleTranscriptReady = (e: Event) => {
      const customEvt = e as CustomEvent<{ mediaId?: string }>;
      if (!customEvt.detail?.mediaId || customEvt.detail.mediaId === activeMediaId) {
        fetchTranscript();
      }
    };

    if (typeof window !== 'undefined') {
      window.addEventListener('athenus:transcript-ready', handleTranscriptReady);
    }
    return () => {
      if (typeof window !== 'undefined') {
        window.removeEventListener('athenus:transcript-ready', handleTranscriptReady);
      }
    };
  }, [activeMediaId, fetchTranscript]);

  // Bind Picture-in-Picture lifecycle event listeners to the persistent video element
  useEffect(() => {
    const videoEl = videoRef.current;
    if (!videoEl) return;

    const handleEnterPip = () => {
      console.log('[useVideo] enterpictureinpicture event fired');
      setIsPipActive(true);
    };

    const handleLeavePip = () => {
      console.log('[useVideo] leavepictureinpicture event fired');
      setIsPipActive(false);
      if (videoEl && !videoEl.paused) {
        setIsPlaying(true);
      }
    };

    // Sync initial PiP state
    if (typeof document !== 'undefined' && document.pictureInPictureElement === videoEl) {
      setIsPipActive(true);
    }

    videoEl.addEventListener('enterpictureinpicture', handleEnterPip);
    videoEl.addEventListener('leavepictureinpicture', handleLeavePip);

    return () => {
      videoEl.removeEventListener('enterpictureinpicture', handleEnterPip);
      videoEl.removeEventListener('leavepictureinpicture', handleLeavePip);
    };
  }, [videoRef.current]);

  // Handle loaded metadata position restore
  const handleLoadedMetadata = () => {
    const videoEl = videoRef.current;
    if (!videoEl) return;

    videoEl.playbackRate = playbackSpeed;

    if (targetSeekSeconds === null && activeMediaId) {
      const savedPos = localStorage.getItem(`athenus_playback_pos_${activeMediaId}`);
      if (savedPos) {
        const secs = parseFloat(savedPos);
        if (!isNaN(secs) && secs > 0 && secs < videoEl.duration) {
          videoEl.currentTime = secs;
          setCurrentTime(formatSecondsToTimestamp(secs));
        }
      }
    }
  };

  // Synchronize activeSegmentIndex continuously whenever currentTime in store changes
  useEffect(() => {
    if (!currentTime || segments.length === 0) {
      if (activeSegmentIndex !== -1) setActiveSegmentIndex(-1);
      return;
    }

    // 1. Primary match: exact formatted timestamp string match (0ms delay, zero rounding error)
    const exactMatchIdx = segments.findIndex((seg) => seg.timestamp === currentTime);
    if (exactMatchIdx !== -1) {
      setActiveSegmentIndex(exactMatchIdx);
      return;
    }

    // 2. Fallback match: numeric range check for continuous playback between timestamp boundaries
    const parts = currentTime.split(':');
    let currentSecs = 0;
    if (parts.length === 2) {
      currentSecs = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
    } else if (parts.length === 3) {
      currentSecs = parseInt(parts[0], 10) * 3600 + parseInt(parts[1], 10) * 60 + parseInt(parts[2], 10);
    } else {
      currentSecs = parseFloat(currentTime) || 0;
    }

    const foundIdx = segments.findIndex(
      (seg) => currentSecs >= seg.start_seconds && currentSecs < seg.end_seconds
    );
    if (foundIdx !== -1) {
      setActiveSegmentIndex(foundIdx);
    } else if (segments.length > 0 && currentSecs >= segments[segments.length - 1].end_seconds) {
      setActiveSegmentIndex(segments.length - 1);
    }
  }, [currentTime, segments]);

  // Video time update event listener
  const handleTimeUpdate = () => {
    const videoEl = videoRef.current;
    if (!videoEl) return;
    const currentSecs = videoEl.currentTime;
    setCurrentTime(formatSecondsToTimestamp(currentSecs));

    if (activeMediaId && currentSecs > 0) {
      localStorage.setItem(`athenus_playback_pos_${activeMediaId}`, currentSecs.toString());
    }
  };

  const seekToSeconds = useCallback((seconds: number) => {
    setTargetSeekSeconds(seconds);
    const tsStr = formatSecondsToTimestamp(seconds);
    setCurrentTime(tsStr);

    if (segments.length > 0) {
      const foundIdx = segments.findIndex(
        (seg) => seconds >= seg.start_seconds && seconds < seg.end_seconds
      );
      if (foundIdx !== -1) {
        setActiveSegmentIndex(foundIdx);
      } else if (seconds >= segments[segments.length - 1].end_seconds) {
        setActiveSegmentIndex(segments.length - 1);
      }
    }

    setIsPlaying(true);
  }, [segments, setCurrentTime, setTargetSeekSeconds]);

  const seekToTimestamp = useCallback((timestampStr: string) => {
    const parts = timestampStr.split(':');
    if (parts.length === 2) {
      const seconds = parseInt(parts[0], 10) * 60 + parseInt(parts[1], 10);
      seekToSeconds(seconds);
    }
  }, [seekToSeconds]);

  const togglePlayPause = useCallback(() => {
    if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play().catch(() => { });
        setIsPlaying(true);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    }
  }, []);

  const togglePictureInPicture = useCallback(async () => {
    if (!videoRef.current) return;
    try {
      if (document.pictureInPictureElement === videoRef.current) {
        await document.exitPictureInPicture();
      } else if (document.pictureInPictureEnabled && !videoRef.current.disablePictureInPicture) {
        await videoRef.current.requestPictureInPicture();
      }
    } catch (err) {
      console.error('[useVideo] Picture-in-Picture error:', err);
    }
  }, []);

  const changePlaybackSpeed = useCallback((newSpeed: number) => {
    setPlaybackSpeed(newSpeed);
    if (videoRef.current) {
      videoRef.current.playbackRate = newSpeed;
    }
  }, [setPlaybackSpeed]);

  return {
    currentTime,
    segments,
    activeSegmentIndex,
    mediaSrc,
    videoRef,
    seekToTimestamp,
    seekToSeconds,
    togglePlayPause,
    togglePictureInPicture,
    isPlaying,
    setIsPlaying,
    isPipActive,
    loading,
    hasTranscript,
    refetchTranscript: fetchTranscript,
    playbackSpeed,
    changePlaybackSpeed,
    handleLoadedMetadata,
    handleTimeUpdate,
  };
}
