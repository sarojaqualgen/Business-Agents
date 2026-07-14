import React from 'react';
import { parseInlineEmphasis } from '../../lib/format.js';

export default function FormattedText({ text }) {
  const segments = parseInlineEmphasis(text);
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
    </>
  );
}
