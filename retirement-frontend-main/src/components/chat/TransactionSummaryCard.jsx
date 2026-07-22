import React from 'react';
import { formatCurrency, titleCase } from '../../lib/format.js';
import TransactionTypeIcon from './trace/TransactionTypeIcon.jsx';

const STATUS_STYLES = {
  pending_confirmation: { label: 'Awaiting Confirmation', className: 'text-warning' },
  pending_review: { label: 'Pending Administrator Review', className: 'text-purple' },
  executed: { label: 'Executed', className: 'text-success' },
  cancelled: { label: 'Cancelled', className: 'text-text-faint' },
};

function rowsForTransaction(transaction) {
  switch (transaction.type) {
    case 'loan_initiation':
      return [
        ['Amount', formatCurrency(transaction.amount)],
        ['Repayment term', `${transaction.termYears} year(s)`],
        ['Purpose', transaction.purpose],
      ];
    case 'deferral_change':
      return [
        ['New rate', `${transaction.ratePercent}%`],
        ['Contribution type', titleCase(transaction.contributionType)],
      ];
    case 'investment_reallocation':
      return (transaction.allocations || []).map((a) => [a.fund, `${a.percent}%`]);
    case 'hardship_distribution':
      return [
        ['Amount', formatCurrency(transaction.amount)],
        ['Reason', titleCase(transaction.reason)],
        ['Entry ID', transaction.entryId],
      ];
    case 'beneficiary_update':
      return [['Entry ID', transaction.entryId]];
    case 'address_update':
      return [['Action', 'Mailing address updated']];
    default:
      return [];
  }
}

export default function TransactionSummaryCard({ transaction, children }) {
  const status = STATUS_STYLES[transaction.status] || null;
  const rows = rowsForTransaction(transaction);

  return (
    <div className="bg-bg-s2 rounded-md p-3.5">
      <div className="flex items-center justify-between mb-2.5">
        <span className="text-sm font-medium text-text flex items-center gap-1.5">
          <TransactionTypeIcon type={transaction.type} />
          {transaction.label || titleCase(transaction.type)}
        </span>
        {status && <span className={`text-[11px] font-mono font-semibold ${status.className}`}>{status.label}</span>}
      </div>
      <dl className="flex flex-col gap-1.5">
        {rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between text-[13px]">
            <dt className="text-text-faint">{label}</dt>
            <dd className="font-medium text-text">{value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </div>
  );
}
