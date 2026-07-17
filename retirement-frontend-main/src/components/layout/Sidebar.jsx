import React from 'react';
import { NavLink } from 'react-router-dom';
import Avatar from '../ui/Avatar.jsx';
import { useAuth } from '../../context/AuthContext.jsx';
import { titleCase } from '../../lib/format.js';
import QualGenLogo from '../../assets/QualGenLogo.jsx';

const PARTICIPANT_NAV = [
  { to: '/participant', label: 'Participant Actions', end: true },
  { to: '/participant/chat', label: 'Chat' },
  { to: '/participant/loans', label: 'Loans' },
  { to: '/participant/investments', label: 'Investments' },
  { to: '/participant/distributions', label: 'Distributions' },
  { to: '/participant/documents', label: 'Documents' },
  { to: '/participant/activity', label: 'Activity History' },
];

const SPONSOR_NAV = [
  { to: '/sponsor', label: 'Overview', end: true },
  { to: '/sponsor/queue', label: 'Review Queue' },
  { to: '/sponsor/audit', label: 'Audit Log' },
  { to: '/sponsor/blackout', label: 'Blackout Manager' },
];

function navLinkClasses({ isActive }) {
  return [
    'flex items-center gap-2.5 px-4 py-2.5 rounded-md text-sm border-l-[3px]',
    'transition-all duration-200 ease-out will-change-transform',
    isActive
      ? 'bg-accent-light text-accent-dark font-semibold border-accent shadow-sm translate-x-0'
      : 'text-text-muted border-transparent hover:bg-bg-s2 hover:text-text hover:border-border-strong ' +
        'hover:translate-x-0.5',
  ].join(' ');
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" className="w-4.5 h-4.5">
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  );
}

export default function Sidebar({ variant, isOpen = false, onClose }) {
  const { principal, logout } = useAuth();
  const nav = variant === 'sponsor' ? SPONSOR_NAV : PARTICIPANT_NAV;
  const displayName =
    variant === 'sponsor' ? principal?.planId || 'Plan Sponsor' : principal?.participantId || 'Participant';

  return (
    <>
      {/* Mobile scrim, shown only while the drawer is open. */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/40 z-30 lg:hidden"
          onClick={onClose}
          aria-hidden="true"
        />
      )}

      <aside
        className={[
          'w-[264px] min-w-[264px] bg-bg-surface border-r border-border flex flex-col h-screen',
          'fixed inset-y-0 left-0 z-40 transition-transform duration-200 ease-out',
          'lg:sticky lg:top-0 lg:translate-x-0 lg:z-auto',
          isOpen ? 'translate-x-0 shadow-card-hover' : '-translate-x-full',
        ].join(' ')}
      >
        <div className="flex items-center justify-between px-5 pt-[18px] pb-[14px] border-b border-border">
          <div className="flex flex-col gap-0.5">
            <div className="flex items-center gap-2">
              <QualGenLogo height={22} iconOnly={true} />
              <span className="text-[19px] font-extrabold tracking-tight text-text leading-none">QRetire</span>
            </div>
            <div className="text-[10px] text-text-faint font-mono tracking-wide ml-0.5">Powered by Qualgen.ai</div>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Close navigation"
            className="lg:hidden w-8 h-8 rounded-md flex items-center justify-center text-text-muted hover:bg-bg-s2 hover:text-text transition-colors"
          >
            <CloseIcon />
          </button>
        </div>

        <div className="flex items-center gap-2.5 px-5 py-3.5 border-b border-border">
          <Avatar name={displayName} principalType={principal?.principalType} />
          <div className="min-w-0">
            <div className="text-sm font-medium truncate">{displayName}</div>
            <div className="text-[11px] text-text-faint truncate">
              {titleCase(principal?.principalType || '')}
            </div>
          </div>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1.5 overflow-y-auto">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={navLinkClasses} onClick={onClose}>
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="px-3 py-4 border-t border-border">
          <button
            type="button"
            onClick={logout}
            className="w-full text-left px-4 py-2.5 rounded-md text-sm text-text-muted hover:bg-danger/10 hover:text-danger transition-colors duration-150"
          >
            Sign out
          </button>
        </div>
      </aside>
    </>
  );
}
