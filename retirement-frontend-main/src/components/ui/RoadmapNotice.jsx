import React from 'react';

/**
 * Used on pages whose real functionality is handled elsewhere today —
 * through the chat/workflow engine, or a manual sponsor-side process —
 * rather than on this page itself. Communicates scope honestly instead of
 * a bare stub, in a professional card layout.
 *
 * `icon` is optional: when provided it renders as a larger illustration
 * badge with the milestone shown as a small pill underneath; when omitted
 * the milestone renders inside the badge itself, preserving the original
 * compact look for any call site that doesn't pass one.
 */
export default function RoadmapNotice({ title, description, milestone, points, icon }) {
  return (
    <div className="card p-8 sm:p-10 max-w-2xl mx-auto text-center relative overflow-hidden">
      {/* Soft banking-style backdrop glow, purely decorative. */}
      <div
        className="absolute -top-16 left-1/2 -translate-x-1/2 w-56 h-56 rounded-full bg-accent-light/60
          blur-3xl pointer-events-none"
        aria-hidden="true"
      />

      <div className="relative">
        <div
          className="w-14 h-14 rounded-2xl bg-accent-light text-accent-dark mx-auto mb-4 flex items-center
            justify-center shadow-sm"
        >
          {icon || (
            <span className="font-mono text-sm font-semibold" aria-hidden="true">
              {milestone}
            </span>
          )}
        </div>

        {icon && (
          <div
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-bg-s2 border border-border
              text-[11px] font-mono text-text-muted mb-3"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-accent" aria-hidden="true" />
            {milestone}
          </div>
        )}

        <h2 className="text-base font-semibold text-text mb-2">{title}</h2>
        <p className="text-sm text-text-muted leading-relaxed max-w-md mx-auto">{description}</p>

        {points && points.length > 0 && (
          <ul className="text-left mt-6 pt-6 border-t border-border space-y-3 max-w-md mx-auto">
            {points.map((point) => (
              <li key={point} className="flex items-start gap-2.5 text-sm text-text-muted">
                <span className="mt-1.5 w-1.5 h-1.5 rounded-full bg-accent flex-shrink-0" />
                <span>{point}</span>
              </li>
            ))}
          </ul>
        )}

        <p className="text-[11px] font-mono text-text-faint mt-6 pt-5 border-t border-border max-w-md mx-auto">
          This workflow will execute through the chat engine and backend API integration.
        </p>
      </div>
    </div>
  );
}
