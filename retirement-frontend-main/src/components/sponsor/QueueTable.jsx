import React from 'react';
import EmptyState from '../ui/EmptyState.jsx';
import { formatCurrency, titleCase } from '../../lib/format.js';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
}

// Maps raw status → { label, classes } for inline badge rendering
const STATUS_STYLES = {
  pending: {
    label: 'Pending',
    classes: 'bg-warning/15 text-warning border-warning/30',
  },
  approved_awaiting_bank_details: {
    label: 'Awaiting Bank',
    classes: 'bg-blue-500/15 text-blue-600 border-blue-500/30',
  },
  approved: {
    label: 'Approved',
    classes: 'bg-success/15 text-success border-success/30',
  },
  denied: {
    label: 'Denied',
    classes: 'bg-danger/15 text-danger border-danger/30',
  },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || { label: status, classes: 'bg-bg-s2 text-text-muted border-border-strong' };
  return (
    <span className={`inline-flex items-center px-2.5 py-1 rounded-full text-[11px] font-medium border whitespace-nowrap ${s.classes}`}>
      {s.label}
    </span>
  );
}

export default function QueueTable({ entries, onApprove, onDeny, onViewDocs }) {
  if (entries.length === 0) {
    return (
      <EmptyState
        title="No queue entries"
        description="Nothing matches the current filters. Try widening the status or action filter."
      />
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-[11px] font-mono text-text-muted border-b border-border">
            <th className="py-2.5 pr-4">Entry</th>
            <th className="py-2.5 pr-4">Participant</th>
            <th className="py-2.5 pr-4">Action</th>
            <th className="py-2.5 pr-4">Amount</th>
            <th className="py-2.5 pr-4">Docs</th>
            <th className="py-2.5 pr-4">Submitted</th>
            <th className="py-2.5 pr-4">Status</th>
            <th className="py-2.5 pr-4 text-right">Decision</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isPending = entry.status === 'pending';
            const isResolved = ['approved', 'denied'].includes(entry.status);
            const amount = entry.amount ?? entry.payload?.amount;

            return (
              <tr key={entry.entry_id} className="border-b border-border/60 hover:bg-bg-s2/40 align-top">
                <td className="py-3 pr-4">
                  <p className="font-mono text-[11px] text-text-muted">{entry.entry_id}</p>
                  <p className="font-mono text-[10px] text-text-faint">{entry.plan_id}</p>
                </td>
                <td className="py-3 pr-4 font-mono text-[12px]">{entry.participant_id}</td>
                <td className="py-3 pr-4">{titleCase(entry.action)}</td>
                <td className="py-3 pr-4 tabular-nums">
                  {amount != null ? formatCurrency(amount) : '—'}
                </td>
                <td className="py-3 pr-4">
                  {entry.doc_count > 0 ? (
                    <button
                      type="button"
                      onClick={() => onViewDocs(entry)}
                      className="inline-flex items-center gap-1 px-2 py-1 rounded text-xs font-medium bg-accent/10 text-accent border border-accent/25 hover:bg-accent/20 transition-colors whitespace-nowrap"
                    >
                      {entry.doc_count} doc{entry.doc_count !== 1 ? 's' : ''}
                      {entry.docs_sponsor_approved > 0 && (
                        <span className="text-success text-[10px] font-bold">✓</span>
                      )}
                    </button>
                  ) : (
                    <span className="text-text-faint text-xs">—</span>
                  )}
                </td>
                <td className="py-3 pr-4 text-[11px] text-text-muted whitespace-nowrap">
                  {formatDate(entry.submitted_at)}
                </td>
                <td className="py-3 pr-4">
                  <StatusBadge status={entry.status} />
                </td>
                <td className="py-3 pr-4 text-right">
                  {isPending ? (
                    <div className="flex gap-2 justify-end">
                      <button
                        type="button"
                        onClick={() => onApprove(entry)}
                        className="px-3 py-1.5 rounded-md text-xs font-medium bg-success/15 text-success border border-success/30 hover:bg-success/25 transition-colors"
                      >
                        Approve
                      </button>
                      <button
                        type="button"
                        onClick={() => onDeny(entry)}
                        className="px-3 py-1.5 rounded-md text-xs font-medium bg-danger/15 text-danger border border-danger/30 hover:bg-danger/25 transition-colors"
                      >
                        Deny
                      </button>
                    </div>
                  ) : isResolved ? (
                    <div className="text-right">
                      {entry.resolution_note && entry.resolution_note !== 'Disbursed' ? (
                        <p className="text-[11px] text-text-muted max-w-[180px] ml-auto">{entry.resolution_note}</p>
                      ) : (
                        <p className="text-[11px] text-text-faint italic">
                          {entry.resolution_note === 'Disbursed' ? 'Funds disbursed' : 'No note'}
                        </p>
                      )}
                      {entry.resolved_at && (
                        <p className="text-[10px] text-text-faint font-mono mt-0.5">{formatDate(entry.resolved_at)}</p>
                      )}
                    </div>
                  ) : (
                    <span className="text-[11px] text-text-faint italic">Awaiting participant</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
