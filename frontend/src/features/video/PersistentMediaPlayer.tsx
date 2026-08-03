'use client';

import React, { useEffect, useRef, useState } from 'react';
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
        document.exitPictureInPicture().catch(() => {});
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

  // Target seek handler (e.g. grounded citation click)
  useEffect(() => {
    if (targetSeekSeconds !== null && videoElementRef.current) {
      videoElementRef.current.currentTime = targetSeekSeconds;
      videoElementRef.current.play().catch(() => {});
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

  const handleTimeUpdate = () => {
    const videoEl = videoElementRef.current;
    if (!videoEl) return;
    const currentSecs = videoEl.currentTime;
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
        className="w-full h-full object-contain rounded border border-outline-variant shadow-lg"
      />
    </div>
  );

  // If in VideoWorkspace view and target slot exists in DOM, portal the single player into the slot
  if (isVideoWorkspaceView && targetSlot) {
    return createPortal(playerContent, targetSlot);
  }

  // Otherwise, keep mounted in off-screen container so PiP window floating playback stays active
  return (
    <div className="fixed bottom-0 right-0 w-1 h-1 opacity-0 pointer-events-none overflow-hidden z-0">
      {playerContent}
    </div>
  );
};
