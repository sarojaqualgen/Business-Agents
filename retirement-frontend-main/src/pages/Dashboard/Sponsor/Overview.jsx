import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { PLAN_UPDATED_EVENT, QUEUE_UPDATED_EVENT } from '../../../lib/events.js';
import StatCard from '../../../components/ui/StatCard.jsx';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';

function ResetDemoButton({ onReset }) {
  const [state, setState] = useState('idle'); // idle | confirming | resetting | done | error
  const [error, setError] = useState(null);

  async function handleReset() {
    if (state === 'idle') { setState('confirming'); return; }
    if (state === 'confirming') {
      setState('resetting');
      setError(null);
      try {
        await apiClient.resetDemo();
        setState('done');
        // Force a full page reload after 1.5s so ALL React state (activity caches,
        // pending panels, etc.) is wiped across every page — not just this component.
        setTimeout(() => { window.location.reload(); }, 1500);
      } catch (err) {
        setError(err.message || 'Reset failed');
        setState('error');
        setTimeout(() => setState('idle'), 3000);
      }
    }
  }

  if (state === 'done') {
    return <span className="text-xs text-success font-medium">Demo reset — all clear.</span>;
  }
  if (state === 'error') {
    return <span className="text-xs text-danger">{error}</span>;
  }

  return (
    <div className="flex items-center gap-2">
      {state === 'confirming' && (
        <span className="text-xs text-warning">This wipes all requests, audit entries and docs. Sure?</span>
      )}
      <button
        type="button"
        onClick={handleReset}
        disabled={state === 'resetting'}
        className={[
          'px-3 py-1.5 rounded-md text-xs font-medium transition-colors disabled:opacity-50',
          state === 'confirming'
            ? 'bg-danger text-white hover:bg-danger/80'
            : 'bg-bg-s2 border border-border text-text-muted hover:border-danger hover:text-danger',
        ].join(' ')}
      >
        {state === 'resetting' ? 'Resetting…' : state === 'confirming' ? 'Yes, reset everything' : 'Reset Demo State'}
      </button>
      {state === 'confirming' && (
        <button
          type="button"
          onClick={() => setState('idle')}
          className="text-xs text-text-faint hover:text-text transition-colors"
        >
          Cancel
        </button>
      )}
    </div>
  );
}

// How often the overview silently re-checks plan/queue data, in addition to
// refreshing immediately whenever a sponsor workflow (approve, deny,
// blackout activate/deactivate) writes to the mock database.
const AUTO_REFRESH_MS = 15000;

export default function Overview() {
  const { principal } = useAuth();
  const [plan, setPlan] = useState(null);
  const [participantCount, setParticipantCount] = useState(0);
  const [pendingCount, setPendingCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setIsLoading(true);
      try {
        const [plansRes, participantsRes, queueRes] = await Promise.all([
          apiClient.listPlans(),
          apiClient.listParticipants(),
          apiClient.getQueue(),
        ]);
        const match = (plansRes.plans || []).find((p) => p.plan_id === principal?.planId);
        setPlan(match || null);
        setParticipantCount(
          (participantsRes.participants || []).filter((p) => p.plan_id === principal?.planId).length,
        );
        setPendingCount(
          (queueRes.entries || []).filter((e) => e.plan_id === principal?.planId && e.status === 'pending').length,
        );
      } catch {
        // API error — leave existing state, stop spinner
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [principal?.planId],
  );

  useEffect(() => {
    load();
  }, [load]);

  // Auto-refresh: react immediately to any queue decision or blackout
  // change for this plan, plus a light polling interval as a fallback.
  useEffect(() => {
    if (!principal?.planId) return undefined;

    function onPlanUpdated(event) {
      if (event.detail?.planId === principal.planId) load({ silent: true });
    }
    function onQueueUpdated() {
      load({ silent: true });
    }

    window.addEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
    window.addEventListener(QUEUE_UPDATED_EVENT, onQueueUpdated);
    const interval = setInterval(() => load({ silent: true }), AUTO_REFRESH_MS);

    return () => {
      window.removeEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
      window.removeEventListener(QUEUE_UPDATED_EVENT, onQueueUpdated);
      clearInterval(interval);
    };
  }, [principal?.planId, load]);

  if (isLoading) {
    return <LoadingState label="Loading plan summary…" />;
  }

  if (!plan) {
    return (
      <EmptyState tone="error" icon="error" title="No plan found" description={`No plan record for ${principal?.planId || 'this session'}.`} />
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <p className="text-sm text-text-muted">Overview of {plan.plan_name}.</p>
        <ResetDemoButton onReset={() => load({ silent: true })} />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <StatCard label="Participants" value={participantCount} />
        <Link to="queue" className="block">
          <StatCard label="Pending Queue Items" value={pendingCount} hint="Go to Review Queue" />
        </Link>
        <StatCard label="Blackout Status" value={plan.blackout_active ? 'Active' : 'Inactive'} />
        <StatCard label="Loans Permitted" value={plan.loans_permitted ? 'Yes' : 'No'} />
      </div>

      <div className="card p-4 sm:p-6">
        <h2 className="text-sm font-semibold text-text mb-4">Plan Details</h2>
        <dl className="grid grid-cols-2 gap-y-3 text-sm">
          <dt className="text-text-muted">Plan ID</dt>
          <dd className="text-text font-mono">{plan.plan_id}</dd>
          <dt className="text-text-muted">Plan Name</dt>
          <dd className="text-text">{plan.plan_name}</dd>
          <dt className="text-text-muted">Plan Type</dt>
          <dd className="text-text">{plan.plan_type}</dd>
          <dt className="text-text-muted">Hardship Permitted</dt>
          <dd className="text-text">{plan.hardship_permitted ? 'Yes' : 'No'}</dd>
        </dl>
      </div>
    </div>
  );
}
