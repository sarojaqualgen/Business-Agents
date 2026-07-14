import React from 'react';

// Colour map keyed by lowercase status/result string. Anything unmapped
// falls back to the neutral "muted" style rather than guessing a colour.
const TONE_CLASSES = {
  pending: 'bg-warning/15 text-warning border-warning/30',
  approved: 'bg-success/15 text-success border-success/30',
  denied: 'bg-danger/15 text-danger border-danger/30',
  active: 'bg-danger/15 text-danger border-danger/30',
  inactive: 'bg-success/15 text-success border-success/30',
  default: 'bg-bg-s2 text-text-muted border-border-strong',
};

export default function Badge({ tone, children }) {
  const key = (tone || '').toLowerCase();
  const classes = TONE_CLASSES[key] || TONE_CLASSES.default;
  return (
    <span
      className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border capitalize ${classes}`}
    >
      {children}
    </span>
  );
}
