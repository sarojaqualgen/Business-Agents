import React from 'react';

// Human-readable label per intent returned by mockChatEngine.classifyIntent.
// Kept separate from the engine itself — this is presentation only.
const INTENT_LABELS = {
  loan_inquiry: 'Loan Inquiry',
  loan_initiation: 'Loan Initiation',
  hardship_distribution: 'Hardship Distribution',
  deferral_change: 'Deferral Change',
  investment_reallocation: 'Investment Reallocation',
  beneficiary_update: 'Beneficiary Update',
  address_update: 'Address Update',
  vesting_inquiry: 'Vesting Inquiry',
  account_inquiry: 'Account Inquiry',
  general_inquiry: 'General Inquiry',
};

/**
 * Small chip surfacing the mock pipeline's intent-classification result
 * next to the trace header, so the "Intent Detection" step is visible to
 * the user rather than only implied by the trace text.
 */
export default function IntentBadge({ intent }) {
  if (!intent) return null;
  const label = INTENT_LABELS[intent] || intent;
  return (
    <span className="font-mono text-[10px] px-1.5 py-0.5 rounded border border-border-strong text-text-faint whitespace-nowrap">
      {label}
    </span>
  );
}

export { INTENT_LABELS };
