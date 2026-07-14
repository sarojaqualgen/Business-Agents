import React, { useState } from 'react';

/**
 * Collects bank routing and account details after a supervised loan is confirmed
 * and the backend returns `awaiting_bank_details`. Styled to match ConfirmationDialog.
 *
 * Props:
 *   action      — e.g. "loan_initiation" (for display only)
 *   onSubmit    — called with { routingNumber, accountNumber, accountType }
 *   onCancel    — called when user dismisses without submitting
 *   isSubmitting — disables buttons while the request is in flight
 */
export default function BankDetailsCard({ action, onSubmit, onCancel, isSubmitting }) {
  const [routingNumber, setRoutingNumber] = useState('');
  const [accountNumber, setAccountNumber] = useState('');
  const [accountType, setAccountType] = useState('checking');

  const routingValid = /^\d{9}$/.test(routingNumber);
  const canSubmit = routingValid && accountNumber.trim().length > 0 && !isSubmitting;

  function handleSubmit(e) {
    e.preventDefault();
    if (!canSubmit) return;
    onSubmit({ routingNumber, accountNumber: accountNumber.trim(), accountType });
  }

  return (
    <div className="bg-bg-surface border border-warning rounded-lg p-4 max-w-md">
      <h3 className="text-sm font-semibold text-text mb-1 flex items-center gap-2">
        <span className="text-warning">⚠</span> Bank Details Required
      </h3>
      <p className="text-xs text-text-muted leading-relaxed mb-4">
        Your loan has been approved. Provide your bank account details and funds will be sent within{' '}
        <span className="font-medium text-text">3–5 business days</span>.
      </p>

      <form onSubmit={handleSubmit} className="space-y-3">
        {/* Routing number */}
        <div>
          <label className="label-mono" htmlFor="routing-number">
            Routing number (9 digits)
          </label>
          <input
            id="routing-number"
            type="text"
            inputMode="numeric"
            maxLength={9}
            value={routingNumber}
            onChange={(e) => setRoutingNumber(e.target.value.replace(/\D/g, '').slice(0, 9))}
            placeholder="e.g. 021000021"
            className={[
              'input-field text-sm font-mono',
              routingNumber && !routingValid ? 'border-danger' : '',
            ].join(' ')}
            disabled={isSubmitting}
          />
          {routingNumber && !routingValid && (
            <p className="text-[11px] text-danger mt-0.5">Must be exactly 9 digits.</p>
          )}
        </div>

        {/* Account number */}
        <div>
          <label className="label-mono" htmlFor="account-number">
            Account number
          </label>
          <input
            id="account-number"
            type="text"
            inputMode="numeric"
            value={accountNumber}
            onChange={(e) => setAccountNumber(e.target.value.replace(/\D/g, ''))}
            placeholder="e.g. 000123456789"
            className="input-field text-sm font-mono"
            disabled={isSubmitting}
          />
        </div>

        {/* Account type */}
        <div>
          <label className="label-mono" htmlFor="account-type">
            Account type
          </label>
          <select
            id="account-type"
            value={accountType}
            onChange={(e) => setAccountType(e.target.value)}
            className="input-field text-sm"
            disabled={isSubmitting}
          >
            <option value="checking">Checking</option>
            <option value="savings">Savings</option>
          </select>
        </div>

        <div className="flex gap-2 pt-1">
          <button
            type="submit"
            disabled={!canSubmit}
            className="px-4 py-2 rounded-md text-[13px] font-medium bg-accent hover:bg-accent-dark text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? 'Submitting…' : 'Submit Bank Details'}
          </button>
          <button
            type="button"
            onClick={onCancel}
            disabled={isSubmitting}
            className="px-4 py-2 rounded-md text-[13px] font-medium bg-bg-s2 border border-border-strong text-text-muted hover:text-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
        </div>
      </form>
    </div>
  );
}
