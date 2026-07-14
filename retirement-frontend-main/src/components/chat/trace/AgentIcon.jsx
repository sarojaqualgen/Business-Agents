import React from 'react';

// Deterministic glyph + color per agent role. Kept as a lookup table (not
// SVGs) so it stays cheap to render inside a scrolling trace list of many
// steps, and new agent roles degrade gracefully to a neutral default.
const AGENT_STYLES = {
  'Intent Agent': { glyph: '◆', className: 'text-accent' },
  'Data Agent': { glyph: '▲', className: 'text-purple' },
  'Compliance Agent': { glyph: '●', className: 'text-success' },
};

const DEFAULT_STYLE = { glyph: '·', className: 'text-text-faint' };

export default function AgentIcon({ agent, className = '' }) {
  const style = AGENT_STYLES[agent] || DEFAULT_STYLE;
  return (
    <span
      aria-hidden="true"
      className={['font-mono text-[10px] leading-none flex-shrink-0', style.className, className].join(' ')}
    >
      {style.glyph}
    </span>
  );
}

export { AGENT_STYLES };
