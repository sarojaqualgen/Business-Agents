import React from 'react';

const ICONS = {
  empty: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M3.75 9h16.5M3.75 15h16.5M5.25 5.25h13.5A1.5 1.5 0 0 1 20.25 6.75v10.5a1.5 1.5 0 0 1-1.5 1.5H5.25a1.5 1.5 0 0 1-1.5-1.5V6.75a1.5 1.5 0 0 1 1.5-1.5Z"
    />
  ),
  error: (
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M12 9v3.75m0 3.75h.008v.008H12V16.5Zm9-4.5a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z"
    />
  ),
};

/**
 * Shared empty / error placeholder used inside tables and cards. `tone`
 * only changes the icon color; the calling page decides the copy.
 */
export default function EmptyState({ title, description, tone = 'empty', icon = 'empty' }) {
  const toneClasses = tone === 'error' ? 'text-danger bg-danger/10' : 'text-text-faint bg-bg-s2';
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-4">
      <div className={`w-11 h-11 rounded-full flex items-center justify-center mb-3 ${toneClasses}`}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" className="w-5 h-5">
          {ICONS[icon] || ICONS.empty}
        </svg>
      </div>
      <p className="text-sm font-medium text-text">{title}</p>
      {description && <p className="text-xs text-text-muted mt-1 max-w-xs">{description}</p>}
    </div>
  );
}
