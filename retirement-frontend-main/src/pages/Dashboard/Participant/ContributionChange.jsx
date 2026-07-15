import React, { useCallback, useEffect, useState } from 'react';
import { apiClient, ApiError } from '../../../lib/apiClient.js';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';
import { ACCOUNT_UPDATED_EVENT } from '../../../lib/events.js';

const LIMIT_402G = 23000;
const LIMIT_CATCHUP_50 = 7500;

function pctDisplay(v) {
  return `${(v * 100).toFixed(1)}%`;
}

export default function ContributionChange() {
  const [data, setData] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState(null);

  // Draft values
  const [newPct, setNewPct] = useState('');   // string to allow empty input
  const [deferralType, setDeferralType] = useState('pre_tax');
  const [catchUp, setCatchUp] = useState(false);

  // Submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  const [showSuccess, setShowSuccess] = useState(false);

  // Supervised confirmation state (deferral to 0%)
  const [pendingConfirm, setPendingConfirm] = useState(null); // {warning}
  const [isConfirming, setIsConfirming] = useState(false);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await apiClient.getDeferralInfo();
      setData(res);
      setNewPct(String(Math.round(res.current_deferral_pct * 1000) / 10));
      setDeferralType(res.deferral_type);
    } catch (err) {
      setError(err.message || 'Failed to load deferral info');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const numericPct = parseFloat(newPct) || 0;  // 0–100
  const decimalPct = numericPct / 100;          // 0.0–1.0

  // Estimated annual deferral (for limit warning)
  const annualDeferral = data ? data.annual_compensation * decimalPct : 0;
  const effectiveLimit = data?.catch_up_eligible && catchUp
    ? LIMIT_402G + LIMIT_CATCHUP_50
    : LIMIT_402G;
  const overLimit = annualDeferral > effectiveLimit;

  // Roth catch-up required for HCEs over $23k
  const roth_catchup_required =
    data?.is_hce && catchUp && annualDeferral > LIMIT_402G && deferralType === 'pre_tax';

  const isUnchanged =
    data &&
    Math.abs(decimalPct - data.current_deferral_pct) < 0.0005 &&
    deferralType === data.deferral_type &&
    !catchUp;

  async function handleApply() {
    if (isSubmitting || isUnchanged || overLimit || roth_catchup_required) return;
    setIsSubmitting(true);
    setSubmitError(null);
    setPendingConfirm(null);
    try {
      const result = await apiClient.changeDeferral({
        newDeferralPct: decimalPct,
        deferralType,
        catchUp,
      });
      if (result.status === 'requires_confirmation') {
        setPendingConfirm({ warning: result.warning });
      } else {
        // full autonomy — done
        setShowSuccess(true);
        window.dispatchEvent(new CustomEvent(ACCOUNT_UPDATED_EVENT));
        setTimeout(() => load(), 800);
        setTimeout(() => setShowSuccess(false), 4000);
      }
    } catch (err) {
      setSubmitError(err.message || 'Could not update deferral');
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirm() {
    setIsConfirming(true);
    setSubmitError(null);
    try {
      await apiClient.confirmTransaction();
      setPendingConfirm(null);
      setShowSuccess(true);
      window.dispatchEvent(new CustomEvent(ACCOUNT_UPDATED_EVENT));
      setTimeout(() => load(), 800);
      setTimeout(() => setShowSuccess(false), 4000);
    } catch (err) {
      setSubmitError(err.message || 'Confirmation failed');
    } finally {
      setIsConfirming(false);
    }
  }

  async function handleCancel() {
    try { await apiClient.cancelTransaction(); } catch { /* ignore */ }
    setPendingConfirm(null);
    setSubmitError(null);
  }

  if (isLoading) return <LoadingState label="Loading your deferral info…" />;

  if (error) {
    return (
      <EmptyState
        tone="error"
        icon="error"
        title="Could not load deferral info"
        description={error}
      />
    );
  }

  if (!data) return null;

  const isBlackout = data.blackout_active;
  const isBusy = isSubmitting || isConfirming || !!pendingConfirm || isBlackout;

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-[20px] font-bold text-text leading-tight">Contribution Change</h1>
        <p className="text-sm text-text-muted mt-1">
          Adjust how much of each paycheck goes into your 401(k). FAP compliance runs automatically.
          Changes take effect on your next payroll cycle.
        </p>
      </div>

      {isBlackout && (
        <div className="card p-4 border-warning/30 bg-warning/5">
          <p className="text-sm text-warning font-medium">
            A plan blackout is active. Contribution changes cannot be made during this period.
          </p>
        </div>
      )}

      {/* Current deferral summary */}
      <div className="card p-5 flex items-center justify-between gap-4">
        <div>
          <p className="text-[11px] font-mono text-text-muted uppercase tracking-wide mb-1">Current deferral</p>
          <p className="text-3xl font-bold text-text tabular-nums">
            {pctDisplay(data.current_deferral_pct)}
          </p>
          <p className="text-[12px] text-text-muted mt-0.5">
            {data.deferral_type === 'pre_tax' ? 'Pre-tax' : 'Roth'} · {' '}
            {data.catch_up_eligible ? 'Catch-up eligible' : 'Standard limits'}
          </p>
        </div>
        {data.catch_up_eligible && (
          <div className="rounded-md bg-accent/10 px-3 py-2 text-center">
            <p className="text-[10px] font-mono text-accent uppercase tracking-wide">Catch-up</p>
            <p className="text-[12px] font-semibold text-accent mt-0.5">eligible</p>
          </div>
        )}
      </div>

      {/* Input form */}
      <div className="card p-5 space-y-5">
        {/* New rate */}
        <div>
          <label className="block text-[11px] font-mono text-text-muted uppercase tracking-wide mb-2">
            New deferral rate
          </label>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={0}
              max={100}
              step={0.5}
              disabled={isBusy}
              value={newPct}
              onChange={(e) => {
                setNewPct(e.target.value);
                setSubmitError(null);
              }}
              className="input-field w-28 text-right text-xl font-bold py-2 disabled:opacity-50"
            />
            <span className="text-xl text-text-muted font-bold">%</span>
            <span className="text-sm text-text-faint">
              ≈ ${(annualDeferral).toLocaleString(undefined, { maximumFractionDigits: 0 })}/yr
            </span>
          </div>
          {overLimit && (
            <p className="text-[12px] text-danger mt-1.5">
              Projected deferral ${annualDeferral.toLocaleString(undefined, { maximumFractionDigits: 0 })} exceeds
              the {data.catch_up_eligible && catchUp ? 'catch-up' : 'standard'} limit of ${effectiveLimit.toLocaleString()}.
              FAP will deny this — lower the rate.
            </p>
          )}
        </div>

        {/* Pre-tax / Roth toggle */}
        <div>
          <p className="text-[11px] font-mono text-text-muted uppercase tracking-wide mb-2">Contribution type</p>
          <div className="flex gap-2">
            {['pre_tax', 'roth'].map((t) => (
              <button
                key={t}
                type="button"
                disabled={isBusy}
                onClick={() => setDeferralType(t)}
                className={[
                  'px-4 py-2 rounded-md text-[13px] font-medium border transition-colors duration-150',
                  deferralType === t
                    ? 'bg-accent text-white border-accent shadow-sm'
                    : 'bg-bg-s2 text-text-muted border-border-strong hover:border-accent/40 hover:text-text',
                  'disabled:opacity-50 disabled:cursor-not-allowed',
                ].join(' ')}
              >
                {t === 'pre_tax' ? 'Pre-tax' : 'Roth'}
              </button>
            ))}
          </div>
          {deferralType === 'roth' && (
            <p className="text-[11px] text-text-faint mt-1.5">
              Roth contributions are taxed now, grow tax-free, and are not taxed at withdrawal.
            </p>
          )}
        </div>

        {/* Catch-up election (age 50+) */}
        {data.catch_up_eligible && (
          <div>
            <p className="text-[11px] font-mono text-text-muted uppercase tracking-wide mb-2">Catch-up contribution</p>
            <label className="flex items-start gap-3 cursor-pointer group">
              <input
                type="checkbox"
                disabled={isBusy}
                checked={catchUp}
                onChange={(e) => setCatchUp(e.target.checked)}
                className="mt-0.5 accent-accent disabled:opacity-50"
              />
              <span className="text-[13px] text-text">
                Elect catch-up contribution (+${LIMIT_CATCHUP_50.toLocaleString()}/yr above standard limit)
              </span>
            </label>
            {data.is_hce && catchUp && deferralType === 'pre_tax' && (
              <p className="text-[12px] text-warning mt-1.5">
                SECURE 2.0 §603: As an HCE, catch-up contributions must be designated Roth.
                Switch to Roth to proceed.
              </p>
            )}
          </div>
        )}
      </div>

      {/* Confirmation panel (for deferral to 0%) */}
      {pendingConfirm && (
        <div className="card p-5 border-warning/40 bg-warning/5 space-y-4">
          <div className="flex items-start gap-3">
            <div className="w-8 h-8 rounded-full bg-warning/15 text-warning flex items-center justify-center text-sm font-bold flex-shrink-0">!</div>
            <div>
              <p className="text-[13px] font-semibold text-warning">Confirmation required</p>
              <p className="text-[13px] text-text-muted mt-0.5">{pendingConfirm.warning}</p>
              <p className="text-[12px] text-text-faint mt-1">
                FAP approved this change. All 12 ERISA rules passed. Your explicit confirmation is required.
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={handleCancel}
              disabled={isConfirming}
              className="btn-secondary"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleConfirm}
              disabled={isConfirming}
              className="px-5 py-2 rounded-md text-[13px] font-semibold bg-warning text-white hover:bg-yellow-600 transition-colors duration-150 disabled:opacity-60"
            >
              {isConfirming ? 'Confirming…' : 'Yes, set to 0%'}
            </button>
          </div>
        </div>
      )}

      {/* Submit footer */}
      {!pendingConfirm && (
        <div className="card p-5 flex flex-col sm:flex-row items-start sm:items-center gap-4 justify-between">
          <div>
            {submitError && <p className="text-[13px] text-danger">{submitError}</p>}
            {showSuccess && (
              <p className="text-[13px] text-success font-semibold">
                Deferral rate updated to {pctDisplay(decimalPct)} ({deferralType === 'pre_tax' ? 'pre-tax' : 'Roth'}).
              </p>
            )}
            {!submitError && !showSuccess && (
              <p className="text-[13px] text-text-muted">
                {isUnchanged
                  ? 'No changes to apply'
                  : `Change deferral from ${pctDisplay(data.current_deferral_pct)} → ${pctDisplay(decimalPct)}`}
              </p>
            )}
          </div>
          <button
            type="button"
            onClick={handleApply}
            disabled={isBusy || isUnchanged || overLimit || roth_catchup_required || numericPct < 0}
            className={[
              'px-5 py-2 rounded-md text-[13px] font-semibold transition-colors duration-150 shadow-sm flex-shrink-0',
              !isBusy && !isUnchanged && !overLimit && !roth_catchup_required
                ? 'bg-accent hover:bg-accent-dark text-white'
                : 'bg-bg-s3 text-text-faint cursor-not-allowed',
              'disabled:opacity-60 disabled:cursor-not-allowed',
            ].join(' ')}
          >
            {isSubmitting ? 'Applying…' : 'Apply Changes'}
          </button>
        </div>
      )}

      <p className="text-[11px] text-text-faint text-center font-mono pb-2">
        All deferral changes gate through FAP (12 ERISA rules) · IRC §402(g) · SECURE 2.0 §603
      </p>
    </div>
  );
}
