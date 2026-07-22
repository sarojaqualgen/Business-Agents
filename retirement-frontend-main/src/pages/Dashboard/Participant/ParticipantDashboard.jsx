import React from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import AppLayout from '../../../components/layout/AppLayout.jsx';
import ChatContainer from '../../../components/chat/ChatContainer.jsx';
import ActionGuidePage from '../../../components/participant/ActionGuidePage.jsx';
import Overview from './Overview.jsx';
import Documents from './Documents.jsx';
import Activity from './Activity.jsx';
import Investments from './Investments.jsx';
import ContributionChange from './ContributionChange.jsx';
import DistributionsPage from './DistributionsPage.jsx';
import {
  LoanIcon,
  HardshipIcon,
  BeneficiaryIcon,
} from '../../../components/participant/icons.jsx';

const HEADERS = {
  '':                   { title: 'Participant Actions',       subtitle: 'Everything available under your retirement plan' },
  chat:                 { title: 'Chat',                      subtitle: 'Ask about your account or start a request' },
  loans:                { title: 'Loans',                     subtitle: 'Borrow against your vested balance' },
  investments:          { title: 'Investment Reallocation',   subtitle: 'Change how your account is invested' },
  'contribution-change':{ title: 'Contribution Change',       subtitle: 'Adjust your payroll deferral rate' },
  'beneficiary-update': { title: 'Beneficiary Update',        subtitle: 'Add or update your beneficiaries' },
  hardship:             { title: 'Hardship Withdrawal',       subtitle: 'Access funds early for a qualifying financial hardship' },
  distributions:        { title: 'Distributions',             subtitle: 'In-service, separation, RMD, or QDRO — choose your distribution type' },
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

        <Route path="contribution-change" element={<ContributionChange />} />

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
          path="hardship"
          element={
            <ActionGuidePage
              icon={<HardshipIcon />}
              title="Hardship Withdrawal"
              description="Withdraw funds while still employed for a qualifying IRS safe-harbor hardship expense. Subject to ordinary income tax and a 10% early withdrawal penalty under IRC §72(t) if under age 59½. Supporting documentation is required; the plan administrator must review before funds are released."
              citation="IRC §401(k)(2)(B)(i)(IV) · Treas. Reg. §1.401(k)-1(d)(3)"
              fields={[
                { label: 'Amount', hint: 'must not exceed the actual hardship need', required: true },
                { label: 'Qualifying reason', hint: 'medical bills, eviction / foreclosure, tuition, funeral costs, casualty loss, or disaster relief', required: true },
                { label: 'Supporting document', hint: 'bill, eviction notice, tuition invoice, etc. — uploaded after submission', required: true },
                { label: 'Tax acknowledgment', hint: 'you will be prompted to confirm this is a taxable event', required: true },
              ]}
              examples={[
                'I need a hardship withdrawal of $5,000 for medical bills',
                'Hardship withdrawal for $6,000 — eviction prevention',
                'Request a hardship distribution of $8,000 for unpaid tuition',
                'I need $5,000 for funeral expenses for my father',
              ]}
            />
          }
        />

        <Route path="distributions" element={<DistributionsPage />} />

        <Route path="documents" element={<Documents />} />
        <Route path="activity" element={<Activity />} />
      </Routes>
    </AppLayout>
  );
}
