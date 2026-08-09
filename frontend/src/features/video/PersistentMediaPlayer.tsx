'use client';

import React, { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { useAppStore } from '@/store/useAppStore';
import { getMediaUrl } from '@/services/mediaService';
import { formatSecondsToTimestamp } from '@/services/chatService';

// Module-level singleton reference to the single authoritative HTMLVideoElement.
export const persistentVideoRef = { current: null as HTMLVideoElement | null };

export const PersistentMediaPlayer: React.FC = () => {
  const videoElementRef = useRef<HTMLVideoElement | null>(null);
  const {
    activeView,
    activeMediaId,
    setCurrentTime,
    setTargetSeekSeconds,
    targetSeekSeconds,
    playbackSpeed,
  } = useAppStore();

  const [mediaSrc, setMediaSrc] = useState<string>('');
  const [targetSlot, setTargetSlot] = useState<HTMLElement | null>(null);
  const prevMediaIdRef = useRef<string | null>(activeMediaId);

  // Guards handleTimeUpdate against stale 'timeupdate' events that fire
  // between a seek being requested (targetSeekSeconds set) and the browser
  // actually completing that seek. Using a ref (not React state) here is
  // deliberate: refs are read synchronously with no render/commit delay.
  //
  // IMPORTANT: this guard must be armed in a useLayoutEffect (NOT a passive
  // useEffect). A passive effect runs after paint, leaving a window where the
  // still-playing video keeps emitting 'timeupdate' at the OLD position and
  // the guard is still false — so the stale event overwrites currentTime and
  // the transcript briefly re-highlights the previous segment. A layout
  // effect runs synchronously during the click's commit, before the browser
  // can deliver the next 'timeupdate', so the guard is armed before any stale
  // event can be processed.
  const pendingSeekRef = useRef(false);
  const lastSeekTargetRef = useRef<number | null>(null);

  // Sync internal ref with global module ref
  useEffect(() => {
    persistentVideoRef.current = videoElementRef.current;
  }, []);

  // Find target DOM slot in VideoWorkspace when activeView is view-video
  useEffect(() => {
    if (activeView === 'view-video' && typeof document !== 'undefined') {
      // Small timeout/raf to ensure slot div is mounted in DOM
      const timer = setTimeout(() => {
        const slotEl = document.getElementById('video-player-slot');
        setTargetSlot(slotEl);
      }, 0);
      return () => clearTimeout(timer);
    } else {
      setTargetSlot(null);
    }
  }, [activeView]);

  // Handle activeMediaId change (Video A -> Video B)
  useEffect(() => {
    const videoEl = videoElementRef.current;

    if (prevMediaIdRef.current !== activeMediaId) {
      // If switching from Video A to Video B while Video A is in PiP, exit PiP cleanly!
      if (videoEl && typeof document !== 'undefined' && document.pictureInPictureElement === videoEl) {
        console.log('[PersistentMediaPlayer] Switching media asset while in PiP. Exiting PiP cleanly.');
        document.exitPictureInPicture().catch(() => { });
      }

      prevMediaIdRef.current = activeMediaId;
    }

    if (activeMediaId) {
      setMediaSrc(getMediaUrl(activeMediaId));
    } else {
      setMediaSrc('');
      if (videoEl) {
        videoEl.pause();
        videoEl.removeAttribute('src');
        videoEl.load();
      }
    }
  }, [activeMediaId]);

  // Target seek handler (e.g. grounded citation click).
  useLayoutEffect(() => {
    if (targetSeekSeconds !== null && videoElementRef.current) {
      const videoEl = videoElementRef.current;

      if (Math.abs(videoEl.currentTime - targetSeekSeconds) < 0.05) {
        setCurrentTime(formatSecondsToTimestamp(targetSeekSeconds));
        setTargetSeekSeconds(null);
        return;
      }

      pendingSeekRef.current = true;
      lastSeekTargetRef.current = targetSeekSeconds;
      videoEl.currentTime = targetSeekSeconds;
      videoEl.play().catch(() => { });
      setCurrentTime(formatSecondsToTimestamp(targetSeekSeconds));
      setTargetSeekSeconds(null);
    }
  }, [targetSeekSeconds, setTargetSeekSeconds, setCurrentTime]);

  // Sync playback rate
  useEffect(() => {
    if (videoElementRef.current) {
      videoElementRef.current.playbackRate = playbackSpeed;
    }
  }, [playbackSpeed]);

  const handleLoadedMetadata = () => {
    const videoEl = videoElementRef.current;
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

  const handleSeeking = () => {
    pendingSeekRef.current = true;
  };

  const handleSeeked = () => {
    pendingSeekRef.current = false;
  };

  const handleTimeUpdate = () => {
    const videoEl = videoElementRef.current;
    if (!videoEl || videoEl.seeking || pendingSeekRef.current) {
      return;
    }
    const currentSecs = videoEl.currentTime;

    // Filter out trailing pre-seek timeupdate events until the video reaches the seek target
    if (lastSeekTargetRef.current !== null) {
      if (currentSecs < lastSeekTargetRef.current - 0.5) {
        return;
      }
      lastSeekTargetRef.current = null;
    }

    setCurrentTime(formatSecondsToTimestamp(currentSecs));

    if (activeMediaId && currentSecs > 0) {
      localStorage.setItem(`athenus_playback_pos_${activeMediaId}`, currentSecs.toString());
    }
  };

  const isVideoWorkspaceView = activeView === 'view-video';

  const playerContent = (
    <div className="w-full h-full flex items-center justify-center relative">
      <video
        ref={videoElementRef}
        src={mediaSrc || undefined}
        controls={isVideoWorkspaceView}
        onLoadedMetadata={handleLoadedMetadata}
        onTimeUpdate={handleTimeUpdate}
        onSeeking={handleSeeking}
        onSeeked={handleSeeked}
        className="w-full h-full object-contain rounded border border-outline-variant shadow-lg"
      />
    </div>
  );

  // If in VideoWorkspace view: portal into target slot when ready (never render off-screen fallback in VideoWorkspace view)
  if (isVideoWorkspaceView) {
    if (targetSlot) {
      return createPortal(playerContent, targetSlot);
    }
    return null;
  }

  // Otherwise (browsing other views), keep mounted in off-screen container for background / PiP playback
  return (
    <div className="fixed bottom-0 right-0 w-1 h-1 opacity-0 pointer-events-none overflow-hidden z-0">
      {playerContent}
    </div>
  );
};