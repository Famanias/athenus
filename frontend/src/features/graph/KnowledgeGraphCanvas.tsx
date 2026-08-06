'use client';

import React, { useCallback, useMemo, useRef, useState } from 'react';
import { useGraph } from './useGraph';
import { Button } from '@/components/ui/Button';
import { useAppStore } from '@/store/useAppStore';
import { formatSecondsToTimestamp } from '@/services/chatService';

const RELATION_COLORS: Record<string, string> = {
  prerequisite_for: '#e9c349',
  related_to: '#6b8cff',
  expands_on: '#4ec9a8',
  contradicts: '#ef6a6a',
  example_of: '#c792ea',
};

export const KnowledgeGraphCanvas: React.FC = () => {
  const {
    loading,
    error,
    positionedNodes,
    positionedEdges,
    selectedNode,
    setSelectedNode,
    searchResults,
    searching,
    searchConcepts,
    clearSearchResults,
    computeShortestPath,
    clearPath,
    pathNodeIds,
    pathSourceId,
    pathTargetId,
    pathEdgeKeys,
    layoutWidth,
    layoutHeight,
    artifact,
    fetchGraph,
  } = useGraph();

  const { setActiveMediaId, setActiveView, setTargetSeekSeconds } = useAppStore();

  const [zoom, setZoom] = useState<number>(0.9);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<boolean>(false);
  const [dragStart, setDragStart] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const [searchQuery, setSearchQuery] = useState<string>('');

  const svgRef = useRef<SVGSVGElement | null>(null);

  const isPathNode = (id: string) => pathNodeIds.includes(id);
  const isPathEdge = (edgeId: string) => pathEdgeKeys.has(edgeId);
  const isPathSource = (id: string) => pathSourceId === id;
  const isPathTarget = (id: string) => pathTargetId === id;

  const nodeColor = useCallback(
    (nodeId: string) => {
      if (isPathSource(nodeId)) return '#e9c349';
      if (isPathTarget(nodeId)) return '#4ec9a8';
      if (isPathNode(nodeId)) return '#e9c349';
      return '#0f2a44';
    },
    [isPathSource, isPathTarget, isPathNode]
  );

  const handleWheel = (e: React.WheelEvent) => {
    const factor = e.deltaY > 0 ? 0.92 : 1.08;
    setZoom((z) => Math.min(2.5, Math.max(0.3, z * factor)));
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    if ((e.target as Element).closest('.graph-node')) return;
    setDragging(true);
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!dragging) return;
    setPan((prev) => ({
      x: prev.x + (e.clientX - dragStart.x),
      y: prev.y + (e.clientY - dragStart.y),
    }));
    setDragStart({ x: e.clientX, y: e.clientY });
  };

  const handleMouseUp = () => setDragging(false);

  const resetView = () => {
    setZoom(0.9);
    setPan({ x: 0, y: 0 });
  };

  const handleSearch = (q: string) => {
    setSearchQuery(q);
    searchConcepts(q);
  };

  const handleJumpToTimestamp = (mediaId: string | null, startTime: number | null) => {
    if (!mediaId || startTime == null) return;
    setActiveMediaId(mediaId);
    setTargetSeekSeconds(startTime);
    setActiveView('view-video');
  };

  const relationColor = (type: string) => RELATION_COLORS[type] || '#4b5870';

  const arrowMarker = useMemo(
    () => (
      <defs>
        <marker
          id="arrowhead"
          markerWidth="8"
          markerHeight="8"
          refX="7"
          refY="4"
          orient="auto"
        >
          <path d="M0,0 L8,4 L0,8 Z" fill="#4b5870" />
        </marker>
        <marker id="arrowhead-path" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
          <path d="M0,0 L8,4 L0,8 Z" fill="#e9c349" />
        </marker>
      </defs>
    ),
    []
  );

  return (
    <div className="flex-1 flex overflow-hidden w-full h-full">
      {/* Visual Graph Canvas Area */}
      <div className="flex-1 bg-surface-container-lowest border-r border-outline-variant flex flex-col relative">
        {/* Toolbar */}
        <div className="flex justify-between items-center px-4 py-3 border-b border-outline-variant z-10 bg-surface-container-lowest/90 backdrop-blur">
          <div>
            <h2 className="font-carvist text-xl font-bold text-on-surface">
              Concept Knowledge Graph Visualizer
            </h2>
            <p className="text-xs text-on-surface-variant">
              Interactive prerequisite dependencies across all workspace video lectures.
            </p>
          </div>
          <div className="flex items-center gap-2">
            {/* Search Box */}
            <div className="relative">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => handleSearch(e.target.value)}
                placeholder="Search concepts..."
                className="w-52 bg-surface-container border border-outline-variant rounded p-1.5 text-xs text-on-surface focus:border-secondary focus:outline-none font-mono"
              />
              {searching && (
                <span className="absolute right-2 top-1/2 -translate-y-1/2 text-[10px] text-on-surface-variant font-mono animate-pulse">
                  searching...
                </span>
              )}
              {!searching && searchResults.length > 0 && (
                <div className="absolute top-full mt-1 w-64 bg-surface-container-high border border-outline-variant rounded shadow-xl z-50 overflow-hidden">
                  {searchResults.map((r) => (
                    <button
                      key={r.id}
                      onClick={() => {
                        setSelectedNode(
                          positionedNodes.find((n) => n.id === r.id) || null
                        );
                        setSearchQuery('');
                        clearSearchResults();
                      }}
                      className="w-full text-left px-3 py-2 hover:bg-surface-container-highest text-xs text-on-surface flex justify-between gap-2 items-center"
                    >
                      <span className="truncate">{r.name}</span>
                      <span className="font-mono text-[10px] text-secondary shrink-0">
                        {Math.round(r.score * 100)}%
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <Button variant="secondary" size="sm" icon="sync" onClick={() => fetchGraph()}>
              Refresh
            </Button>
          </div>
        </div>

        {/* Artifact Lifecycle Status Bar */}
        <div className="px-4 py-2 border-b border-outline-variant bg-surface-container-low flex items-center gap-3 text-[11px] font-mono z-10">
          <span className="text-on-surface-variant">Artifact:</span>
          <span className={`font-bold uppercase ${artifact?.status === 'failed' ? 'text-rose-400' : artifact?.status === 'ready' ? 'text-emerald-400' : 'text-secondary'}`}>
            {artifact?.status || 'idle'}
          </span>
          <span className="text-on-surface-variant/60">progress {artifact?.progress ?? 0}%</span>
          {artifact?.message && (
            <span className="text-on-surface-variant truncate">{artifact.message}</span>
          )}
        </div>

        {/* Canvas */}
        <div
          className="flex-1 relative overflow-hidden bg-surface-container-lowest"
          onWheel={handleWheel}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Animated background rings */}
          <div className="absolute inset-0 opacity-10 pointer-events-none flex items-center justify-center">
            <div className="w-96 h-96 border border-secondary/40 rounded-full animate-[spin_40s_linear_infinite]" />
          </div>

          {loading && (
            <div className="absolute inset-0 z-20 flex items-center justify-center text-xs text-on-surface-variant font-mono">
              Analyzing concept relationships...
            </div>
          )}

          {!loading && error && (
            <div className="absolute inset-0 z-20 flex items-center justify-center">
              <div className="p-6 text-center space-y-3 max-w-sm bg-surface-container border border-outline-variant rounded-lg">
                <span className="text-4xl block">⚠️</span>
                <h4 className="font-bold text-sm text-on-surface">Graph Load Error</h4>
                <p className="text-xs text-on-surface-variant">{error}</p>
              </div>
            </div>
          )}

          {!loading && !error && positionedNodes.length === 0 && (
            <div className="absolute inset-0 z-20 flex items-center justify-center">
              <div className="p-8 text-center space-y-3 max-w-sm">
                <span className="text-4xl block">🕸</span>
                <h4 className="font-bold text-sm text-on-surface">No Concept Nodes Mapped</h4>
                <p className="text-xs text-on-surface-variant">
                  Upload and process video lectures to automatically extract concepts and construct your workspace knowledge graph.
                </p>
              </div>
            </div>
          )}

          {/* SVG Graph Layer */}
          {!loading && positionedNodes.length > 0 && (
            <svg
              ref={svgRef}
              className="absolute inset-0 w-full h-full cursor-grab active:cursor-grabbing"
              style={{ touchAction: 'none' }}
            >
              {arrowMarker}
              <g transform={`translate(${pan.x}, ${pan.y}) scale(${zoom})`}>
                {/* Edges */}
                {positionedEdges.map((edge) => {
                  const highlighted = isPathEdge(edge.id);
                  const color = highlighted ? '#e9c349' : relationColor(edge.relation_type);
                  return (
                    <g key={edge.id}>
                      <line
                        x1={edge.sourceX}
                        y1={edge.sourceY}
                        x2={edge.targetX}
                        y2={edge.targetY}
                        stroke={color}
                        strokeWidth={highlighted ? 3 : 1.2}
                        opacity={highlighted ? 0.95 : 0.5}
                        markerEnd={highlighted ? 'url(#arrowhead-path)' : 'url(#arrowhead)'}
                      />
                      <title>{`${edge.source} → ${edge.target} [${edge.relation_type}]`}</title>
                    </g>
                  );
                })}

                {/* Nodes */}
                {positionedNodes.map((node) => {
                  const isSelected = selectedNode?.id === node.id;
                  const isPath = isPathNode(node.id);
                  const r = isPath ? 26 : 20 + Math.min(node.degree * 3, 14);
                  return (
                    <g
                      key={node.id}
                      className="graph-node"
                      transform={`translate(${node.x}, ${node.y})`}
                      style={{ cursor: 'pointer' }}
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedNode(node);
                      }}
                    >
                      {isSelected && <circle r={r + 7} fill="none" stroke="#e9c349" strokeWidth={1.5} strokeDasharray="4 3" opacity={0.8} />}
                      <circle r={r} fill={nodeColor(node.id)} stroke={isSelected || isPath ? '#e9c349' : '#2a3d63'} strokeWidth={isSelected ? 2 : 1.2} />
                      {isPath && <circle r={4} fill="#e9c349" />}
                      <text
                        textAnchor="middle"
                        y={r + 13}
                        fontSize="11"
                        fontWeight={isSelected || isPath ? 700 : 500}
                        fill={isSelected || isPath ? '#e9c349' : '#9fb4d8'}
                        fontFamily="JetBrains Mono, monospace"
                      >
                        {node.name.length > 24 ? `${node.name.slice(0, 23)}…` : node.name}
                      </text>
                      <text textAnchor="middle" y={r - 4} fontSize="8" fill="#5d7298" fontFamily="JetBrains Mono, monospace">
                        {node.degree}°
                      </text>
                    </g>
                  );
                })}
              </g>
            </svg>
          )}

          {/* Zoom Controls */}
          {!loading && positionedNodes.length > 0 && (
            <div className="absolute bottom-4 right-4 z-30 flex flex-col gap-1.5">
              <button
                onClick={() => setZoom((z) => Math.min(2.5, z * 1.2))}
                className="w-8 h-8 bg-surface-container-high border border-outline-variant rounded text-on-surface hover:bg-surface-container-highest text-sm font-bold"
                title="Zoom in"
              >
                +
              </button>
              <button
                onClick={() => setZoom((z) => Math.max(0.3, z / 1.2))}
                className="w-8 h-8 bg-surface-container-high border border-outline-variant rounded text-on-surface hover:bg-surface-container-highest text-sm font-bold"
                title="Zoom out"
              >
                −
              </button>
              <button
                onClick={resetView}
                className="w-8 h-8 bg-surface-container-high border border-outline-variant rounded text-on-surface hover:bg-surface-container-highest text-[10px] font-mono"
                title="Reset view"
              >
                ⤢
              </button>
            </div>
          )}

          {/* Path Legend */}
          {pathNodeIds.length > 0 && (
            <div className="absolute bottom-4 left-4 z-30 px-3 py-2 bg-surface-container-high border border-outline-variant rounded text-[10px] font-mono space-y-1">
              <span className="text-secondary font-bold uppercase">Prerequisite Path Highlighted</span>
              <div className="flex gap-2 items-center">
                <span className="w-3 h-3 rounded-full bg-secondary inline-block" />
                <span className="text-on-surface-variant">Nodes ({pathNodeIds.length})</span>
                <button onClick={clearPath} className="text-rose-400 hover:underline ml-2">
                  Clear
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Right Node Inspector Panel */}
      <aside className="w-80 bg-surface-container-lowest border-l border-outline-variant flex flex-col p-6 space-y-4 shrink-0 overflow-y-auto custom-scrollbar">
        <span className="font-mono text-xs font-semibold text-secondary uppercase tracking-wider">
          Node Inspector
        </span>

        {selectedNode ? (
          <div className="space-y-4 text-xs">
            <div className="p-4 bg-surface-container-low border border-outline-variant rounded space-y-2">
              <div className="flex justify-between items-start">
                <span className="font-mono text-[10px] text-secondary uppercase font-semibold">
                  ACTIVE NODE
                </span>
                <span className={`font-mono text-[10px] uppercase ${selectedNode.status === 'failed' ? 'text-rose-400' : 'text-emerald-400'}`}>
                  {selectedNode.status}
                </span>
              </div>
              <h3 className="font-bold text-sm text-on-surface">
                {selectedNode.name}
              </h3>
              <p className="text-on-surface-variant leading-relaxed">
                {selectedNode.description || 'No description available.'}
              </p>
              <div className="flex gap-3 text-[10px] font-mono text-on-surface-variant/70 pt-1">
                <span>Degree: {selectedNode.degree}</span>
                <span>Videos: {selectedNode.video_count}</span>
              </div>
            </div>

            {/* Timestamp Citation Links */}
            <div className="space-y-2">
              <span className="font-mono text-[10px] text-on-surface-variant font-semibold uppercase block">
                Grounded Lecture Timestamps
              </span>
              {selectedNode.media_id && selectedNode.start_time != null ? (
                <button
                  onClick={() => handleJumpToTimestamp(selectedNode.media_id, selectedNode.start_time)}
                  className="w-full p-2 bg-surface-container rounded border border-outline-variant text-on-surface flex items-center justify-between gap-2 font-mono text-[11px] hover:border-secondary hover:bg-surface-container-high transition-colors"
                >
                  <span className="flex items-center gap-1.5">
                    <span>🎥</span>
                    <span className="truncate max-w-[120px]">{selectedNode.media_id}</span>
                  </span>
                  <span className="text-secondary font-bold">
                    {formatSecondsToTimestamp(selectedNode.start_time)} – {formatSecondsToTimestamp(selectedNode.end_time ?? selectedNode.start_time)}
                  </span>
                </button>
              ) : (
                <p className="text-[10px] text-on-surface-variant/60">
                  No timestamp grounding available.
                </p>
              )}
              {selectedNode.source_chunk_ids.length > 0 && (
                <p className="text-[10px] font-mono text-on-surface-variant/60">
                  {selectedNode.source_chunk_ids.length} source chunk(s): {selectedNode.source_chunk_ids.slice(0, 3).join(', ')}
                  {selectedNode.source_chunk_ids.length > 3 ? '…' : ''}
                </p>
              )}
            </div>

            {/* Prerequisite Path Tool */}
            <div className="space-y-2">
              <span className="font-mono text-[10px] text-on-surface-variant font-semibold uppercase block">
                Prerequisite Path
              </span>
              <div className="flex flex-col gap-1.5">
                <button
                  onClick={() => computeShortestPath(selectedNode.id, pathTargetId || selectedNode.id)}
                  className="p-2 bg-surface-container rounded border border-outline-variant text-on-surface font-mono text-[11px] hover:border-secondary hover:bg-surface-container-high transition-colors"
                >
                  Compute Path from {pathTargetId ? 'this → target' : 'this → next selected'}
                </button>
                {pathSourceId && pathTargetId && (
                  <button
                    onClick={clearPath}
                    className="p-2 bg-surface-container rounded border border-outline-variant text-rose-300 font-mono text-[11px] hover:border-rose-400 transition-colors"
                  >
                    Clear Path Highlight
                  </button>
                )}
                <p className="text-[10px] text-on-surface-variant/70 leading-relaxed">
                  Select a source node, then click <span className="text-secondary">"Compute Path"</span> to highlight the shortest dependency chain.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-on-surface-variant">
            Select a concept node to view prerequisite mappings and timestamp citations.
          </p>
        )}
      </aside>
    </div>
  );
};
