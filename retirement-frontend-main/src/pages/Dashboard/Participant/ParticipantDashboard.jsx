import React from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import AppLayout from '../../../components/layout/AppLayout.jsx';
import ChatContainer from '../../../components/chat/ChatContainer.jsx';
import ActionGuidePage from '../../../components/participant/ActionGuidePage.jsx';
import Overview from './Overview.jsx';
import Documents from './Documents.jsx';
import Activity from './Activity.jsx';
import Investments from './Investments.jsx';
import {
  LoanIcon,
  DistributionIcon,
  ContributionIcon,
  BeneficiaryIcon,
} from '../../../components/participant/icons.jsx';

const HEADERS = {
  '':                   { title: 'Participant Actions',       subtitle: 'Everything available under your retirement plan' },
  chat:                 { title: 'Chat',                      subtitle: 'Ask about your account or start a request' },
  loans:                { title: 'Loans',                     subtitle: 'Borrow against your vested balance' },
  investments:          { title: 'Investment Reallocation',   subtitle: 'Change how your account is invested' },
  'contribution-change':{ title: 'Contribution Change',       subtitle: 'Adjust your payroll deferral rate' },
  'beneficiary-update': { title: 'Beneficiary Update',        subtitle: 'Add or update your beneficiaries' },
  distributions:        { title: 'Distributions',             subtitle: 'Request a hardship or in-service distribution' },
  documents:            { title: 'Submitted Documents',       subtitle: "Status of documents you've uploaded" },
  activity:             { title: 'Activity History',          subtitle: 'Your transactions, decisions, and pending requests' },
};

export default function ParticipantDashboard() {
  const location = useLocation();
  const segment = location.pathname.replace(/^\/participant\/?/, '').split('/')[0] || '';
  const { title, subtitle } = HEADERS[segment] || HEADERS[''];

  return (
    <AppLayout variant="participant" title={title} subtitle={subtitle}>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="chat" element={<ChatContainer />} />

        <Route
          path="loans"
          element={
            <ActionGuidePage
              icon={<LoanIcon />}
              title="Loan Request"
              description="Borrow from your vested balance and repay through payroll deductions. The compliance engine checks IRC §72(p) caps before issuing a supervised confirmation step."
              citation="IRC §72(p)"
              fields={[
                { label: 'Loan amount', hint: 'max is lesser of $50,000 or 50% of vested balance', required: true },
                { label: 'Repayment period', hint: 'e.g. 5 years', required: true },
                { label: 'Purpose', hint: 'general, primary home purchase, etc.', required: false },
              ]}
              examples={[
                'I want to take a loan of $10,000 for 5 years',
                'Can I borrow $25,000 for a primary home purchase over 10 years?',
                'What is the maximum loan I can take?',
              ]}
            />
          }
        />

        <Route path="investments" element={<Investments />} />

        <Route
          path="contribution-change"
          element={
            <ActionGuidePage
              icon={<ContributionIcon />}
              title="Contribution Change"
              description="Adjust how much of each paycheck goes into your 401(k), and whether it's pre-tax, Roth, or a catch-up contribution. Note: HCEs must elect catch-up as Roth under SECURE 2.0 §603."
              citation="IRC §402(g) · SECURE 2.0 §603"
              fields={[
                { label: 'New deferral rate', hint: 'e.g. 8%, or $500 per paycheck', required: true },
                { label: 'Pre-tax or Roth', hint: 'affects how contributions are taxed', required: false },
                { label: 'Catch-up election', hint: 'if you\'re 50+ and want to contribute more', required: false },
              ]}
              examples={[
                'Change my deferral to 8%',
                'Set my contribution to 10% pre-tax',
                'I want to add a Roth catch-up contribution of $7,500',
                'Stop my contributions — set deferral to 0%',
              ]}
            />
          }
        />

        <Route
          path="beneficiary-update"
          element={
            <ActionGuidePage
              icon={<BeneficiaryIcon />}
              title="Beneficiary Update"
              description="Name or change who receives your account balance if you pass away. Naming anyone other than your spouse as primary beneficiary may require notarized spousal consent under ERISA §205."
              citation="ERISA §205"
              fields={[
                { label: 'Beneficiary full name', required: true },
                { label: 'Relationship', hint: 'spouse, child, parent, trust, etc.', required: true },
                { label: 'Allocation %', hint: 'if multiple beneficiaries, must total 100%', required: false },
                { label: 'Contingent beneficiary', hint: 'backup if primary predeceases you', required: false },
              ]}
              examples={[
                'Change my beneficiary to my spouse Jane Doe',
                'Add my two children as 50/50 primary beneficiaries',
                'Update my primary beneficiary and add a contingent beneficiary',
              ]}
            />
          }
        />

        <Route
          path="distributions"
          element={
            <ActionGuidePage
              icon={<DistributionIcon />}
              title="Hardship or In-Service Distribution"
              description="Request a withdrawal while still employed. Hardship distributions require a qualifying IRS safe-harbor expense and supporting documents. In-service distributions require age 59½+."
              citation="IRC §401(k)(2)(B) · IRS Revenue Ruling 2010-9"
              fields={[
                { label: 'Distribution type', hint: 'hardship or in-service', required: true },
                { label: 'Amount requested', required: true },
                { label: 'Reason / expense type', hint: 'medical, eviction, tuition, funeral, home purchase, casualty loss', required: true },
                { label: 'Supporting document', hint: 'you will be prompted to upload after submission', required: false },
              ]}
              examples={[
                'I need a hardship withdrawal of $5,000 for medical emergency',
                'Request a hardship distribution of $8,000 for unpaid tuition',
                'I want to take an in-service distribution',
                'Hardship withdrawal for $6,000 — eviction prevention',
              ]}
            />
          }
        />

        <Route path="documents" element={<Documents />} />
        <Route path="activity" element={<Activity />} />
      </Routes>
    </AppLayout>
  );
}
