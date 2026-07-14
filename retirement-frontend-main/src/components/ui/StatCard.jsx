import React from 'react';

export default function StatCard({ label, value, hint }) {
  return (
    <div className={`card p-5 transition-all duration-150 ${hint ? 'hover:shadow-card-hover hover:border-accent/30 hover:-translate-y-0.5' : ''}`}>
      <div className="text-[11px] font-mono text-text-muted mb-2 uppercase tracking-wide">{label}</div>
      <div className="text-2xl font-semibold text-text">{value}</div>
      {hint && <div className="text-xs text-accent-dark font-medium mt-1.5">{hint} →</div>}
    </div>
  );
}
