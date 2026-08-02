'use client';

import React from 'react';
import { Citation, AgentLog } from './types';

interface RetrievedEvidencePanelProps {
  evidence: Citation[];
  agentLogs: AgentLog[];
}

export const RetrievedEvidencePanel: React.FC<RetrievedEvidencePanelProps> = ({
  evidence,
  agentLogs,
}) => {
  return (
    <aside className="w-80 bg-surface-container-lowest border-l border-outline-variant flex flex-col shrink-0">
      <div className="p-4 border-b border-outline-variant font-bold text-xs text-on-surface flex justify-between items-center">
        <span>Retrieved Evidence</span>
        <span className="text-[10px] font-mono text-secondary bg-secondary/10 px-1.5 py-0.5 rounded">
          {evidence.length} Sources
        </span>
      </div>

      <div className="p-4 overflow-y-auto space-y-4 custom-scrollbar flex-1">
        {/* Evidence Chunks */}
        {evidence.map((item, idx) => (
          <div
            key={idx}
            className="p-3 bg-surface-container-low rounded border border-outline-variant space-y-2 hover:border-secondary transition-all"
          >
            <div className="flex justify-between items-center text-[10px] font-mono">
              <span className="text-secondary">
                ⏱ {item.startTime} - {item.endTime}
              </span>
              <span className="text-on-surface-variant/60">
                Score: {item.score}
              </span>
            </div>
            <p className="text-xs text-on-surface-variant leading-relaxed">
              &quot;{item.textSnippet}&quot;
            </p>
          </div>
        ))}

        {/* Agent Activity Stream */}
        <div className="p-4 bg-surface-container-high rounded border border-outline-variant/60 space-y-2">
          <span className="text-[10px] font-mono text-secondary uppercase tracking-widest block">
            Agent Activity Stream
          </span>
          <div className="text-[11px] font-mono space-y-1 text-on-surface-variant/80">
            {agentLogs.map((log, idx) => (
              <p key={idx}>
                <span className="text-outline">[{log.timestamp}]</span>{' '}
                <span className="text-on-surface font-semibold">{log.agent}:</span>{' '}
                {log.message}
              </p>
            ))}
          </div>
        </div>
      </div>
    </aside>
  );
};
