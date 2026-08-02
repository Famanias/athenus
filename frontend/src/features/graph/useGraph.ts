import { useState, useEffect } from 'react';

export interface GraphNode {
  id: string;
  label: string;
  type: 'concept' | 'prerequisite' | 'formula';
  prerequisites: string[];
  videoCount: number;
  description: string;
}

const MOCK_GRAPH_NODES: GraphNode[] = [
  {
    id: 'node_1',
    label: 'Scaled Dot-Product Attention',
    type: 'concept',
    prerequisites: ['Linear Algebra', 'Softmax Function'],
    videoCount: 4,
    description: 'Core attention score computation Q*K^T / sqrt(d_k) weighted by V.',
  },
  {
    id: 'node_2',
    label: 'Softmax Scaling Factor',
    type: 'formula',
    prerequisites: ['Gradient Vanishing', 'Vector Variance'],
    videoCount: 2,
    description: 'Division by sqrt(d_k) to maintain unit variance across dot products.',
  },
  {
    id: 'node_3',
    label: 'Positional Encoding',
    type: 'concept',
    prerequisites: ['Sinusoidal Frequencies', 'Token Embeddings'],
    videoCount: 3,
    description: 'Non-recurrent positional ordering injected into vector representations.',
  },
  {
    id: 'node_4',
    label: 'Multi-Head Attention Subspaces',
    type: 'concept',
    prerequisites: ['Scaled Dot-Product Attention'],
    videoCount: 3,
    description: 'Parallel attention projections allowing multi-subspace attendance.',
  },
];

export function useGraph() {
  const [nodes, setNodes] = useState<GraphNode[]>(MOCK_GRAPH_NODES);
  const [selectedNode, setSelectedNode] = useState<GraphNode | null>(MOCK_GRAPH_NODES[0]);
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
          }
        }
      } catch (_err) {
        // Silent fallback
      } finally {
        setLoading(false);
      }
    }
    fetchGraph();
  }, []);

  return { nodes, selectedNode, setSelectedNode, loading };
}
