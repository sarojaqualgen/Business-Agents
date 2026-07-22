import React from 'react';
import Badge from '../ui/Badge.jsx';
import EmptyState from '../ui/EmptyState.jsx';
import { titleCase } from '../../lib/format.js';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

const COLUMNS = [
  { key: 'timestamp', label: 'Timestamp' },
  { key: 'participant_id', label: 'Participant' },
  { key: 'plan_id', label: 'Plan' },
  { key: 'action', label: 'Action' },
  { key: 'result', label: 'Result' },
  { key: 'autonomy', label: 'Autonomy' },
  { key: 'citation', label: 'Citation' },
];

export default function AuditTable({ entries, sortKey, sortDir, onSort }) {
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No audit entries"
        description="Nothing matches the current filters. Try widening the result or action filter."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] font-mono text-text-muted border-b border-border">
            {COLUMNS.map((col) => (
              <th key={col.key} className="py-2.5 pr-4">
                <button
                  type="button"
                  onClick={() => onSort(col.key)}
                  className="flex items-center gap-1 hover:text-text transition-colors"
                >
                  {col.label}
                  {sortKey === col.key && <span>{sortDir === 'asc' ? '↑' : '↓'}</span>}
                </button>
              </th>
            ))}
            <th className="py-2.5 pr-4">Note</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => (
            <tr key={entry.id} className="border-b border-border/60 hover:bg-bg-s2/40">
              <td className="py-2.5 pr-4 text-text-muted whitespace-nowrap">{formatDate(entry.timestamp)}</td>
              <td className="py-2.5 pr-4">{entry.participant_name || entry.participant_id || '—'}</td>
              <td className="py-2.5 pr-4 font-mono text-text-muted">{entry.plan_id}</td>
              <td className="py-2.5 pr-4">{titleCase(entry.action)}</td>
              <td className="py-2.5 pr-4">
                <Badge tone={entry.result === 'approved' ? 'inactive' : entry.result === 'denied' ? 'active' : 'default'}>
                  {entry.result}
                </Badge>
              </td>
              <td className="py-2.5 pr-4 text-text-muted">{titleCase(entry.autonomy)}</td>
              <td className="py-2.5 pr-4 text-text-muted whitespace-nowrap">{entry.citation}</td>
              <td className="py-2.5 pr-4 text-text-muted max-w-xs">{entry.note}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
