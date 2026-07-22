import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { apiClient } from '../../../lib/apiClient.js';
import { formatCurrency } from '../../../lib/format.js';

const STATUS_BADGE = {
  active:     'bg-success/15 text-success',
  terminated: 'bg-danger/15 text-danger',
  retired:    'bg-warning/15 text-warning',
};

export default function ParticipantsPage() {
  const [participants, setParticipants] = useState([]);
  const [loading, setLoading]           = useState(true);
  const [error, setError]               = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    apiClient.getAdminParticipants()
      .then(d => setParticipants(d.participants || []))
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-6 text-text-muted text-sm">Loading participants…</p>;
  if (error)   return <p className="p-6 text-danger text-sm">Error: {error}</p>;

  return (
    <div className="p-6 space-y-4">
      <p className="text-sm text-text-muted">{participants.length} participant{participants.length !== 1 ? 's' : ''} enrolled in this plan. Click a row to see their full activity.</p>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-bg-s2 border-b border-border text-left text-text-muted font-medium">
              <th className="px-4 py-3">Name</th>
              <th className="px-4 py-3">Status</th>
              <th className="px-4 py-3 text-right">Vested Balance</th>
              <th className="px-4 py-3 text-right">Total Balance</th>
              <th className="px-4 py-3 text-right">Deferral %</th>
              <th className="px-4 py-3">RMD Required</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {participants.map(p => (
              <tr
                key={p.participant_id}
                onClick={() => navigate(`/sponsor/participants/${p.participant_id}`)}
                className="hover:bg-accent-light/40 cursor-pointer transition-colors"
              >
                <td className="px-4 py-3 font-medium text-text">{p.name}</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${STATUS_BADGE[p.employment_status] || 'bg-bg-s2 text-text-muted'}`}>
                    {p.employment_status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(p.vested_balance)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{formatCurrency(p.total_balance)}</td>
                <td className="px-4 py-3 text-right tabular-nums">{p.current_deferral_pct}%</td>
                <td className="px-4 py-3">
                  <span className={`inline-block px-2 py-0.5 rounded text-xs font-medium ${p.rmd_required ? 'bg-warning/15 text-warning' : 'bg-bg-s2 text-text-faint'}`}>
                    {p.rmd_required ? 'Yes' : 'No'}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
