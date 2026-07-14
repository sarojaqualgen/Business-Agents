import React from 'react';
import { Route, Routes, useLocation } from 'react-router-dom';
import AppLayout from '../../../components/layout/AppLayout.jsx';
import Overview from './Overview.jsx';
import Queue from './Queue.jsx';
import AuditLog from './AuditLog.jsx';
import BlackoutManager from './BlackoutManager.jsx';

// Per-route header copy so the sticky top bar always reflects the page
// you're actually on, instead of a single static title for the whole
// sponsor shell. Matched against the tail segment of the pathname.
const HEADERS = {
  '': { title: 'Plan Sponsor Overview', subtitle: 'Plan health and pending activity' },
  queue: { title: 'Review Queue', subtitle: 'Requests awaiting your approval' },
  audit: { title: 'Audit Log', subtitle: 'Compliance decision history for this plan' },
  blackout: { title: 'Blackout Manager', subtitle: 'Restrict transactions during a blackout period' },
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
        <Route path="audit" element={<AuditLog />} />
        <Route path="blackout" element={<BlackoutManager />} />
      </Routes>
    </AppLayout>
  );
}
