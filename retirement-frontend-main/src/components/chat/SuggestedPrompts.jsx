import React from 'react';
import { SUGGESTED_PROMPTS, classifyIntent } from '../../lib/chatPrompts.js';

// Deterministic glyph per classified intent — reuses the same classifyIntent
// function the mock AI pipeline runs on send, so the icon shown here always
// matches what the trace panel will report once the prompt is executed.
const INTENT_GLYPHS = {
  loan_inquiry: '💵',
  loan_initiation: '💵',
  deferral_change: '📊',
  investment_reallocation: '📈',
  hardship_distribution: '🏥',
  beneficiary_update: '👪',
  address_update: '🏠',
  vesting_inquiry: '⏳',
  account_inquiry: '📋',
  general_inquiry: '💬',
};

/**
 * Prompt suggestion chips. Clicking one fills the composer without submitting
 * so the participant can review or edit before sending. Disabled while a
 * response is streaming or a transaction is awaiting confirmation.
 */
export default function SuggestedPrompts({ onSelect, disabled = false }) {
  return (
    <div className="flex flex-wrap gap-2 justify-center mt-4">
      {SUGGESTED_PROMPTS.map((prompt) => {
        const glyph = INTENT_GLYPHS[classifyIntent(prompt)] || '💬';
        return (
          <button
            key={prompt}
            type="button"
            onClick={() => onSelect(prompt)}
            disabled={disabled}
            className="bg-bg-surface border border-border-strong rounded-full px-3.5 py-1.5 text-xs text-text-muted hover:border-accent hover:text-text hover:bg-bg-s2 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:border-border-strong disabled:hover:bg-bg-surface flex items-center gap-1.5"
          >
            <span aria-hidden="true">{glyph}</span>
            {prompt}
          </button>
        );
      })}
    </div>
  );
}
