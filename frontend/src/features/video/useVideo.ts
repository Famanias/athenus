import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getMediaUrl } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';
import { persistentVideoRef } from './PersistentMediaPlayer';
import { refreshTranscriptQuery, useTranscriptQuery } from './transcriptQueries';
import {
  findActiveTranscriptSegment,
  mapTranscriptSegments,
  timestampToSeconds,
} from './transcriptSegments';
import type { TranscriptSegment } from './transcriptSegments';

export type { TranscriptSegment } from './transcriptSegments';

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
  const transcriptQuery = useTranscriptQuery(activeMediaId, activeWorkspaceId);

  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number>(-1);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isPipActive, setIsPipActive] = useState<boolean>(false);

  // Persistent reference pointing to the single authoritative HTMLVideoElement in PersistentMediaPlayer
  const videoRef = persistentVideoRef;

  const mediaUrl = activeMediaId ? getMediaUrl(activeMediaId, activeWorkspaceId) : '';
  const mediaSrc = mediaUrl;
  const loading = transcriptQuery.isLoading || transcriptQuery.isFetching;
  const segments = useMemo<TranscriptSegment[]>(
    () => mapTranscriptSegments(transcriptQuery.data?.segments || []),
    [transcriptQuery.data]
  );
  const hasTranscript = segments.length > 0;

  const fetchTranscript = useCallback(async () => {
    if (!activeMediaId) {
      return;
    }

    try {
      await refreshTranscriptQuery(activeMediaId, activeWorkspaceId);
    } catch (_err) {
      // If asset does not belong to this workspace, reset state
      setActiveMediaId(null);
    }
  }, [activeMediaId, activeWorkspaceId, setActiveMediaId]);

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
    const currentSecs = timestampToSeconds(currentTime);
    if (currentSecs === null) return;
    const foundIdx = findActiveTranscriptSegment(segments, currentSecs);
    if (foundIdx !== -1) {
      setActiveSegmentIndex(foundIdx);
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
      const foundIdx = findActiveTranscriptSegment(segments, seconds);
      if (foundIdx !== -1) {
        setActiveSegmentIndex(foundIdx);
      }
    }

    setIsPlaying(true);
  }, [segments, setCurrentTime, setTargetSeekSeconds]);

  const seekToTimestamp = useCallback((timestampStr: string) => {
    const seconds = timestampToSeconds(timestampStr);
    if (seconds !== null) seekToSeconds(seconds);
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
