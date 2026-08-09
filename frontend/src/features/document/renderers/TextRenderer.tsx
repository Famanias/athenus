// TextRenderer — renders raw TXT and Markdown (MD) source documents.
//
// Implementation notes:
//   - The file content is fetched from the backend getMediaUrl() endpoint.
//   - `.txt` files are displayed as plain preformatted text (preserving
//     whitespace/line breaks exactly).
//   - `.md` files are parsed with a small, dependency-free Markdown renderer
//     that produces React elements directly (no dangerouslySetInnerHTML, so
//     untrusted uploaded content cannot inject HTML/scripts).
//   - Headings receive stable anchor ids, surfaced in a "Jump to section"
//     index for quick navigation.
//
// Supported Markdown subset: ATX headings (#..######), fenced code blocks,
// inline code, bold, italic, unordered/ordered lists, links, blockquotes,
// horizontal rules, and paragraphs.

'use client';

import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/Button';
import { extractExtension } from '../registry/RendererRegistry';
import type { RendererProps } from '../types';

interface HeadingAnchor {
  id: string;
  level: number;
  text: string;
}

// ---------------------------------------------------------------------------
// Minimal inline Markdown renderer (produces React nodes, no innerHTML)
// ---------------------------------------------------------------------------

interface InlineToken {
  type: 'text' | 'code' | 'bold' | 'italic' | 'link';
  content: string;
  url?: string;
}

/** Split inline text into styled tokens. Order matters: code first (so
 *  asterisks inside `code` are not italicized), then bold, then links,
 *  then italic. */
function tokenizeInline(text: string): InlineToken[] {
  const tokens: InlineToken[] = [];
  let remaining = text;

  while (remaining.length > 0) {
    // Inline code
    const codeMatch = remaining.match(/^`([^`]+)`/);
    if (codeMatch) {
      tokens.push({ type: 'code', content: codeMatch[1] });
      remaining = remaining.slice(codeMatch[0].length);
      continue;
    }
    // Link [label](url)
    const linkMatch = remaining.match(/^\[([^\]]+)\]\(([^)\s]+)\)/);
    if (linkMatch) {
      tokens.push({ type: 'link', content: linkMatch[1], url: linkMatch[2] });
      remaining = remaining.slice(linkMatch[0].length);
      continue;
    }
    // Bold **text**
    const boldMatch = remaining.match(/^\*\*([^*]+)\*\*/);
    if (boldMatch) {
      tokens.push({ type: 'bold', content: boldMatch[1] });
      remaining = remaining.slice(boldMatch[0].length);
      continue;
    }
    // Italic *text*
    const italicMatch = remaining.match(/^\*([^*]+)\*/);
    if (italicMatch) {
      tokens.push({ type: 'italic', content: italicMatch[1] });
      remaining = remaining.slice(italicMatch[0].length);
      continue;
    }
    // Plain text up to the next special marker
    const nextSpecial = remaining.search(/[`[*]/);
    if (nextSpecial === -1) {
      tokens.push({ type: 'text', content: remaining });
      remaining = '';
    } else if (nextSpecial === 0) {
      // Lone marker with no match — consume it as literal text.
      tokens.push({ type: 'text', content: remaining[0] });
      remaining = remaining.slice(1);
    } else {
      tokens.push({ type: 'text', content: remaining.slice(0, nextSpecial) });
      remaining = remaining.slice(nextSpecial);
    }
  }

  return tokens;
}

function renderInline(tokens: InlineToken[], keyPrefix: string): React.ReactNode[] {
  return tokens.map((t, i) => {
    const key = `${keyPrefix}-${i}`;
    switch (t.type) {
      case 'code':
        return (
          <code key={key} className="px-1 py-0.5 rounded bg-surface-container-high font-mono text-[0.95em] text-secondary">
            {t.content}
          </code>
        );
      case 'bold':
        return <strong key={key} className="font-bold">{t.content}</strong>;
      case 'italic':
        return <em key={key} className="italic">{t.content}</em>;
      case 'link':
        return (
          <a
            key={key}
            href={t.url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-secondary underline decoration-secondary/40 underline-offset-2 hover:decoration-secondary"
          >
            {t.content}
          </a>
        );
      default:
        return <React.Fragment key={key}>{t.content}</React.Fragment>;
    }
  });
}

// ---------------------------------------------------------------------------
// Markdown block renderer
// ---------------------------------------------------------------------------

function buildAnchorId(text: string, index: number): string {
  const slug = text
    .toLowerCase()
    .replace(/[^a-z0-9一-龥\s-]/g, '')
    .trim()
    .replace(/\s+/g, '-');
  return slug || `section-${index + 1}`;
}

interface MarkdownBlock {
  id: string;
  level: number;
  text: string;
}

function parseMarkdownBlocks(source: string): MarkdownBlock[] {
  const rawBlocks = source.split(/\n{2,}/);
  const blocks: MarkdownBlock[] = [];
  let inFence = false;
  let fenceAccumulator: string[] = [];

  for (const raw of rawBlocks) {
    // Fenced code block open/close
    if (raw.trimStart().startsWith('```')) {
      if (!inFence) {
        inFence = true;
        fenceAccumulator = [];
        // content after the opening fence on the same line is the language hint
        const lang = raw.trim().slice(3).trim();
        if (lang) fenceAccumulator.push(lang);
      } else {
        inFence = false;
        blocks.push({ id: `code-${blocks.length}`, level: 0, text: `\`\`\`\n${fenceAccumulator.join('\n')}\n\`\`\`` });
      }
      continue;
    }
    if (inFence) {
      fenceAccumulator.push(raw);
      continue;
    }

    // Heading
    const headingMatch = raw.match(/^(#{1,6})\s+(.+)$/);
    if (headingMatch) {
      const level = headingMatch[1].length;
      const text = headingMatch[2].trim();
      blocks.push({ id: buildAnchorId(text, blocks.length), level, text });
      continue;
    }

    // Horizontal rule
    if (/^\s*(---+|\*\*\*+)\s*$/.test(raw)) {
      blocks.push({ id: `hr-${blocks.length}`, level: 0, text: '---' });
      continue;
    }

    // Blockquote
    if (raw.trimStart().startsWith('>')) {
      const quoteText = raw
        .split('\n')
        .map((l) => l.replace(/^\s*>\s?/, ''))
        .join('\n');
      blocks.push({ id: `quote-${blocks.length}`, level: 0, text: `> ${quoteText}` });
      continue;
    }

    // Lists (each item becomes its own block)
    if (/^\s*[-*+]\s+/.test(raw) || /^\s*\d+[.)]\s+/.test(raw)) {
      raw.split('\n').forEach((line) => {
        const unordered = line.match(/^\s*[-*+]\s+(.+)$/);
        const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
        if (unordered) blocks.push({ id: `li-${blocks.length}`, level: 0, text: `• ${unordered[1]}` });
        else if (ordered) blocks.push({ id: `li-${blocks.length}`, level: 0, text: `1. ${ordered[1]}` });
      });
      continue;
    }

    // Paragraph
    blocks.push({ id: `p-${blocks.length}`, level: 0, text: raw });
  }

  // Close any unclosed fence defensively.
  if (inFence) {
    blocks.push({ id: `code-${blocks.length}`, level: 0, text: `\`\`\`\n${fenceAccumulator.join('\n')}\n\`\`\`` });
  }

  return blocks;
}

// ---------------------------------------------------------------------------
// TextRenderer component
// ---------------------------------------------------------------------------

export const TextRenderer: React.FC<RendererProps> = ({
  url,
  metadata,
  activePage,
  safeTotalPages,
  targetPage,
  onPageChange,
}) => {
  const [content, setContent] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [jumpTarget, setJumpTarget] = useState<string | null>(null);
  const anchorRefs = useRef<Record<string, HTMLHeadingElement | null>>({});

  const isMarkdown = useMemo(() => {
    const ext = extractExtension(metadata.file_path || metadata.title || url);
    return ext.toLowerCase() === '.md' || ext.toLowerCase() === '.markdown';
  }, [metadata.file_path, metadata.title, url]);

  // Fetch the text content from the backend.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setContent('');

    fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to fetch document (HTTP ${res.status})`);
        return res.text();
      })
      .then((text) => {
        if (!cancelled) {
          setContent(text);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load text document.');
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [url]);

  const blocks = useMemo(() => (isMarkdown ? parseMarkdownBlocks(content) : []), [isMarkdown, content]);

  const headings: HeadingAnchor[] = useMemo(
    () =>
      blocks
        .filter((b) => b.level >= 1 && b.level <= 6)
        .map((b) => ({ id: b.id, level: b.level, text: b.text })),
    [blocks]
  );

  // Scroll to a section anchor when requested (from the jump index).
  useEffect(() => {
    if (!jumpTarget) return;
    const el = anchorRefs.current[jumpTarget];
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
    setJumpTarget(null);
  }, [jumpTarget]);

  const fileSize = useMemo(() => {
    const bytes = metadata.file_size_bytes;
    if (bytes > 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
    if (bytes > 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${bytes} bytes`;
  }, [metadata.file_size_bytes]);

  const handleDownload = useCallback(() => {
    window.open(url, '_blank', 'noopener,noreferrer');
  }, [url]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden bg-surface-container-lowest">
      <div className="flex-1 overflow-y-auto custom-scrollbar">
        {loading && (
          <div className="p-10 text-center text-xs text-on-surface-variant font-mono">
            Loading text document…
          </div>
        )}

        {error && (
          <div className="p-10 text-center space-y-3">
            <span className="text-3xl block">⚠️</span>
            <p className="text-xs text-on-surface-variant">{error}</p>
            <Button variant="secondary" size="sm" onClick={handleDownload}>
              Download Original File
            </Button>
          </div>
        )}

        {!loading && !error && !isMarkdown && (
          <pre className="p-6 text-xs leading-relaxed text-on-surface whitespace-pre-wrap font-mono select-text">
            {content}
          </pre>
        )}

        {!loading && !error && isMarkdown && (
          <div className="max-w-3xl mx-auto p-6 space-y-3 text-sm leading-relaxed text-on-surface select-text">
            {blocks.map((block, idx) => {
              if (block.level >= 1 && block.level <= 6) {
                const Tag = `h${block.level}` as 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6';
                const sizeClass =
                  block.level === 1
                    ? 'text-2xl font-bold'
                    : block.level === 2
                    ? 'text-xl font-bold'
                    : block.level === 3
                    ? 'text-lg font-bold'
                    : block.level === 4
                    ? 'text-base font-bold'
                    : 'text-sm font-bold';
                return (
                  <Tag
                    key={block.id}
                    id={block.id}
                    ref={(el) => {
                      anchorRefs.current[block.id] = el;
                    }}
                    className={`${sizeClass} text-on-surface mt-5 pt-3 border-t border-outline-variant/40 scroll-mt-24`}
                  >
                    {renderInline(tokenizeInline(block.text), block.id)}
                  </Tag>
                );
              }

              if (block.text.startsWith('```')) {
                const codeBody = block.text.replace(/^```\n?/, '').replace(/\n?```$/, '');
                return (
                  <pre
                    key={block.id}
                    className="p-3 rounded bg-surface-container-high border border-outline-variant/50 overflow-x-auto text-xs font-mono text-on-surface custom-scrollbar"
                  >
                    {codeBody}
                  </pre>
                );
              }

              if (block.text === '---') {
                return <hr key={block.id} className="border-outline-variant/40 my-3" />;
              }

              if (block.text.startsWith('> ')) {
                const quoteBody = block.text.slice(2);
                return (
                  <blockquote
                    key={block.id}
                    className="border-l-4 border-secondary/50 pl-3 py-1 text-on-surface-variant italic"
                  >
                    {renderInline(tokenizeInline(quoteBody), block.id)}
                  </blockquote>
                );
              }

              if (block.text.startsWith('• ')) {
                return (
                  <ul key={block.id} className="list-none space-y-1 pl-1">
                    <li className="flex gap-2">
                      <span className="text-secondary shrink-0">•</span>
                      <span>{renderInline(tokenizeInline(block.text.slice(2)), block.id)}</span>
                    </li>
                  </ul>
                );
              }

              if (/^\d+\.\s/.test(block.text)) {
                return (
                  <ol key={block.id} className="list-none space-y-1 pl-1">
                    <li className="flex gap-2">
                      <span className="text-secondary shrink-0 font-mono">
                        {block.text.match(/^\d+/)?.[0]}.
                      </span>
                      <span>{renderInline(tokenizeInline(block.text.replace(/^\d+\.\s/, '')), block.id)}</span>
                    </li>
                  </ol>
                );
              }

              return (
                <p key={block.id}>{renderInline(tokenizeInline(block.text), block.id)}</p>
              );
            })}
          </div>
        )}
      </div>

      {/* Text toolbar */}
      <div className="px-3 py-2 bg-surface-container-low border-t border-outline-variant text-[10px] font-mono text-on-surface-variant/60 flex flex-wrap justify-between items-center gap-3 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-secondary shrink-0">{isMarkdown ? '📝 Markdown' : '📄 Text'}</span>
          <span className="hidden md:inline truncate max-w-xs">{metadata.title}</span>
          <span className="hidden md:inline">{fileSize}</span>
        </div>

        {headings.length > 0 && (
          <select
            value=""
            onChange={(e) => {
              if (e.target.value) setJumpTarget(e.target.value);
            }}
            className="bg-surface-container border border-outline-variant rounded px-2 py-1 text-[10px] font-mono text-on-surface focus:border-secondary outline-none max-w-[220px]"
          >
            <option value="">Jump to section…</option>
            {headings.map((h) => (
              <option key={h.id} value={h.id}>
                {'#'.repeat(h.level)} {h.text}
              </option>
            ))}
          </select>
        )}

        <Button variant="ghost" size="sm" onClick={handleDownload} title="Open raw file">
          Open
        </Button>
      </div>
    </div>
  );
};
