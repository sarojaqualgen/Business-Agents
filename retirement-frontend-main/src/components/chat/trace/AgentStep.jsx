import React from 'react';
import AgentIcon from './AgentIcon.jsx';

// Splits a mock-engine trace label like "→ GetLoanHeadroom(PART-008)" or
// "← max_loan: $42,500" into a direction glyph + the remaining text, so the
// direction can be styled distinctly from the tool/result content.
function splitDirection(label) {
  if (!label) return { direction: null, rest: '' };
  if (label.startsWith('→ ')) return { direction: 'out', rest: label.slice(2) };
  if (label.startsWith('← ')) return { direction: 'in', rest: label.slice(2) };
  return { direction: null, rest: label };
}

const DIRECTION_STYLE = {
  out: { glyph: '→', className: 'text-text-faint' },
  in: { glyph: '←', className: 'text-success' },
};

/**
 * Renders one agent/tool trace line. Pure presentational component — no
 * knowledge of streaming state — so it can be reused inline (collapsible
 * panel) or in a connector-style vertical timeline.
 */
export default function AgentStep({ step, isLast = false, isActive = false }) {
  const { direction, rest } = splitDirection(step.label);
  const dirStyle = direction ? DIRECTION_STYLE[direction] : null;

  return (
    <div className="flex gap-2 items-start font-mono text-[11px] leading-relaxed">
      <div className="flex flex-col items-center flex-shrink-0 pt-0.5">
        <AgentIcon agent={step.agent} className={isActive ? 'animate-pulse' : ''} />
        {!isLast && <span className="w-px flex-1 min-h-[10px] bg-border mt-1" />}
      </div>
      <div className={isLast ? '' : 'pb-1.5'}>
        <span className="text-accent">[{step.agent}]</span>{' '}
        {dirStyle ? (
          <>
            <span className={dirStyle.className}>{dirStyle.glyph}</span>{' '}
            <span className="text-text-muted">{rest}</span>
          </>
        ) : (
          <span className="text-text-muted">{rest}</span>
        )}
      </div>
    </div>
  );
}
