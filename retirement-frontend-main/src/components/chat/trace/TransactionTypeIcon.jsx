import React from 'react';

const TYPE_GLYPHS = {
  loan_initiation: '💵',
  deferral_change: '📊',
  investment_reallocation: '📈',
  hardship_distribution: '🏥',
  beneficiary_update: '👪',
  address_update: '🏠',
};

export default function TransactionTypeIcon({ type, className = '' }) {
  const glyph = TYPE_GLYPHS[type] || '📄';
  return (
    <span aria-hidden="true" className={['text-sm leading-none', className].join(' ')}>
      {glyph}
    </span>
  );
}
