import React from 'react';

/**
 * Consistent loading indicator used across dashboards while a page's
 * initial data fetch is in flight. Purely presentational — no polling or
 * timing logic lives here.
 */
export default function LoadingState({ label = 'Loading…' }) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 py-16 text-text-muted">
      <span
        className="w-6 h-6 rounded-full border-2 border-border-strong border-t-accent animate-spin"
        aria-hidden="true"
      />
      <p className="text-sm">{label}</p>
    </div>
  );
}
