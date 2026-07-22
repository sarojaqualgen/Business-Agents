import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { ACCOUNT_UPDATED_EVENT } from '../../../lib/events.js';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';
import Badge from '../../../components/ui/Badge.jsx';
import { formatCurrency } from '../../../lib/format.js';

const ACTION_LABELS = {
  loan_initiation:        'Loan',
  deferral_change:        'Deferral Change',
  investment_reallocation:'Investment Reallocation',
  address_update:         'Address Update',
  hardship_distribution:  'Hardship Withdrawal',
  in_service_distribution:'In-Service Distribution',
  separation_distribution:'Separation Distribution',
  beneficiary_update:     'Beneficiary Update',
  qdro:                   'QDRO',
  rmd:                    'RMD Distribution',
};

function actionLabel(action) {
  return ACTION_LABELS[action] || (action || '').replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}

const STATUS_MAP = {
  executed:       { tone: 'inactive', label: 'Executed' },
  denied:         { tone: 'active',   label: 'Denied' },
  pending_review: { tone: 'pending',  label: 'Pending Review' },
  awaiting_bank:  { tone: 'pending',  label: 'Awaiting Bank Details' },
  approved:       { tone: 'inactive', label: 'Approved' },
  disbursed:      { tone: 'inactive', label: 'Disbursed' },
  cancelled:      { tone: 'default',  label: 'Cancelled' },
  loan:           { tone: 'pending',  label: 'Active Loan' },
};

function statusBadge(type) {
  const { tone, label } = STATUS_MAP[type] || { tone: 'default', label: type };
  return <Badge tone={tone}>{label}</Badge>;
}

const ICON_COLORS = {
  loan_initiation:        'bg-blue-500/15 text-blue-600',
  deferral_change:        'bg-green-500/15 text-green-600',
  investment_reallocation:'bg-purple-500/15 text-purple-600',
  address_update:         'bg-slate-400/20 text-slate-500',
  hardship_distribution:  'bg-orange-500/15 text-orange-600',
  in_service_distribution:'bg-orange-500/15 text-orange-600',
  separation_distribution:'bg-red-500/15 text-red-600',
  beneficiary_update:     'bg-teal-500/15 text-teal-600',
  qdro:                   'bg-red-500/15 text-red-600',
  rmd:                    'bg-yellow-500/15 text-yellow-700',
};

const FILTER_TABS = [
  { key: 'all',            label: 'All' },
  { key: 'executed',       label: 'Executed' },
  { key: 'loan',           label: 'Loans' },
  { key: 'awaiting_bank',  label: 'Awaiting Bank' },
  { key: 'pending_review', label: 'Pending Review' },
  { key: 'denied',         label: 'Denied' },
];

function formatTimestamp(ts) {
  if (!ts) return '—';
  const d = new Date(ts);
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) +
    ' · ' + d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
}

// Inline bank details form — used for both loans (supervised) and hardship (human_review)
function InlineBankForm({ item, onSuccess, onCancel }) {
  const [routing, setRouting] = useState('');
  const [account, setAccount] = useState('');
  const [accountType, setAccountType] = useState('checking');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  const routingValid = /^\d{9}$/.test(routing);
  const canSubmit = routingValid && account.trim().length >= 4 && !isSubmitting;

  async function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    setIsSubmitting(true);
    setError(null);
    try {
      const res = await apiClient.disburseFunds({
        routingNumber: routing,
        accountNumber: account.trim(),
        accountType,
        entryId: item.entry_id || undefined,
      });
      const msg = res.disbursement
        ? `Disbursement initiated — funds arrive in ${res.disbursement.estimated_arrival} to account ending in ${res.disbursement.account_last4}.`
        : 'Bank details submitted. Disbursement is being processed.';
      setSuccess(msg);
      onSuccess();
    } catch (err) {
      setError(err.message || 'Submission failed. Please try again.');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (success) {
    return (
      <div className="mt-3 p-3 rounded-lg bg-success/8 border border-success/25">
        <p className="text-xs text-success font-medium">{success}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-3 p-3 rounded-lg bg-warning/5 border border-warning/25 space-y-3">
      <p className="text-xs font-medium text-warning">
        Bank details required to receive funds
      </p>

      <div className="grid grid-cols-2 gap-2">
        <div>
          <label className="label-mono text-[10px]">Routing number (9 digits)</label>
          <input
            type="text"
            inputMode="numeric"
            maxLength={9}
            value={routing}
            onChange={(e) => setRouting(e.target.value.replace(/\D/g, '').slice(0, 9))}
            placeholder="021000021"
            className={['input-field text-sm font-mono', routing && !routingValid ? 'border-danger' : ''].join(' ')}
            disabled={isSubmitting}
          />
          {routing && !routingValid && (
            <p className="text-[10px] text-danger mt-0.5">Must be 9 digits</p>
          )}
        </div>
        <div>
          <label className="label-mono text-[10px]">Account number</label>
          <input
            type="text"
            inputMode="numeric"
            value={account}
            onChange={(e) => setAccount(e.target.value.replace(/\D/g, ''))}
            placeholder="000123456789"
            className="input-field text-sm font-mono"
            disabled={isSubmitting}
          />
        </div>
      </div>

      <div>
        <label className="label-mono text-[10px]">Account type</label>
        <select
          value={accountType}
          onChange={(e) => setAccountType(e.target.value)}
          className="input-field text-sm"
          disabled={isSubmitting}
        >
          <option value="checking">Checking</option>
          <option value="savings">Savings</option>
        </select>
      </div>

      {error && <p className="text-xs text-danger">{error}</p>}

      <div className="flex gap-2">
        <button
          type="submit"
          disabled={!canSubmit}
          className="px-3 py-1.5 rounded-md text-xs font-medium bg-accent text-white hover:bg-accent-dark transition-colors disabled:opacity-50"
        >
          {isSubmitting ? 'Submitting…' : 'Submit Bank Details'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isSubmitting}
          className="px-3 py-1.5 rounded-md text-xs font-medium text-text-muted hover:text-text border border-border transition-colors"
        >
          Cancel
        </button>
      </div>
    </form>
  );
}

export default function Activity() {
  const { principal } = useAuth();
  const [activities, setActivities] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [bankFormOpen, setBankFormOpen] = useState(null);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await apiClient.getParticipantActivity(principal?.participantId);
      setActivities(res.activities || []);
    } catch {
      setActivities([]);
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, [principal?.participantId]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    function onUpdate(event) {
      if (event.detail?.participantId === principal?.participantId) load({ silent: true });
    }
    window.addEventListener(ACCOUNT_UPDATED_EVENT, onUpdate);
    return () => window.removeEventListener(ACCOUNT_UPDATED_EVENT, onUpdate);
  }, [principal?.participantId, load]);

  // Auto-open bank form if there's exactly one awaiting_bank item
  useEffect(() => {
    const pending = activities.filter((a) => a.type === 'awaiting_bank');
    if (pending.length === 1 && !bankFormOpen) {
      setBankFormOpen(pending[0].entry_id || pending[0].id);
    }
  }, [activities]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = filter === 'all' ? activities : activities.filter((a) => a.type === filter);

  if (isLoading) return <LoadingState label="Loading your activity history…" />;

  return (
    <div className="max-w-2xl space-y-5">
      {/* Filter tabs */}
      <div className="flex items-center gap-1 flex-wrap border-b border-border pb-3">
        {FILTER_TABS.map((tab) => {
          const count = tab.key === 'all' ? activities.length : activities.filter((a) => a.type === tab.key).length;
          if (tab.key !== 'all' && count === 0) return null;
          const isActive = filter === tab.key;
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setFilter(tab.key)}
              className={[
                'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-colors',
                isActive ? 'bg-accent-light text-accent-dark' : 'text-text-muted hover:text-text hover:bg-bg-s2',
              ].join(' ')}
            >
              {tab.label}
              {count > 0 && (
                <span className={[
                  'text-[10px] px-1.5 py-0.5 rounded-full tabular-nums',
                  isActive ? 'bg-accent/20 text-accent-dark' : 'bg-bg-s2 text-text-faint',
                ].join(' ')}>
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          tone="default"
          icon="info"
          title={filter === 'all' ? 'No activity yet' : `No ${filter.replace(/_/g, ' ')} actions`}
          description={
            filter === 'all'
              ? 'Your transactions and compliance decisions will appear here as you use the plan.'
              : 'Switch to "All" to see everything.'
          }
        />
      ) : (
        <div className="space-y-2">
          {filtered.map((item) => {
            const itemKey = item.entry_id || item.id;
            const bankOpen = bankFormOpen === itemKey;
            const isAwaitingBank = item.type === 'awaiting_bank';

            return (
              <div
                key={item.id}
                className={[
                  'card p-4 transition-shadow',
                  isAwaitingBank ? 'border-warning/40 shadow-sm' : 'hover:shadow-card-hover',
                ].join(' ')}
              >
                <div className="flex items-start gap-3.5">
                  {/* Action icon */}
                  <div className={[
                    'w-9 h-9 rounded-full flex items-center justify-center text-[11px] font-bold flex-shrink-0 mt-0.5',
                    ICON_COLORS[item.action] || 'bg-bg-s2 text-text-muted',
                  ].join(' ')}>
                    {actionLabel(item.action).slice(0, 2).toUpperCase()}
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div>
                        <p className="text-sm font-medium text-text leading-snug">
                          {item.label || actionLabel(item.action)}
                        </p>
                        {item.amount != null && (
                          <p className="text-[13px] text-text-muted tabular-nums mt-0.5">
                            {formatCurrency(item.amount)}
                            {item.outstanding != null && item.type === 'loan' && (
                              <span className="ml-2 text-[11px] text-text-faint">
                                ({formatCurrency(item.outstanding)} outstanding)
                              </span>
                            )}
                          </p>
                        )}
                      </div>
                      {statusBadge(item.type)}
                    </div>

                    {item.denial_code && (
                      <p className="text-[11px] font-mono text-danger/70 mt-1">{item.denial_code}</p>
                    )}
                    {item.entry_id && !isAwaitingBank && (
                      <p className="text-[11px] text-text-faint font-mono mt-1">Entry {item.entry_id}</p>
                    )}

                    <p className="text-[11px] text-text-faint mt-2">{formatTimestamp(item.timestamp)}</p>


                    {/* Bank details CTA */}
                    {isAwaitingBank && !bankOpen && (
                      <button
                        type="button"
                        onClick={() => setBankFormOpen(itemKey)}
                        className="mt-3 px-3 py-1.5 rounded-md text-xs font-medium bg-warning text-white hover:bg-warning/80 transition-colors"
                      >
                        Provide Bank Details
                      </button>
                    )}

                    {/* Inline bank form */}
                    {isAwaitingBank && bankOpen && (
                      <InlineBankForm
                        item={item}
                        onSuccess={() => {
                          setBankFormOpen(null);
                          load({ silent: true });
                        }}
                        onCancel={() => setBankFormOpen(null)}
                      />
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
