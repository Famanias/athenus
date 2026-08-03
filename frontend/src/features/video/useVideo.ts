import { useState, useEffect, useRef, useCallback } from 'react';
import { useAppStore } from '@/store/useAppStore';
import { getTranscript, getMediaUrl, BackendTranscriptSegmentDTO } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';

export interface TranscriptSegment {
  id: string;
  timestamp: string;
  start_seconds: number;
  end_seconds: number;
  speaker: string;
  text: string;
  isHighlighted?: boolean;
}

export function useVideo() {
  const {
    activeMediaId,
    currentTime,
    setCurrentTime,
    targetSeekSeconds,
    setTargetSeekSeconds,
    playbackSpeed,
    setPlaybackSpeed,
  } = useAppStore();

  const [segments, setSegments] = useState<TranscriptSegment[]>([]);
  const [activeSegmentIndex, setActiveSegmentIndex] = useState<number>(-1);
  const [loading, setLoading] = useState<boolean>(false);
  const [hasTranscript, setHasTranscript] = useState<boolean>(false);
  const [mediaSrc, setMediaSrc] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isPipActive, setIsPipActive] = useState<boolean>(false);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const mediaUrl = activeMediaId ? getMediaUrl(activeMediaId) : '';

  // Stage 1 Diagnostic & Stage 2 Unmount Cleanup Lifecycle
  useEffect(() => {
    const instanceId = Math.random().toString(36).substring(2, 7);
    if (typeof window !== 'undefined') {
      const vCount = document.getElementsByTagName('video').length;
      console.log(`[useVideo:#${instanceId}] Mounted hook instance | Total DOM Video Count: ${vCount}`);
    }

    return () => {
      const videoEl = videoRef.current;
      console.log(`[useVideo:#${instanceId}] Unmounting hook instance...`);

      if (videoEl) {
        // Exit Picture-in-Picture if active on this video element
        if (typeof document !== 'undefined' && document.pictureInPictureElement === videoEl) {
          console.log(`[useVideo:#${instanceId}] Exiting Picture-in-Picture during unmount`);
          document.exitPictureInPicture().catch(() => {});
        }

        // Pause playback and release media decoders
        videoEl.pause();
        videoEl.removeAttribute('src');
        videoEl.load();
      }

      if (typeof window !== 'undefined') {
        const remainingCount = document.getElementsByTagName('video').length;
        console.log(`[useVideo:#${instanceId}] Cleaned up | Remaining DOM Video Count: ${remainingCount}`);
      }
    };
  }, []);

  // Fetch transcript segments on activeMediaId change
  useEffect(() => {
    if (!activeMediaId) {
      setSegments([]);
      setHasTranscript(false);
      setMediaSrc('');
      return;
    }

    setMediaSrc(mediaUrl);

    async function fetchTranscript() {
      try {
        setLoading(true);
        const data = await getTranscript(activeMediaId!);
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
        setSegments([]);
        setHasTranscript(false);
      } finally {
        setLoading(false);
      }
    }

    fetchTranscript();
  }, [activeMediaId, mediaUrl]);

  // Handle external target seek (e.g. grounded citation click)
  useEffect(() => {
    if (targetSeekSeconds !== null && videoRef.current) {
      videoRef.current.currentTime = targetSeekSeconds;
      videoRef.current.play().catch(() => {});
      setCurrentTime(formatSecondsToTimestamp(targetSeekSeconds));
      setTargetSeekSeconds(null);
    }
  }, [targetSeekSeconds, setTargetSeekSeconds, setCurrentTime]);

  // Update playback rate when store playbackSpeed changes
  useEffect(() => {
    if (videoRef.current) {
      videoRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  // Bind Picture-in-Picture lifecycle event listeners
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

    videoEl.addEventListener('enterpictureinpicture', handleEnterPip);
    videoEl.addEventListener('leavepictureinpicture', handleLeavePip);

    return () => {
      videoEl.removeEventListener('enterpictureinpicture', handleEnterPip);
      videoEl.removeEventListener('leavepictureinpicture', handleLeavePip);
    };
  }, [videoRef.current]);

  // Restore playback position on video loaded metadata if no external target seek
  const handleLoadedMetadata = () => {
    if (!videoRef.current) return;

    videoRef.current.playbackRate = playbackSpeed;

    if (targetSeekSeconds === null && activeMediaId) {
      const savedPos = localStorage.getItem(`athenus_playback_pos_${activeMediaId}`);
      if (savedPos) {
        const secs = parseFloat(savedPos);
        if (!isNaN(secs) && secs > 0 && secs < videoRef.current.duration) {
          videoRef.current.currentTime = secs;
          setCurrentTime(formatSecondsToTimestamp(secs));
        }
      }
    }
  };

  // Video time update event listener
  const handleTimeUpdate = () => {
    if (!videoRef.current) return;
    const currentSecs = videoRef.current.currentTime;
    setCurrentTime(formatSecondsToTimestamp(currentSecs));

    // Persist position in localStorage
    if (activeMediaId && currentSecs > 0) {
      localStorage.setItem(`athenus_playback_pos_${activeMediaId}`, currentSecs.toString());
    }

    // Determine active transcript segment
    if (segments.length > 0) {
      const foundIdx = segments.findIndex(
        (seg) => currentSecs >= seg.start_seconds && currentSecs < seg.end_seconds
      );
      if (foundIdx !== -1) {
        setActiveSegmentIndex(foundIdx);
      } else if (currentSecs >= segments[segments.length - 1].end_seconds) {
        setActiveSegmentIndex(segments.length - 1);
      }
    }
  };

  const seekToSeconds = useCallback((seconds: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      setCurrentTime(formatSecondsToTimestamp(seconds));
      videoRef.current.play().catch(() => {});
      setIsPlaying(true);
    }
  }, [setCurrentTime]);

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
        videoRef.current.play().catch(() => {});
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
    playbackSpeed,
    changePlaybackSpeed,
    handleLoadedMetadata,
    handleTimeUpdate,
  };
}
