import React from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import AppLayout from '../../../components/layout/AppLayout.jsx';
import Overview from './Overview.jsx';
import Queue from './Queue.jsx';
import AuditLog from './AuditLog.jsx';
import BlackoutManager from './BlackoutManager.jsx';
import ParticipantsPage from './ParticipantsPage.jsx';
import ParticipantActivityPage from './ParticipantActivityPage.jsx';
import PlanActivityPage from './PlanActivityPage.jsx';

const HEADERS = {
  '':               { title: 'Plan Administrator Overview', subtitle: 'Plan health and pending activity' },
  queue:            { title: 'Review Queue', subtitle: 'Requests awaiting your approval' },
  'plan-activity':  { title: 'Plan Activity', subtitle: 'All participant actions across the plan — newest first' },
  participants:     { title: 'Participants', subtitle: 'All enrolled participants and their activity' },
  audit:            { title: 'Audit Log', subtitle: 'Compliance decision history for this plan' },
  blackout:         { title: 'Blackout Manager', subtitle: 'Restrict transactions during a blackout period' },
};

export default function SponsorDashboard() {
  const location = useLocation();
  const segment = location.pathname.replace(/^\/sponsor\/?/, '').split('/')[0] || '';
  const { title, subtitle } = HEADERS[segment] || HEADERS[''];

  return (
    <AppLayout variant="sponsor" title={title} subtitle={subtitle}>
      <Routes>
        <Route index element={<Overview />} />
        <Route path="queue" element={<Queue />} />
        <Route path="plan-activity" element={<PlanActivityPage />} />
        <Route path="participants" element={<ParticipantsPage />} />
        <Route path="participants/:participantId" element={<ParticipantActivityPage />} />
        <Route path="audit" element={<AuditLog />} />
        <Route path="blackout" element={<BlackoutManager />} />
      </Routes>
    </AppLayout>
  );
}
