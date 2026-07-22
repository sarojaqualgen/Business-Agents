import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../../lib/apiClient.js';
import { formatCurrency, formatDateTime, titleCase } from '../../../lib/format.js';

const ACTION_LABELS = {
  loan_initiation:         'Loan Initiated',
  hardship_distribution:   'Hardship Distribution',
  in_service_distribution: 'In-Service Distribution',
  separation_distribution: 'Separation Distribution',
  rmd:                     'Required Minimum Distribution',
  qdro:                    'QDRO Transfer',
  beneficiary_update:      'Beneficiary Update',
  deferral_change:         'Deferral Change',
  investment_reallocation: 'Investment Reallocation',
  address_update:          'Address Update',
};

const RESULT_STYLES = {
  full:         { label: 'Executed',     cls: 'bg-success/15 text-success' },
  supervised:   { label: 'Confirmed',    cls: 'bg-success/15 text-success' },
  human_review: { label: 'Queued',       cls: 'bg-warning/15 text-warning' },
  denied:       { label: 'Denied',       cls: 'bg-danger/15 text-danger' },
  executed:     { label: 'Executed',     cls: 'bg-success/15 text-success' },
  loan:         { label: 'Loan Active',  cls: 'bg-accent-light text-accent-dark' },
  cancelled:    { label: 'Cancelled',    cls: 'bg-bg-s2 text-text-muted' },
};

function resultBadge(event) {
  if (event.type === 'fap_decision' && !event.authorized) return RESULT_STYLES.denied;
  if (event.type === 'executed') return RESULT_STYLES.executed;
  if (event.type === 'loan')     return RESULT_STYLES.loan;
  // If participant cancelled this request after submission, show Cancelled regardless of autonomy level
  if (event.queue_status === 'cancelled') return RESULT_STYLES.cancelled;
  return RESULT_STYLES[event.autonomy_level] || { label: titleCase(event.autonomy_level || 'approved'), cls: 'bg-bg-s2 text-text-muted' };
}

const ALL_TYPES = ['all', 'loan_initiation', 'hardship_distribution', 'in_service_distribution',
  'separation_distribution', 'rmd', 'qdro', 'beneficiary_update', 'deferral_change',
  'investment_reallocation', 'address_update'];

export default function PlanActivityPage() {
  const [events, setEvents]     = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [filter, setFilter]     = useState('all');   // action type filter
  const [showDenied, setShowDenied] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    apiClient.getAdminPlanActivity()
      .then(d => setEvents(d.events || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-6 text-text-muted text-sm">Loading plan activity…</p>;
  if (error)   return <p className="p-6 text-danger text-sm">Error: {error}</p>;

  const visible = events.filter(e => {
    if (!showDenied && e.type === 'fap_decision' && !e.authorized) return false;
    if (filter !== 'all' && e.action !== filter) return false;
    return true;
  });

  return (
    <div className="p-6 space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-text-muted font-medium whitespace-nowrap">Action type</label>
          <select
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="text-sm border border-border rounded-md px-2 py-1.5 bg-bg-surface text-text focus:outline-none focus:ring-2 focus:ring-accent"
          >
            {ALL_TYPES.map(t => (
              <option key={t} value={t}>{t === 'all' ? 'All actions' : (ACTION_LABELS[t] || t)}</option>
            ))}
          </select>
        </div>

        <label className="flex items-center gap-2 text-sm text-text-muted cursor-pointer select-none">
          <input
            type="checkbox"
            checked={showDenied}
            onChange={e => setShowDenied(e.target.checked)}
            className="rounded accent-accent"
          />
          Show denied
        </label>

        <span className="ml-auto text-xs text-text-faint tabular-nums">
          {visible.length} event{visible.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Table */}
      {visible.length === 0 ? (
        <p className="text-sm text-text-muted">No events match the current filter.</p>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bg-s2 border-b border-border text-left text-text-muted font-medium">
                <th className="px-4 py-3 whitespace-nowrap">Date / Time</th>
                <th className="px-4 py-3">Participant</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Result</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3">Note / Denial Code</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {visible.map((e, i) => {
                const { label, cls } = resultBadge(e);
                return (
                  <tr
                    key={e.id || i}
                    onClick={() => navigate(`/sponsor/participants/${e.participant_id}`)}
                    className="hover:bg-accent-light/40 cursor-pointer transition-colors"
                  >
                    <td className="px-4 py-3 text-text-muted text-xs tabular-nums whitespace-nowrap">
                      {e.timestamp ? formatDateTime(e.timestamp) : '—'}
                    </td>
                    <td className="px-4 py-3 font-medium text-text">{e.participant_name}</td>
                    <td className="px-4 py-3 text-text">{ACTION_LABELS[e.action] || e.action}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${cls}`}>{label}</span>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">
                      {e.amount != null ? formatCurrency(e.amount) : '—'}
                    </td>
                    <td className="px-4 py-3 text-xs text-text-muted max-w-xs truncate">
                      {e.denial_code || e.note || e.erisa_citation || '—'}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
