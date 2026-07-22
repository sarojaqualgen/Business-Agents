import React from 'react';

/**
 * Shown below an assistant message when the backend requests taxable-event
 * acknowledgment before submitting a distribution (hardship, in-service,
 * separation, RMD). Clicking "Yes, I Acknowledge" auto-sends a confirmation
 * message so Haiku can carry forward the collected params and proceed to FAP.
 */
export default function TaxAcknowledgmentCard({ onConfirm, onCancel, isResolving }) {
  return (
    <div className="bg-bg-surface border border-warning rounded-lg p-4 max-w-md">
      <h3 className="text-sm font-semibold text-text mb-2 flex items-center gap-2">
        <span className="text-warning">⚠</span> Tax Disclosure — Action Required
      </h3>
      <p className="text-[13px] text-text-muted leading-relaxed mb-3">
        By confirming, you acknowledge that this distribution is a{' '}
        <strong className="text-text">taxable event</strong>. Ordinary income tax will apply to the
        full amount. If you are under age 59½, a 10% early withdrawal penalty under IRC § 72(t)
        may also apply.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={isResolving}
          className="px-4 py-2 rounded-md text-[13px] font-medium bg-accent hover:bg-accent-dark text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isResolving ? 'Processing…' : 'Yes, I Acknowledge'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isResolving}
          className="px-4 py-2 rounded-md text-[13px] font-medium bg-bg-s2 border border-border-strong text-text-muted hover:text-text transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
