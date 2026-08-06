import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { apiClient } from '@/services/apiClient';
import { useAppStore } from '@/store/useAppStore';

export interface GraphConcept {
  id: string;
  workspace_id: string;
  name: string;
  description: string;
  status: string;
  media_id: string | null;
  source_chunk_ids: string[];
  start_time: number | null;
  end_time: number | null;
  degree: number;
  video_count: number;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  relation_type: string;
  weight: number;
  media_id: string | null;
}

export interface ArtifactLifecycle {
  status: string;
  progress: number;
  message: string | null;
  error_message: string | null;
  updated_at: string | null;
}

export interface GraphTopology {
  workspace_id: string;
  artifact: ArtifactLifecycle | null;
  nodes: GraphConcept[];
  edges: GraphEdge[];
}

export interface SearchResult {
  id: string;
  name: string;
  description: string;
  score: number;
  media_id: string | null;
  start_time: number | null;
  end_time: number | null;
}

export interface PositionedNode extends GraphConcept {
  x: number;
  y: number;
}

export interface PositionedEdge extends GraphEdge {
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
}

// ---------------------------------------------------------------------------
// Deterministic force-directed layout (repulsion + edge springs + gravity)
// ---------------------------------------------------------------------------
const LAYOUT_WIDTH = 1400;
const LAYOUT_HEIGHT = 900;
const ITERATIONS = 180;

function computeLayout(nodes: GraphConcept[], edges: GraphEdge[]): PositionedNode[] {
  if (nodes.length === 0) return [];

  const pos = nodes.map((_, idx) => {
    const angle = (2 * Math.PI * idx) / Math.max(nodes.length, 1);
    const radius = Math.min(LAYOUT_WIDTH, LAYOUT_HEIGHT) * 0.32;
    return {
      x: LAYOUT_WIDTH / 2 + radius * Math.cos(angle),
      y: LAYOUT_HEIGHT / 2 + radius * Math.sin(angle),
    };
  });

  const adjacency = new Map<string, string[]>();
  for (const edge of edges) {
    if (!adjacency.has(edge.source)) adjacency.set(edge.source, []);
    if (!adjacency.has(edge.target)) adjacency.set(edge.target, []);
    adjacency.get(edge.source)!.push(edge.target);
    adjacency.get(edge.target)!.push(edge.source);
  }

  for (let iter = 0; iter < ITERATIONS; iter++) {
    const temp = 60 * (1 - iter / ITERATIONS) + 2;
    // Repulsion
    for (let i = 0; i < nodes.length; i++) {
      for (let j = i + 1; j < nodes.length; j++) {
        const dx = pos[i].x - pos[j].x;
        const dy = pos[i].y - pos[j].y;
        const distSq = dx * dx + dy * dy + 0.01;
        const dist = Math.sqrt(distSq);
        const force = (4000 / distSq) * temp;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;
        pos[i].x += fx;
        pos[i].y += fy;
        pos[j].x -= fx;
        pos[j].y -= fy;
      }
    }
    // Springs along edges
    for (const edge of edges) {
      const si = nodes.findIndex((n) => n.id === edge.source);
      const ti = nodes.findIndex((n) => n.id === edge.target);
      if (si < 0 || ti < 0) continue;
      const dx = pos[ti].x - pos[si].x;
      const dy = pos[ti].y - pos[si].y;
      const dist = Math.sqrt(dx * dx + dy * dy) + 0.01;
      const force = 0.012 * temp * (dist - 130);
      const fx = (dx / dist) * force;
      const fy = (dy / dist) * force;
      pos[si].x += fx;
      pos[si].y += fy;
      pos[ti].x -= fx;
      pos[ti].y -= fy;
    }
    // Center gravity
    for (const p of pos) {
      p.x += (LAYOUT_WIDTH / 2 - p.x) * 0.004 * temp * 0.1;
      p.y += (LAYOUT_HEIGHT / 2 - p.y) * 0.004 * temp * 0.1;
    }
  }

  const minX = Math.min(...pos.map((p) => p.x));
  const minY = Math.min(...pos.map((p) => p.y));
  return nodes.map((node, idx) => ({
    ...node,
    x: pos[idx].x - minX + 80,
    y: pos[idx].y - minY + 80,
  }));
}

export function useGraph() {
  const activeWorkspaceId = useAppStore((state) => state.activeWorkspaceId);
  const [nodes, setNodes] = useState<GraphConcept[]>([]);
  const [edges, setEdges] = useState<GraphEdge[]>([]);
  const [artifact, setArtifact] = useState<ArtifactLifecycle | null>(null);
  const [selectedNode, setSelectedNode] = useState<GraphConcept | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searching, setSearching] = useState<boolean>(false);
  const [pathNodeIds, setPathNodeIds] = useState<string[]>([]);
  const [pathSourceId, setPathSourceId] = useState<string | null>(null);
  const [pathTargetId, setPathTargetId] = useState<string | null>(null);

  const workspaceRef = useRef(activeWorkspaceId);
  workspaceRef.current = activeWorkspaceId;

  const fetchGraph = useCallback(async () => {
    const ws = workspaceRef.current;
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient<GraphTopology>(`/api/v1/graph/workspace/${encodeURIComponent(ws)}`);
      setNodes(data.nodes || []);
      setEdges(data.edges || []);
      setArtifact(data.artifact || null);
      setSelectedNode((prev) => prev && data.nodes?.some((n) => n.id === prev.id) ? prev : null);
      setPathNodeIds([]);
      setPathSourceId(null);
      setPathTargetId(null);
    } catch (_err) {
      setNodes([]);
      setEdges([]);
      setArtifact(null);
      setSelectedNode(null);
      setError('Failed to load workspace knowledge graph.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph, activeWorkspaceId]);

  const searchConcepts = useCallback(
    async (q: string) => {
      if (!q.trim()) {
        setSearchResults([]);
        return;
      }
      setSearching(true);
      try {
        const ws = workspaceRef.current;
        const results = await apiClient<SearchResult[]>(
          `/api/v1/graph/concepts/search?workspace_id=${encodeURIComponent(ws)}&q=${encodeURIComponent(q)}&limit=8`
        );
        setSearchResults(results || []);
      } catch (_err) {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    },
    []
  );

  const computeShortestPath = useCallback(async (source: string, target: string) => {
    const ws = workspaceRef.current;
    try {
      const data = await apiClient<{ path: string[]; exists: boolean }>(
        `/api/v1/graph/concepts/shortest-path?workspace_id=${encodeURIComponent(ws)}&source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`
      );
      if (data.exists) {
        setPathNodeIds(data.path);
        setPathSourceId(source);
        setPathTargetId(target);
      } else {
        setPathNodeIds([]);
      }
      return data.exists;
    } catch (_err) {
      setPathNodeIds([]);
      return false;
    }
  }, []);

  const clearPath = useCallback(() => {
    setPathNodeIds([]);
    setPathSourceId(null);
    setPathTargetId(null);
  }, []);

  const positionedNodes: PositionedNode[] = useMemo(() => computeLayout(nodes, edges), [nodes, edges]);
  const positionedEdges: PositionedEdge[] = useMemo(() => {
    const byId = new Map(positionedNodes.map((n) => [n.id, n]));
    return edges
      .map((edge) => {
        const s = byId.get(edge.source);
        const t = byId.get(edge.target);
        if (!s || !t) return null;
        return { ...edge, sourceX: s.x, sourceY: s.y, targetX: t.x, targetY: t.y };
      })
      .filter(Boolean) as PositionedEdge[];
  }, [edges, positionedNodes]);

  const pathEdgeKeys = useMemo(() => {
    const keySet = new Set<string>();
    for (let i = 0; i < pathNodeIds.length - 1; i++) {
      keySet.add(`edge_${pathNodeIds[i]}_${pathNodeIds[i + 1]}`);
      keySet.add(`edge_${pathNodeIds[i + 1]}_${pathNodeIds[i]}`);
    }
    return keySet;
  }, [pathNodeIds]);

  const maxX = positionedNodes.reduce((m, n) => Math.max(m, n.x), 0);
  const maxY = positionedNodes.reduce((m, n) => Math.max(m, n.y), 0);

  return {
    nodes,
    edges,
    artifact,
    loading,
    error,
    positionedNodes,
    positionedEdges,
    selectedNode,
    setSelectedNode,
    searchResults,
    searching,
    searchConcepts,
    clearSearchResults: () => setSearchResults([]),
    computeShortestPath,
    clearPath,
    pathNodeIds,
    pathSourceId,
    pathTargetId,
    pathEdgeKeys,
    layoutWidth: maxX + 120,
    layoutHeight: maxY + 120,
    activeWorkspaceId,
    fetchGraph,
  };
}
