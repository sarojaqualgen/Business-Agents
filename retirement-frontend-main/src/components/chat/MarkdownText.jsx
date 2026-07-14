import React from 'react';

/**
 * Full-markdown renderer for assistant responses. Handles:
 *   # ## ###  → headings (h2–h4, bold, text-text)
 *   ---        → horizontal rule
 *   - or *     → unordered bullet list
 *   > quote    → blockquote with left warning border
 *   `code`     → inline code span (bg-bg-s2, border-border)
 *   **bold**   → <strong>
 *   blank line → paragraph break
 *
 * No external dependencies — pure React/JSX.
 * Parse is done line-by-line so we never use dangerouslySetInnerHTML.
 */

// ── Inline parser: splits text into bold / code / plain segments ──────────
const INLINE_RE = /(\*\*[^*]+\*\*|`[^`]+`)/g;

function parseInline(text) {
  const parts = text.split(INLINE_RE);
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return (
        <strong key={i} className="font-semibold text-text">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return (
        <code
          key={i}
          className="px-1 py-0.5 rounded text-xs font-mono bg-bg-s2 border border-border text-text"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    return <React.Fragment key={i}>{part}</React.Fragment>;
  });
}

// ── Block parser: converts lines into typed block descriptors ─────────────
function parseBlocks(text) {
  const rawLines = text.split('\n');
  const blocks = [];
  let listItems = null; // accumulator for consecutive list lines

  function flushList() {
    if (listItems && listItems.length > 0) {
      blocks.push({ type: 'list', items: listItems });
      listItems = null;
    }
  }

  for (const line of rawLines) {
    // Heading
    const headingMatch = line.match(/^(#{1,3})\s+(.*)/);
    if (headingMatch) {
      flushList();
      const level = headingMatch[1].length; // 1, 2, or 3
      blocks.push({ type: 'heading', level, text: headingMatch[2] });
      continue;
    }

    // Horizontal rule
    if (/^---+$/.test(line.trim())) {
      flushList();
      blocks.push({ type: 'hr' });
      continue;
    }

    // Blockquote
    const quoteMatch = line.match(/^>\s?(.*)/);
    if (quoteMatch) {
      flushList();
      blocks.push({ type: 'blockquote', text: quoteMatch[1] });
      continue;
    }

    // Unordered list item
    const listMatch = line.match(/^[-*]\s+(.*)/);
    if (listMatch) {
      if (!listItems) listItems = [];
      listItems.push(listMatch[1]);
      continue;
    }

    // Blank line — flush list and act as paragraph separator
    if (line.trim() === '') {
      flushList();
      blocks.push({ type: 'blank' });
      continue;
    }

    // Plain paragraph line
    flushList();
    blocks.push({ type: 'paragraph', text: line });
  }

  flushList();
  return blocks;
}

// ── Heading level → Tailwind classes ─────────────────────────────────────
function headingClass(level) {
  switch (level) {
    case 1:  return 'text-base font-bold text-text mt-1';
    case 2:  return 'text-sm font-bold text-text mt-1';
    default: return 'text-sm font-semibold text-text mt-1';
  }
}

// ── Main component ────────────────────────────────────────────────────────
export default function MarkdownText({ text }) {
  if (!text) return null;

  const blocks = parseBlocks(text);

  // Collapse consecutive blank blocks so multiple empty lines don't add
  // extra whitespace.
  const deduped = blocks.filter(
    (b, i) => !(b.type === 'blank' && blocks[i - 1]?.type === 'blank'),
  );

  return (
    <div className="space-y-1.5 text-sm leading-relaxed">
      {deduped.map((block, i) => {
        switch (block.type) {
          case 'heading':
            return (
              <p key={i} className={headingClass(block.level)}>
                {parseInline(block.text)}
              </p>
            );

          case 'hr':
            return <hr key={i} className="border-border my-1" />;

          case 'list':
            return (
              <ul key={i} className="space-y-0.5 pl-1">
                {block.items.map((item, j) => (
                  <li key={j} className="flex items-start gap-1.5">
                    <span className="text-accent mt-0.5 flex-shrink-0 leading-snug">●</span>
                    <span>{parseInline(item)}</span>
                  </li>
                ))}
              </ul>
            );

          case 'blockquote':
            return (
              <blockquote
                key={i}
                className="border-l-2 border-warning/60 pl-3 text-text-muted italic"
              >
                {parseInline(block.text)}
              </blockquote>
            );

          case 'blank':
            return <div key={i} className="h-1" />;

          case 'paragraph':
          default:
            return (
              <p key={i} className="text-text">
                {parseInline(block.text)}
              </p>
            );
        }
      })}
    </div>
  );
}
