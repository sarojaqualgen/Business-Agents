import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { ACCOUNT_UPDATED_EVENT, PLAN_UPDATED_EVENT } from '../../../lib/events.js';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';
import ActionCard from '../../../components/participant/ActionCard.jsx';
import PlanInfoPanel from '../../../components/participant/PlanInfoPanel.jsx';
import {
  LoanIcon,
  HardshipIcon,
  InvestmentIcon,
  ContributionIcon,
  BeneficiaryIcon,
  DistributionIcon,
  DocumentIcon,
} from '../../../components/participant/icons.jsx';

// How often the page silently re-checks account/plan data, in addition to
// refreshing immediately whenever a workflow (loan, deferral change,
// reallocation, address update, blackout) writes to the mock database.
const AUTO_REFRESH_MS = 15000;

// Navigation/action cards only — no business logic is attached here. Each
// card links to its (placeholder) workflow route; the live workflows run
// through the chat engine, with manual/queue-based paths landing in a
// later milestone. See RoadmapNotice on each destination route.
const ACTIONS = [
  {
    key: 'loan',
    icon: <LoanIcon />,
    title: 'Loan',
    description: 'Borrow against your vested balance and repay through payroll deduction.',
    tooltip: 'Request a loan up to the lesser of $50,000 or 50% of your vested balance under IRC §§72(p). Repayment terms and outstanding-loan limits are enforced by your plan.',
    to: '/participant/loans',
  },
  {
    key: 'hardship',
    icon: <HardshipIcon />,
    title: 'Hardship Withdrawal',
    description: 'Access funds early for an IRS-qualifying financial hardship.',
    tooltip: 'Withdraw funds for a qualifying safe-harbor expense — medical bills, eviction prevention, tuition, funeral costs, or disaster relief. Requires supporting documentation and plan sponsor review.',
    to: '/participant/hardship',
  },
  {
    key: 'investment-reallocation',
    icon: <InvestmentIcon />,
    title: 'Investment Reallocation',
    description: 'Reallocate your account balance across available funds.',
    tooltip: "Change how your current balance and future contributions are invested across the plan's fund lineup, including target-date and QDIA options.",
    to: '/participant/investments',
  },
  {
    key: 'contribution-change',
    icon: <ContributionIcon />,
    title: 'Contribution Change',
    description: 'Adjust your payroll deferral rate, pre-tax/Roth split, or catch-up election.',
    tooltip: "Change how much of your paycheck is deferred into the plan, including pre-tax vs. Roth elections. HCE catch-up contributions may be required to be Roth under SECURE 2.0 §603.",
    to: '/participant/contribution-change',
  },
  {
    key: 'beneficiary-update',
    icon: <BeneficiaryIcon />,
    title: 'Beneficiary Update',
    description: 'Add, remove, or update your primary and contingent beneficiaries.',
    tooltip: 'Submit a beneficiary change for your account. Naming anyone other than your spouse as primary beneficiary may require notarized spousal consent under ERISA §205.',
    to: '/participant/beneficiary-update',
    comingSoon: true,
  },
  {
    key: 'distribution',
    icon: <DistributionIcon />,
    title: 'Distribution',
    description: 'Request an in-service, separation, RMD, or QDRO distribution.',
    tooltip: 'Covers four distribution types: In-Service (age 59½+, while employed), Separation (after leaving), RMD (mandatory age 73+), and QDRO (court-ordered). All are taxable events; each has different eligibility rules and review paths.',
    to: '/participant/distributions',
  },
  {
    key: 'documents',
    icon: <DocumentIcon />,
    title: 'View Submitted Documents',
    description: "Review the status of documents you've submitted for a pending request.",
    tooltip: "See every document you've uploaded in support of a hardship or QDRO request, along with its verification status. Your plan sponsor reviews each document before approving.",
    to: '/participant/documents',
    tooltipUp: true,
  },
];

export default function Overview() {
  const { principal } = useAuth();
  const [participant, setParticipant] = useState(null);
  const [plan, setPlan] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(
    async ({ silent = false } = {}) => {
      if (!silent) setIsLoading(true);
      try {
        const [participantsRes, plansRes] = await Promise.all([
          apiClient.listParticipants(),
          apiClient.listPlans(),
        ]);
        const matchedParticipant = (participantsRes.participants || []).find(
          (p) => p.participant_id === principal?.participantId,
        );
        const matchedPlan = (plansRes.plans || []).find(
          (p) => p.plan_id === (matchedParticipant?.plan_id || principal?.planId),
        );
        setParticipant(matchedParticipant || null);
        setPlan(matchedPlan || null);
      } catch {
        // leave existing state on error
      } finally {
        if (!silent) setIsLoading(false);
      }
    },
    [principal?.participantId, principal?.planId],
  );

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [principal?.participantId]);

  // Auto-refresh: react immediately to any executed workflow that touches
  // this participant or plan, plus a light polling interval as a fallback.
  useEffect(() => {
    if (!principal?.participantId) return undefined;

    function onAccountUpdated(event) {
      if (event.detail?.participantId === principal.participantId) load({ silent: true });
    }
    function onPlanUpdated() {
      load({ silent: true });
    }

    window.addEventListener(ACCOUNT_UPDATED_EVENT, onAccountUpdated);
    window.addEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
    const interval = setInterval(() => load({ silent: true }), AUTO_REFRESH_MS);

    return () => {
      window.removeEventListener(ACCOUNT_UPDATED_EVENT, onAccountUpdated);
      window.removeEventListener(PLAN_UPDATED_EVENT, onPlanUpdated);
      clearInterval(interval);
    };
  }, [principal?.participantId, load]);

  if (isLoading) {
    return <LoadingState label="Loading your participant profile…" />;
  }

  if (!participant) {
    return (
      <EmptyState
        tone="error"
        icon="error"
        title="No profile found"
        description={`We couldn't find a participant record for ${principal?.participantId || 'this session'}. Try signing in again.`}
      />
    );
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-[1fr_300px] xl:grid-cols-[1fr_320px] gap-6 items-start">
      <div>
        <p className="text-sm text-text-muted leading-relaxed max-w-2xl mb-6">
          Hover a card for details, or select one to get started.
        </p>

        <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-5">
          {ACTIONS.map((action) => (
            <ActionCard
              key={action.key}
              icon={action.icon}
              title={action.title}
              description={action.description}
              tooltip={action.tooltip}
              to={action.to}
              tooltipUp={action.tooltipUp || false}
              comingSoon={action.comingSoon || false}
            />
          ))}
        </div>
      </div>

      <PlanInfoPanel participant={participant} plan={plan} />
    </div>
  );
}
