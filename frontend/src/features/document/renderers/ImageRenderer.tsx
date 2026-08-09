// ImageRenderer — displays raster and vector images (PNG, JPG/JPEG, WEBP,
// SVG) with fit-to-screen, zoom in/out, and pan controls.
//
// The image is loaded directly from the backend getMediaUrl() endpoint.
// Rendering is a native <img> tag — no canvas processing, so large
// high-resolution images are displayed losslessly and SVG renders as
// crisp vector artwork.
//
// Controls:
//   - Fit / Zoom In / Zoom Out (defaults to fit-to-screen)
//   - Wheel-zoom while holding Ctrl/⌘ (standard browser gesture)
//   - Click-and-drag panning when zoomed in

'use client';

import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import type { RendererProps } from '../types';

const MIN_ZOOM = 0.25;
const MAX_ZOOM = 4;
const ZOOM_STEP = 0.25;

export const ImageRenderer: React.FC<RendererProps> = ({ url, metadata }) => {
  const [zoom, setZoom] = useState<number>(1);
  const [fit, setFit] = useState<boolean>(true);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<boolean>(false);
  const dragStart = useRef<{ x: number; y: number } | null>(null);

  // Reset view state when a new image loads.
  useEffect(() => {
    setZoom(1);
    setFit(true);
    setPan({ x: 0, y: 0 });
    setDragging(false);
    dragStart.current = null;
  }, [url]);

  // While dragging, listen for pointermove on the window so the pointer can
  // travel outside the image bounds without losing the drag.
  useEffect(() => {
    if (!dragging) return;
    const handlePointerMove = (e: PointerEvent) => {
      if (!dragStart.current) return;
      const dx = e.clientX - dragStart.current.x;
      const dy = e.clientY - dragStart.current.y;
      setPan((p) => ({ x: p.x + dx, y: p.y + dy }));
      dragStart.current = { x: e.clientX, y: e.clientY };
    };
    const handlePointerUp = () => {
      setDragging(false);
      dragStart.current = null;
    };
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
    };
  }, [dragging]);

  const clampZoom = (z: number) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, z));

  const handleZoomIn = () => {
    setFit(false);
    setZoom((z) => clampZoom(z + ZOOM_STEP));
  };
  const handleZoomOut = () => {
    setFit(false);
    setZoom((z) => clampZoom(z - ZOOM_STEP));
  };
  const handleZoomFit = () => {
    setFit(true);
    setZoom(1);
    setPan({ x: 0, y: 0 });
  };

  const handleWheel = (e: React.WheelEvent) => {
    // Zoom only when the user holds Ctrl/Cmd (browser convention), so plain
    // scrolling can still scroll the surrounding page.
    if (!e.ctrlKey && !e.metaKey) return;
    e.preventDefault();
    setFit(false);
    setZoom((z) => clampZoom(z + (e.deltaY < 0 ? ZOOM_STEP : -ZOOM_STEP)));
  };

  const fileSize = useMemo(() => {
    const bytes = metadata.file_size_bytes;
    if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${bytes} bytes`;
  }, [metadata.file_size_bytes]);

  const handleImageLoad = () => {
    setFit(true);
    setZoom(1);
  };

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-surface-container-lowest">
      {/* Image canvas */}
      <div
        className="flex-1 relative overflow-hidden flex items-center justify-center"
        onWheel={handleWheel}
        onDoubleClick={handleZoomFit}
      >
        {/* Pan container — becomes draggable when zoomed in */}
        <div
          className={`select-none ${dragging ? 'cursor-grabbing' : zoom > 1 ? 'cursor-grab' : 'cursor-default'}`}
          style={{ transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}
          onPointerDown={(e) => {
            if (zoom > 1) {
              e.preventDefault();
              setDragging(true);
              dragStart.current = { x: e.clientX, y: e.clientY };
            }
          }}
        >
          <img
            src={url}
            alt={metadata.title || 'Document image'}
            onLoad={handleImageLoad}
            draggable={false}
            className={`max-w-full max-h-full object-contain ${fit ? 'w-auto h-auto' : ''}`}
            style={fit ? { maxWidth: '100%', maxHeight: '100%' } : { maxWidth: 'none', maxHeight: 'none' }}
          />
        </div>

        {/* Zoom badge */}
        <span className="absolute top-3 right-3 px-2 py-1 rounded bg-black/40 text-[10px] font-mono text-on-surface/80 border border-outline-variant/50">
          {Math.round(zoom * 100)}%
        </span>
      </div>

      {/* Image toolbar */}
      <div className="px-3 py-2 bg-surface-container-low border-t border-outline-variant text-[10px] font-mono text-on-surface-variant/60 flex flex-wrap justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-secondary shrink-0">🖼 Image</span>
          <span className="hidden md:inline truncate max-w-xs">{metadata.title}</span>
        </div>

        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={handleZoomFit} title="Fit to screen">
            Fit
          </Button>
          <Button variant="ghost" size="sm" onClick={handleZoomOut} title="Zoom out">
            −
          </Button>
          <span className="text-on-surface-variant px-1 w-10 text-center">
            {Math.round(zoom * 100)}%
          </span>
          <Button variant="ghost" size="sm" onClick={handleZoomIn} title="Zoom in">
            +
          </Button>
        </div>

        <span className="hidden sm:inline">{fileSize}</span>
      </div>
    </div>
  );
};
