import React from 'react';
import TransactionSummaryCard from './TransactionSummaryCard.jsx';

/**
 * Renders below a supervised-autonomy assistant response. The FAP token
 * (in the real system) is issued but not consumed until "Confirm" is
 * pressed — "Cancel" invalidates it with no execution.
 */
export default function ConfirmationDialog({ transaction, onConfirm, onCancel, isResolving }) {
  return (
    <div className="bg-bg-surface border border-warning rounded-lg p-4 max-w-md">
      <h3 className="text-sm font-semibold text-text mb-3 flex items-center gap-2">
        <span className="text-warning">⚠</span> Confirmation Required
      </h3>
      <TransactionSummaryCard transaction={transaction} />
      <p className="text-xs text-warning leading-relaxed mt-3 mb-3">
        This action affects your retirement savings and cannot be undone once confirmed.
      </p>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={onConfirm}
          disabled={isResolving}
          className="px-4 py-2 rounded-md text-[13px] font-medium bg-accent hover:bg-accent-dark text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isResolving ? 'Processing…' : 'Confirm'}
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
