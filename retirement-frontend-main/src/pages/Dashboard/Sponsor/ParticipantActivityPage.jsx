import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { apiClient } from '../../../lib/apiClient.js';
import { formatCurrency, formatDateTime } from '../../../lib/format.js';

const ACTION_LABELS = {
  loan_initiation:        'Loan Initiated',
  hardship_distribution:  'Hardship Distribution',
  in_service_distribution:'In-Service Distribution',
  separation_distribution:'Separation Distribution',
  rmd:                    'Required Minimum Distribution',
  qdro:                   'QDRO Transfer',
  beneficiary_update:     'Beneficiary Update',
  deferral_change:        'Deferral Change',
  investment_reallocation:'Investment Reallocation',
  address_update:         'Address Update',
};

const AUTONOMY_BADGE = {
  full:         'bg-success/15 text-success',
  supervised:   'bg-accent-light text-accent-dark',
  human_review: 'bg-warning/15 text-warning',
};

function EventRow({ event }) {
  const label = ACTION_LABELS[event.action] || event.action;

  // Determine status text and colour
  let statusText, statusClass;
  if (event.type === 'fap_decision') {
    if (event.queue_status === 'cancelled') {
      statusText  = 'cancelled';
      statusClass = 'bg-bg-s2 text-text-muted';
    } else if (event.authorized) {
      statusText  = event.autonomy_level ? event.autonomy_level.replace('_', ' ') : 'approved';
      statusClass = AUTONOMY_BADGE[event.autonomy_level] || 'bg-success/15 text-success';
    } else {
      statusText  = 'denied';
      statusClass = 'bg-danger/15 text-danger';
    }
  } else if (event.type === 'loan') {
    statusText  = event.status || 'active';
    statusClass = event.status === 'active' ? 'bg-accent-light text-accent-dark' : 'bg-bg-s2 text-text-muted';
  } else {
    statusText  = 'executed';
    statusClass = 'bg-success/15 text-success';
  }

  return (
    <tr className="border-b border-border last:border-0">
      <td className="px-4 py-3 text-text-muted text-xs tabular-nums whitespace-nowrap">
        {event.timestamp ? formatDateTime(event.timestamp) : '—'}
      </td>
      <td className="px-4 py-3 font-medium text-text">{label}</td>
      <td className="px-4 py-3">
        <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${statusClass}`}>
          {statusText}
        </span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-sm">
        {event.amount != null ? formatCurrency(event.amount) : '—'}
      </td>
      <td className="px-4 py-3 text-xs text-text-muted max-w-xs truncate">
        {event.type === 'fap_decision' && !event.authorized
          ? (event.denial_code || '—')
          : (event.note || event.erisa_citation || '—')}
      </td>
    </tr>
  );
}

export default function ParticipantActivityPage() {
  const { participantId } = useParams();
  const navigate = useNavigate();
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState(null);

  useEffect(() => {
    apiClient.getAdminParticipantActivity(participantId)
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [participantId]);

  if (loading) return <p className="p-6 text-text-muted text-sm">Loading activity…</p>;
  if (error)   return <p className="p-6 text-danger text-sm">Error: {error}</p>;

  const { name, employment_status, vested_balance, total_balance, events = [] } = data;

  const denied   = events.filter(e => e.type === 'fap_decision' && !e.authorized).length;
  const approved = events.filter(e => e.type === 'fap_decision' &&  e.authorized).length;
  const executed = events.filter(e => e.type === 'executed').length;

  return (
    <div className="p-6 space-y-5">
      {/* Back link */}
      <button
        onClick={() => navigate('/sponsor/participants')}
        className="text-sm text-accent hover:underline flex items-center gap-1"
      >
        ← All Participants
      </button>

      {/* Participant summary bar */}
      <div className="rounded-lg border border-border bg-bg-surface p-4 flex flex-wrap gap-6">
        <div>
          <div className="text-xs text-text-muted mb-0.5">Participant</div>
          <div className="font-semibold text-text">{name}</div>
        </div>
        <div>
          <div className="text-xs text-text-muted mb-0.5">Status</div>
          <div className="font-medium text-text capitalize">{employment_status}</div>
        </div>
        <div>
          <div className="text-xs text-text-muted mb-0.5">Vested Balance</div>
          <div className="font-semibold text-text tabular-nums">{formatCurrency(vested_balance)}</div>
        </div>
        <div>
          <div className="text-xs text-text-muted mb-0.5">Total Balance</div>
          <div className="font-semibold text-text tabular-nums">{formatCurrency(total_balance)}</div>
        </div>
        <div className="ml-auto flex gap-4 text-center self-center">
            <div><div className="text-lg font-bold text-success">{approved}</div><div className="text-xs text-text-muted">Approved</div></div>
          <div><div className="text-lg font-bold text-danger">{denied}</div><div className="text-xs text-text-muted">Denied</div></div>
          <div><div className="text-lg font-bold text-accent-dark">{executed}</div><div className="text-xs text-text-muted">Executed</div></div>
        </div>
      </div>

      {/* Activity table */}
      {events.length === 0 ? (
        <p className="text-sm text-text-muted">No activity recorded for this participant yet.</p>
      ) : (
        <div className="rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-bg-s2 border-b border-border text-left text-text-muted font-medium">
                <th className="px-4 py-3 whitespace-nowrap">Date / Time</th>
                <th className="px-4 py-3">Action</th>
                <th className="px-4 py-3">Result</th>
                <th className="px-4 py-3 text-right">Amount</th>
                <th className="px-4 py-3">Note / Code</th>
              </tr>
            </thead>
            <tbody>
              {events.map((e, i) => <EventRow key={e.id || i} event={e} />)}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
