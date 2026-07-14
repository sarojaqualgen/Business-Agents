import React from 'react';

// Minimal, dependency-free stroke icons (24x24 viewBox, currentColor)
// used only by the Participant Actions cards. Keeping these local avoids
// pulling in an icon library just for seven glyphs.

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
  className: 'w-5 h-5',
};

export function LoanIcon() {
  return (
    <svg {...base}>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <path d="M2.5 10h19" />
      <circle cx="7" cy="14.25" r="1.1" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function HardshipIcon() {
  return (
    <svg {...base}>
      <path d="M12 21s-7.5-4.35-9.5-9.1C1.2 8.2 3 5 6.4 5c1.9 0 3.3 1 4.1 2.3.4.6 1 .6 1.4 0C12.7 6 14.1 5 16 5c3.4 0 5.2 3.2 3.9 6.9C17.9 16.65 12 21 12 21Z" />
      <path d="M12 8.5v4M12 14.6h.01" />
    </svg>
  );
}

export function InvestmentIcon() {
  return (
    <svg {...base}>
      <path d="M3 20V4M3 20h18" />
      <path d="M7 16l3.5-4.5L13 14l4.5-6" />
      <path d="M17.5 8h2.5v2.5" />
    </svg>
  );
}

export function DistributionIcon() {
  return (
    <svg {...base}>
      <path d="M4 12a8 8 0 1 1 8 8" />
      <path d="M4 12v5h5" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

export function ContributionIcon() {
  return (
    <svg {...base}>
      <circle cx="8.5" cy="8.5" r="3.2" />
      <circle cx="15.5" cy="15.5" r="3.2" />
      <path d="M17.5 6.5 6.5 17.5" />
    </svg>
  );
}

export function BeneficiaryIcon() {
  return (
    <svg {...base}>
      <circle cx="8.5" cy="8" r="3" />
      <path d="M2.75 19.5c.8-3.2 3.3-5 5.75-5s4.95 1.8 5.75 5" />
      <circle cx="17" cy="7.5" r="2.25" />
      <path d="M15.2 12.2c2 .2 3.9 1.7 4.55 4.3" />
    </svg>
  );
}

export function DocumentIcon() {
  return (
    <svg {...base}>
      <path d="M6 3.5h9l3 3V20a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
      <path d="M15 3.5V7h3" />
      <path d="M8.5 13.5l2 2 4-4.2" />
    </svg>
  );
}
