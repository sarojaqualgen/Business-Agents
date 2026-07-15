import React from 'react';
import { Link } from 'react-router-dom';

const ArrowIcon = () => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={1.8}
    strokeLinecap="round"
    strokeLinejoin="round"
    className="w-3.5 h-3.5"
  >
    <path d="M5 12h13M13 6l6 6-6 6" />
  </svg>
);

export default function ActionCard({ icon, title, description, tooltip, to, tooltipUp = false, comingSoon = false }) {
  const content = (
    <>
      <div className="flex items-start justify-between mb-5">
        <div
          className={[
            'w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0',
            'transition-all duration-200 ease-out',
            comingSoon
              ? 'bg-bg-s2 text-text-faint'
              : 'bg-accent-light text-accent-dark group-hover:bg-accent group-hover:text-white group-hover:scale-105 group-hover:shadow-md',
          ].join(' ')}
        >
          {icon}
        </div>

        {comingSoon ? (
          <span className="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold tracking-wide uppercase bg-bg-s2 text-text-faint border border-border-strong">
            Coming Soon
          </span>
        ) : to ? (
          <span
            className="w-7 h-7 rounded-full bg-bg-s2 text-text-faint flex items-center justify-center
              opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0
              group-hover:bg-accent-light group-hover:text-accent-dark
              transition-all duration-200 ease-out"
          >
            <ArrowIcon />
          </span>
        ) : null}
      </div>

      <h3 className={['text-[15px] font-semibold mb-1.5 tracking-tight', comingSoon ? 'text-text-muted' : 'text-text'].join(' ')}>
        {title}
      </h3>
      <p className="text-[13px] text-text-muted leading-relaxed mb-4">{description}</p>

      {!comingSoon && to && (
        <div
          className="flex items-center gap-1.5 text-[11px] font-mono font-medium text-text-faint
            group-hover:text-accent-dark transition-colors duration-200 uppercase tracking-wide"
        >
          <span>Get started</span>
          <span className="transition-transform duration-200 ease-out group-hover:translate-x-0.5" aria-hidden="true">
            <ArrowIcon />
          </span>
        </div>
      )}

      <div className={tooltipUp ? 'tooltip-bubble tooltip-bubble--up' : 'tooltip-bubble'} role="tooltip">
        {tooltip}
      </div>
    </>
  );

  // Coming-soon cards: hoverable (tooltip works) but not clickable — no Link, no navigation
  if (comingSoon) {
    return (
      <div
        tabIndex={0}
        className="tooltip-anchor group card p-6 block opacity-60 cursor-default
          hover:opacity-80 hover:shadow-sm transition-all duration-200 ease-out
          outline-none focus-visible:ring-2 focus-visible:ring-border-strong"
      >
        {content}
      </div>
    );
  }

  const activeClass =
    'tooltip-anchor group card p-6 block hover:shadow-card-hover hover:border-accent/35 hover:-translate-y-1 ' +
    'transition-all duration-200 ease-out outline-none focus-visible:ring-2 focus-visible:ring-accent/30 cursor-pointer';

  if (to) {
    return (
      <Link to={to} tabIndex={0} className={activeClass}>
        {content}
      </Link>
    );
  }

  return (
    <div tabIndex={0} className={activeClass}>
      {content}
    </div>
  );
}
