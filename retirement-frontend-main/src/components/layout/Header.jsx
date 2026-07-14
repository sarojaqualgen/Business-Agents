import React from 'react';
import { useAuth } from '../../context/AuthContext.jsx';

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" className="w-5 h-5">
      <path d="M3.5 6.5h17M3.5 12h17M3.5 17.5h17" />
    </svg>
  );
}

export default function Header({ title, subtitle, onMenuClick }) {
  const { principal } = useAuth();

  return (
    <header className="sticky top-0 z-10 flex items-center justify-between gap-3 px-4 sm:px-6 py-4 border-b border-border bg-bg/90 backdrop-blur">
      <div className="flex items-center gap-3 min-w-0">
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open navigation"
          className="lg:hidden -ml-1 w-9 h-9 flex-shrink-0 rounded-md flex items-center justify-center text-text-muted
            hover:bg-bg-s2 hover:text-text transition-colors"
        >
          <MenuIcon />
        </button>
        <div className="min-w-0">
          <h1 className="text-base sm:text-lg font-semibold text-text truncate">{title}</h1>
          {subtitle && <p className="text-xs text-text-faint mt-0.5 truncate hidden sm:block">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-3 text-xs text-text-muted font-mono flex-shrink-0">
        {principal?.planId && (
          <span className="px-2.5 py-1 rounded-full bg-bg-s2 border border-border whitespace-nowrap">
            {principal.planId}
          </span>
        )}
      </div>
    </header>
  );
}
