'use client';

import React from 'react';
import { useGraph } from './useGraph';
import { Button } from '@/components/ui/Button';

export const KnowledgeGraphCanvas: React.FC = () => {
  const { nodes, selectedNode, setSelectedNode, loading } = useGraph();

  return (
    <div className="flex-1 flex overflow-hidden w-full h-full">
      {/* Visual Graph Canvas Area */}
      <div className="flex-1 bg-surface-container-lowest border-r border-outline-variant flex flex-col p-6 space-y-4 relative">
        <div className="flex justify-between items-center z-10">
          <div>
            <h2 className="font-carvist text-xl font-bold text-on-surface">
              Concept Knowledge Graph Visualizer
            </h2>
            <p className="text-xs text-on-surface-variant">
              Interactive prerequisite dependencies across all workspace video lectures.
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" icon="sync">
              Update Mappings
            </Button>
          </div>
        </div>

        {/* Interactive Node Graph Map Representation */}
        <div className="flex-1 bg-surface-container-low border border-outline-variant rounded-lg p-8 relative flex items-center justify-center overflow-hidden">
          {/* Animated Graph Background Effect */}
          <div className="absolute inset-0 opacity-20 pointer-events-none flex items-center justify-center">
            <div className="w-96 h-96 border border-secondary/30 rounded-full animate-[spin_25s_linear_infinite]" />
            <div className="absolute w-[480px] h-[480px] border border-secondary/15 rounded-full animate-[spin_40s_linear_infinite_reverse]" />
          </div>

          {loading && (
            <div className="relative z-10 p-8 text-center text-xs text-on-surface-variant font-mono">
              Analyzing concept relationships...
            </div>
          )}

          {!loading && nodes.length === 0 && (
            <div className="relative z-10 p-8 text-center space-y-3 max-w-sm">
              <span className="text-4xl block">🕸</span>
              <h4 className="font-bold text-sm text-on-surface">No Concept Nodes Mapped</h4>
              <p className="text-xs text-on-surface-variant">
                Upload and process video lectures to automatically extract concepts and construct your workspace knowledge graph.
              </p>
            </div>
          )}

          {/* Node Grid Elements */}
          {!loading && nodes.length > 0 && (
            <div className="relative z-10 grid grid-cols-2 gap-8 max-w-2xl w-full">
              {nodes.map((node) => {
                const isSelected = selectedNode?.id === node.id;
                return (
                  <div
                    key={node.id}
                    onClick={() => setSelectedNode(node)}
                    className={`p-4 rounded-lg border transition-all cursor-pointer space-y-2 ${
                      isSelected
                        ? 'bg-surface-container-high border-secondary ring-2 ring-secondary/40 shadow-lg scale-105'
                        : 'bg-surface-container border-outline-variant hover:border-secondary/60'
                    }`}
                  >
                    <div className="flex justify-between items-center">
                      <span className="font-mono text-[10px] text-secondary font-semibold uppercase">
                        {node.type}
                      </span>
                      <span className="text-[10px] font-mono text-on-surface-variant/60">
                        🎥 {node.videoCount} Videos
                      </span>
                    </div>
                    <h4 className="font-bold text-xs text-on-surface">
                      {node.label}
                    </h4>
                    <p className="text-[11px] text-on-surface-variant/70 line-clamp-2">
                      {node.description}
                    </p>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Right Node Inspector Panel */}
      <aside className="w-80 bg-surface-container-lowest border-l border-outline-variant flex flex-col p-6 space-y-4 shrink-0">
        <span className="font-mono text-xs font-semibold text-secondary uppercase tracking-wider">
          Node Inspector
        </span>

        {selectedNode ? (
          <div className="space-y-4 text-xs">
            <div className="p-4 bg-surface-container-low border border-outline-variant rounded space-y-2">
              <span className="font-mono text-[10px] text-secondary uppercase font-semibold">
                ACTIVE NODE
              </span>
              <h3 className="font-bold text-sm text-on-surface">
                {selectedNode.label}
              </h3>
              <p className="text-on-surface-variant leading-relaxed">
                {selectedNode.description}
              </p>
            </div>

            <div className="space-y-2">
              <span className="font-mono text-[10px] text-on-surface-variant font-semibold uppercase block">
                Prerequisite Concepts
              </span>
              <div className="space-y-1.5">
                {selectedNode.prerequisites.map((prereq, idx) => (
                  <div
                    key={idx}
                    className="p-2 bg-surface-container rounded border border-outline-variant text-on-surface flex items-center gap-2 font-mono text-[11px]"
                  >
                    <span className="text-secondary">✦</span>
                    <span>{prereq}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        ) : (
          <p className="text-xs text-on-surface-variant">Select a concept node to view prerequisite mappings.</p>
        )}
      </aside>
    </div>
  );
};
