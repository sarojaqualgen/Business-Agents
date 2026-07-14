import React from 'react';

/**
 * Small labeled <select> used for table filters (status, action type,
 * result, etc). `options` is an array of { value, label }; the first
 * option is expected to represent "All".
 */
export default function FilterSelect({ label, value, onChange, options }) {
  return (
    <label className="flex items-center gap-2 text-xs text-text-muted">
      <span className="font-mono text-[11px]">{label}</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="bg-bg-s2 border border-border-strong rounded-md text-text text-xs px-2.5 py-1.5 outline-none focus:border-accent transition-colors"
      >
        {options.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
    </label>
  );
}
