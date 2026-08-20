'use client';

import React from 'react';

interface ManualNotesEditorProps {
  content: string;
  onChange: (text: string) => void;
  readOnly?: boolean;
}

export const ManualNotesEditor: React.FC<ManualNotesEditorProps> = ({
  content,
  onChange,
  readOnly = false,
}) => {
  const wordCount = content.trim() ? content.trim().split(/\s+/).length : 0;

  return (
    <div className="flex flex-col h-full min-h-[420px] space-y-2">
      <textarea
        value={content}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readOnly}
        placeholder="Start writing..."
        className="w-full flex-1 bg-transparent text-sm text-on-surface placeholder:text-on-surface-variant/35 resize-none outline-none focus:ring-0 border-none p-2 leading-relaxed custom-scrollbar"
        spellCheck={false}
      />
      <div className="flex justify-between items-center text-[11px] text-on-surface-variant/60 font-mono px-2 pt-2 border-t border-outline-variant/20">
        <span>Markdown formatted</span>
        <span>{wordCount} words · {content.length} chars</span>
      </div>
    </div>
  );
};
