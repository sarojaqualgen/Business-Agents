import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { PLAN_UPDATED_EVENT } from '../../../lib/events.js';
import Badge from '../../../components/ui/Badge.jsx';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleDateString('en-US', { dateStyle: 'medium' });
}

export default function BlackoutManager() {
  const { principal } = useAuth();
  const [plan, setPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [reason, setReason] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setIsLoading(true);
      const res = await apiClient.listPlans();
      const match = (res.plans || []).find((p) => p.plan_id === principal?.planId);
      setPlan(match || null);
      if (!silent) setIsLoading(false);
    },
    [principal?.planId],
  );

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onPlanUpdated(event) {
      if (event.detail?.planId === principal?.planId) {
        load({ silent: true });
      }
    }
    window.addEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
    return () => window.removeEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
  }, [principal?.planId, load]);

  async function handleActivate(e) {
    e.preventDefault();
    if (!principal?.planId || !startDate || !endDate) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient.activateBlackout({ planId: principal.planId, startDate, endDate, reason });
      setStartDate('');
      setEndDate('');
      setReason('');
      await load({ silent: true });
    } catch (err) {
      setError(err.message || 'Failed to activate blackout');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleDeactivate() {
    if (!principal?.planId) return;
    setIsSubmitting(true);
    setError(null);
    try {
      await apiClient.deactivateBlackout({ planId: principal.planId });
      await load({ silent: true });
    } catch (err) {
      setError(err.message || 'Failed to deactivate blackout');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading blackout status…" />;
  }

  if (!plan) {
    return (
      <EmptyState tone="error" icon="error" title="No plan found" description={`No plan record for ${principal?.planId || 'this session'}.`} />
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <p className="text-sm text-text-muted">
        Restrict participant transactions during a recordkeeper transition or other blackout period.
      </p>

      <div className="card p-5 sm:p-6">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-2">
          <h2 className="text-sm font-semibold text-text">Current Status</h2>
          <Badge tone={plan.blackout_active ? 'active' : 'inactive'}>
            {plan.blackout_active ? 'Blackout Active' : 'No Blackout'}
          </Badge>
        </div>
        <dl className="grid grid-cols-1 sm:grid-cols-2 gap-y-3 text-sm">
          <div className="flex justify-between sm:block">
            <dt className="text-text-muted">Plan</dt>
            <dd className="text-text font-mono">{plan.plan_id}</dd>
          </div>
          <div className="flex justify-between sm:block">
            <dt className="text-text-muted">Start Date</dt>
            <dd className="text-text">{formatDate(plan.blackout_start)}</dd>
          </div>
          <div className="flex justify-between sm:block">
            <dt className="text-text-muted">End Date</dt>
            <dd className="text-text">{formatDate(plan.blackout_end)}</dd>
          </div>
          <div className="flex justify-between sm:block">
            <dt className="text-text-muted">Reason</dt>
            <dd className="text-text">{plan.blackout_reason || '—'}</dd>
          </div>
        </dl>
        {!plan.blackout_active && (
          <div className="mt-4 pt-4 border-t border-border">
            <EmptyState
              title="No active blackout"
              description="Participant transactions are unrestricted. Activate a blackout below when a recordkeeper transition or other restricted period begins."
            />
          </div>
        )}
        {plan.blackout_active && (
          <button
            type="button"
            onClick={handleDeactivate}
            disabled={isSubmitting}
            className="mt-5 w-full sm:w-auto px-4 py-2 rounded-md text-[13px] font-medium bg-danger/10 text-danger border border-danger/25 hover:bg-danger/15 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Deactivating…' : 'Deactivate Blackout'}
          </button>
        )}
      </div>

      {!plan.blackout_active && (
        <form onSubmit={handleActivate} className="card p-5 sm:p-6 space-y-4">
          <h2 className="text-sm font-semibold text-text">Activate Blackout — ERISA §101(i)</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="label-mono">Start Date</span>
              <input
                type="date"
                className="input-field"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                required
              />
            </label>
            <label className="block">
              <span className="label-mono">End Date</span>
              <input
                type="date"
                className="input-field"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                required
              />
            </label>
          </div>
          <label className="block">
            <span className="label-mono">Reason</span>
            <input
              type="text"
              className="input-field"
              placeholder="e.g. Recordkeeper transition to Empower"
              value={reason}
              onChange={(e) => setReason(e.target.value)}
            />
          </label>
          {error && <p className="text-xs text-danger">{error}</p>}
          <button type="submit" disabled={isSubmitting} className="btn-primary w-full sm:w-auto px-5">
            {isSubmitting ? 'Activating…' : 'Activate Blackout'}
          </button>
        </form>
      )}
    </div>
  );
}
