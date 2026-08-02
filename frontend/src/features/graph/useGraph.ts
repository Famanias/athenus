import { useState, useEffect } from 'react';

export interface GraphNode {
  id: string;
  label: string;
  type: 'concept' | 'prerequisite' | 'formula';
  prerequisites: string[];
  videoCount: number;
  description: string;
}

export function useGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>([]);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  useEffect(() => {
    async function fetchGraph() {
      try {
        setLoading(true);
        const res = await fetch('http://localhost:8000/api/v1/graph/prerequisites');
        if (res.ok) {
          const data = await res.json();
          if (data.nodes && data.nodes.length > 0) {
            setNodes(data.nodes);
            setSelectedNode(data.nodes[0]);
          } else {
            setNodes([]);
            setSelectedNode(null);
          }
        } else {
          setNodes([]);
          setSelectedNode(null);
        }
      } catch (_err) {
        setNodes([]);
        setSelectedNode(null);
      } finally {
        setLoading(false);
      }
    }
    fetchGraph();
  }, []);

  return { nodes, selectedNode, setSelectedNode, loading };
}
