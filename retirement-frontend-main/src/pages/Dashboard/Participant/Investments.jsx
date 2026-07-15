import React, { useCallback, useEffect, useState } from 'react';
import { apiClient, ApiError } from '../../../lib/apiClient.js';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';
import { ACCOUNT_UPDATED_EVENT } from '../../../lib/events.js';

// Percent input component — keyboard-friendly, clamped to 0–100 whole numbers
function PctInput({ value, onChange, disabled }) {
  return (
    <div className="flex items-center gap-1 w-24">
      <input
        type="number"
        min={0}
        max={100}
        step={1}
        value={value === 0 ? '' : value}
        placeholder="0"
        disabled={disabled}
        onChange={(e) => {
          const v = Math.min(100, Math.max(0, parseInt(e.target.value, 10) || 0));
          onChange(v);
        }}
        className="input-field text-right pr-1 py-1.5 text-sm w-16 disabled:opacity-50"
      />
      <span className="text-sm text-text-muted">%</span>
    </div>
  );
}

const ASSET_CLASS_COLORS = {
  'Target Date':           'bg-purple/10 text-purple',
  'US Large Cap Equity':   'bg-accent-light text-accent-dark',
  'International Equity':  'bg-blue-100 text-blue-700',
  'Fixed Income':          'bg-green-50 text-green-700',
  'Stable Value':          'bg-gray-100 text-gray-600',
  'Company Stock':         'bg-yellow-50 text-yellow-700',
  'US Mid/Small Cap Equity': 'bg-orange-50 text-orange-700',
};

function AssetBadge({ assetClass }) {
  const cls = ASSET_CLASS_COLORS[assetClass] || 'bg-bg-s3 text-text-muted';
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-medium ${cls}`}>
      {assetClass}
    </span>
  );
}

function AllocationBar({ pct, color = 'bg-accent' }) {
  return (
    <div className="w-full h-1.5 bg-bg-s3 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full transition-all duration-300 ${color}`}
        style={{ width: `${Math.min(100, pct)}%` }}
      />
    </div>
  );
}

export default function Investments() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Local draft allocations: {fund_id → pct (0–100 integer)}
  const [draft, setDraft] = useState({});
  const [scope, setScope] = useState('both');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState(null); // null | { ok: true } | { ok: false, msg }
  const [showSuccess, setShowSuccess] = useState(false);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.getParticipantInvestments();
      setData(res);
      // Seed draft from current elections
      const map = {};
      for (const e of res.current_elections) {
        map[e.fund_id] = Math.round(e.allocation_pct * 100);
      }
      // Fill zeros for funds not yet in elections
      for (const f of res.fund_lineup) {
        if (!(f.fund_id in map)) map[f.fund_id] = 0;
      }
      setDraft(map);
    } catch (err) {
      setError(err.message || 'Failed to load investments');
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const totalPct = Object.values(draft).reduce((s, v) => s + v, 0);
  const isBalanced = totalPct === 100;
  const remaining = 100 - totalPct;

  function setFundPct(fundId, pct) {
    setDraft((prev) => ({ ...prev, [fundId]: pct }));
    setSubmitResult(null);
  }

  function resetToCurrentAllocations() {
    if (!data) return;
    const map = {};
    for (const e of data.current_elections) {
      map[e.fund_id] = Math.round(e.allocation_pct * 100);
    }
    for (const f of data.fund_lineup) {
      if (!(f.fund_id in map)) map[f.fund_id] = 0;
    }
    setDraft(map);
    setSubmitResult(null);
  }

  async function handleSubmit() {
    if (!isBalanced || isSubmitting) return;

    setIsSubmitting(true);
    setSubmitResult(null);

    const elections = Object.entries(draft)
      .filter(([, pct]) => pct > 0)
      .map(([fund_id, pct]) => ({ fund_id, allocation_pct: pct / 100 }));

    try {
      await apiClient.reallocateFunds({ scope, elections });
      setSubmitResult({ ok: true });
      setShowSuccess(true);
      window.dispatchEvent(new CustomEvent(ACCOUNT_UPDATED_EVENT, {
        detail: { participantId: data?.participant_id },
      }));
      // Refresh from backend after a beat
      setTimeout(() => load({ silent: true }), 800);
      setTimeout(() => setShowSuccess(false), 4000);
    } catch (err) {
      setSubmitResult({ ok: false, msg: err.message || 'Reallocation failed' });
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) return <LoadingState label="Loading your investment elections…" />;

  if (error) {
    return (
      <EmptyState
        tone="error"
        icon="error"
        title="Could not load investments"
        description={error}
      />
    );
  }

  if (!data) return null;

  const isBlackout = data.blackout_active;

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-[20px] font-bold text-text leading-tight">Investment Reallocation</h1>
        <p className="text-sm text-text-muted mt-1">
          Adjust how your account balance and future contributions are invested across the fund lineup.
          FAP compliance runs automatically — changes execute immediately.
        </p>
      </div>

      {isBlackout && (
        <div className="card p-4 border-warning/30 bg-warning/5">
          <p className="text-sm text-warning font-medium">
            A plan blackout is active. Investment elections cannot be changed during this period.
          </p>
        </div>
      )}

      {/* Scope selector */}
      <div className="card p-5">
        <p className="text-[11px] font-mono text-text-muted mb-3 uppercase tracking-wide">Apply changes to</p>
        <div className="flex flex-wrap gap-2">
          {[
            { value: 'both',         label: 'Balance + Future contributions' },
            { value: 'balance_only', label: 'Current balance only' },
            { value: 'future_only',  label: 'Future contributions only' },
          ].map((opt) => (
            <button
              key={opt.value}
              type="button"
              disabled={isBlackout}
              onClick={() => setScope(opt.value)}
              className={[
                'px-3 py-1.5 rounded-md text-[13px] font-medium border transition-colors duration-150',
                scope === opt.value
                  ? 'bg-accent text-white border-accent shadow-sm'
                  : 'bg-bg-s2 text-text-muted border-border-strong hover:border-accent/40 hover:text-text',
                'disabled:opacity-50 disabled:cursor-not-allowed',
              ].join(' ')}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {/* Fund allocation table */}
      <div className="card overflow-hidden">
        <div className="px-5 py-4 border-b border-border flex items-center justify-between">
          <p className="text-[13px] font-semibold text-text">Fund Lineup · {data.fund_lineup.length} funds</p>
          {/* Allocation meter */}
          <div className="flex items-center gap-2">
            <div
              className={[
                'text-sm font-mono font-semibold tabular-nums',
                totalPct > 100 ? 'text-danger' : isBalanced ? 'text-success' : 'text-warning',
              ].join(' ')}
            >
              {totalPct}%
            </div>
            <div className="text-[11px] text-text-faint">
              {isBalanced ? 'Ready' : totalPct > 100 ? `−${totalPct - 100}% over` : `+${remaining}% left`}
            </div>
          </div>
        </div>

        {/* Total allocation bar */}
        <div className="h-1.5 w-full bg-bg-s3">
          <div
            className={[
              'h-full transition-all duration-300',
              totalPct > 100 ? 'bg-danger' : isBalanced ? 'bg-success' : 'bg-accent',
            ].join(' ')}
            style={{ width: `${Math.min(100, totalPct)}%` }}
          />
        </div>

        <div className="divide-y divide-border">
          {data.fund_lineup.map((fund) => {
            const currentPct = Math.round(fund.current_pct * 100);
            const newPct = draft[fund.fund_id] ?? 0;
            const changed = newPct !== currentPct;

            return (
              <div key={fund.fund_id} className="px-5 py-4 flex items-center gap-4">
                {/* Fund info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-[13px] font-semibold text-text truncate">{fund.fund_name}</span>
                    {fund.is_qdia && (
                      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[9px] font-bold bg-accent text-white uppercase tracking-wide flex-shrink-0">
                        QDIA
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2 flex-wrap">
                    <AssetBadge assetClass={fund.asset_class} />
                    {fund.ticker && (
                      <span className="text-[11px] font-mono text-text-faint">{fund.ticker}</span>
                    )}
                    <span className="text-[11px] text-text-faint">
                      {(fund.expense_ratio * 100).toFixed(2)}% exp
                    </span>
                  </div>

                  {/* Current vs new bar */}
                  <div className="mt-2.5 space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-text-faint w-16 text-right">Current</span>
                      <div className="flex-1">
                        <AllocationBar pct={currentPct} color="bg-border-strong" />
                      </div>
                      <span className="text-[11px] font-mono text-text-faint w-8 text-right">{currentPct}%</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] font-mono text-text-faint w-16 text-right">New</span>
                      <div className="flex-1">
                        <AllocationBar
                          pct={newPct}
                          color={newPct > 0 ? (changed ? 'bg-accent' : 'bg-success') : 'bg-bg-s3'}
                        />
                      </div>
                      <span className={['text-[11px] font-mono w-8 text-right', changed ? 'text-accent-dark font-semibold' : 'text-text-faint'].join(' ')}>
                        {newPct}%
                      </span>
                    </div>
                  </div>
                </div>

                {/* Input */}
                <div className="flex-shrink-0">
                  <PctInput
                    value={newPct}
                    onChange={(v) => setFundPct(fund.fund_id, v)}
                    disabled={isBlackout}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Submit section — swaps to success banner after apply */}
      {showSuccess ? (
        <div className="card p-5 border-success/30 bg-success/5 flex items-center gap-4">
          <div className="w-10 h-10 rounded-full bg-success/20 text-success flex items-center justify-center text-lg font-bold flex-shrink-0">
            ✓
          </div>
          <div>
            <p className="text-[14px] font-semibold text-success">Elections updated successfully</p>
            <p className="text-[12px] text-text-muted mt-0.5">
              Your investment elections have been saved and are effective immediately.
            </p>
          </div>
        </div>
      ) : (
        <div className="card p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
          <div className="flex items-center gap-3">
            <div
              className={[
                'w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold flex-shrink-0',
                isBalanced ? 'bg-success/15 text-success' : totalPct > 100 ? 'bg-danger/15 text-danger' : 'bg-warning/15 text-warning',
              ].join(' ')}
            >
              {isBalanced ? '✓' : totalPct > 100 ? '!' : totalPct}
            </div>
            <div>
              {isBalanced
                ? <p className="text-[13px] font-semibold text-success">Allocations balance to 100% — ready to submit</p>
                : totalPct > 100
                ? <p className="text-[13px] font-semibold text-danger">Over-allocated by {totalPct - 100}% — reduce some funds</p>
                : <p className="text-[13px] font-semibold text-warning">{remaining}% unallocated — assign to a fund to continue</p>
              }
              {submitResult?.ok === false && (
                <p className="text-xs text-danger mt-0.5">{submitResult.msg}</p>
              )}
            </div>
          </div>

          <div className="flex gap-2 flex-shrink-0">
            <button
              type="button"
              onClick={resetToCurrentAllocations}
              disabled={isSubmitting || isBlackout}
              className="btn-secondary"
            >
              Reset
            </button>
            <button
              type="button"
              onClick={handleSubmit}
              disabled={!isBalanced || isSubmitting || isBlackout}
              className={[
                'px-5 py-2 rounded-md text-[13px] font-semibold transition-colors duration-150 shadow-sm',
                isBalanced && !isBlackout
                  ? 'bg-accent hover:bg-accent-dark text-white'
                  : 'bg-bg-s3 text-text-faint cursor-not-allowed',
                'disabled:opacity-60 disabled:cursor-not-allowed',
              ].join(' ')}
            >
              {isSubmitting ? 'Applying…' : 'Apply Changes'}
            </button>
          </div>
        </div>
      )}

      <p className="text-[11px] text-text-faint text-center font-mono pb-2">
        All reallocations gate through FAP (12 ERISA rules) before execution · Changes are effective immediately
      </p>
    </div>
  );
}
