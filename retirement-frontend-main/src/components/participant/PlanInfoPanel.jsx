import React from 'react';
import Badge from '../ui/Badge.jsx';
import { formatCurrency, formatPercent, titleCase } from '../../lib/format.js';

/**
 * Side panel showing the participant's selected retirement plan and
 * account snapshot, kept visually and structurally separate from the
 * Participant Actions grid per the latest UI feedback.
 */
export default function PlanInfoPanel({ participant, plan }) {
  return (
    <aside className="card p-6 lg:sticky lg:top-[88px] h-max">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-[15px] font-semibold text-text tracking-tight">Plan Information</h2>
        {plan?.blackout_active !== undefined && (
          <Badge tone={plan.blackout_active ? 'active' : 'inactive'}>
            {plan.blackout_active ? 'Blackout' : 'Open'}
          </Badge>
        )}
      </div>

      <dl className="space-y-3.5 text-sm mb-6">
        <div className="flex justify-between gap-4">
          <dt className="text-text-muted">Plan</dt>
          <dd className="text-text font-medium text-right leading-snug">{plan?.plan_name || '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Plan ID</dt>
          <dd className="text-text font-mono text-[13px]">{plan?.plan_id || '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Plan Type</dt>
          <dd className="text-text">{plan?.plan_type?.toUpperCase() || '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Loans Permitted</dt>
          <dd className="text-text">{plan?.loans_permitted ? 'Yes' : 'No'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Hardship Permitted</dt>
          <dd className="text-text">{plan?.hardship_permitted ? 'Yes' : 'No'}</dd>
        </div>
      </dl>

      <div className="h-px bg-border mb-6" />

      <h3 className="text-[11px] font-mono text-text-muted mb-4 uppercase tracking-wider">Your Account</h3>
      <dl className="space-y-3.5 text-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Vesting</dt>
          <dd className="text-text font-semibold tabular-nums">{formatPercent(participant?.vesting_pct)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Loan Headroom</dt>
          <dd className="text-text font-semibold tabular-nums">{formatCurrency(participant?.loan_headroom)}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Outstanding Loans</dt>
          <dd className="text-text tabular-nums">{participant?.outstanding_loans ?? '—'}</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-text-muted">Years of Service</dt>
          <dd className="text-text tabular-nums">{participant?.years_of_service ?? '—'}</dd>
        </div>
        <div className="flex justify-between gap-3 items-center">
          <dt className="text-text-muted">Employment Status</dt>
          <dd>
            {/* Badge's "inactive" tone renders green — reused here (not
                relabeled, per Badge's existing status vocabulary) because
                an "active" employee is the good/green state, the inverse
                of an "active" blackout. */}
            <Badge tone={participant?.employment_status === 'active' ? 'inactive' : 'default'}>
              {titleCase(participant?.employment_status || '—')}
            </Badge>
          </dd>
        </div>
      </dl>
    </aside>
  );
}
