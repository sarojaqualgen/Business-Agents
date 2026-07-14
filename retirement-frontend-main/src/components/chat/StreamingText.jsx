import React, { useState } from 'react';
import { useTypewriter } from '../../hooks/useTypewriter.js';
import { hasAnimated, markAnimated } from '../../lib/animatedIds.js';
import { parseInlineEmphasis } from '../../lib/format.js';

/**
 * Character-reveal renderer for a completed assistant response. Plays the
 * typewriter animation exactly once per message id (tracked via
 * lib/animatedIds) — messages rehydrated from localStorage, or re-rendered
 * after the animation already ran, display instantly instead of re-typing.
 *
 * Still routes through parseInlineEmphasis so **bold** markers render the
 * same way whether or not the text is mid-animation.
 */
export default function StreamingText({ id, text }) {
  const [skip] = useState(() => hasAnimated(id));
  const { visibleText, done } = useTypewriter(text, {
    skip,
    onDone: () => markAnimated(id),
  });

  const segments = parseInlineEmphasis(visibleText);

  return (
    <>
      {segments.map((seg, i) =>
        seg.bold ? (
          <strong key={i} className="font-semibold text-text">
            {seg.text}
          </strong>
        ) : (
          <React.Fragment key={i}>{seg.text}</React.Fragment>
        ),
      )}
      {!done && <span className="inline-block w-1.5 h-3.5 -mb-0.5 ml-0.5 bg-accent/70 animate-pulse" />}
    </>
  );
}
