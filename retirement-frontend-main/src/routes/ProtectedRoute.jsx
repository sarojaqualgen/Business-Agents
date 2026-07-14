import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext.jsx';

const PARTICIPANT_TYPES = new Set(['participant', 'participant_delegate', 'investment_advisor']);
const SPONSOR_TYPES = new Set(['plan_sponsor', 'plan_trustee']);

/**
 * Guards a route behind an active session, and optionally behind a role
 * ("participant" | "sponsor"). Unauthenticated users are bounced to /login
 * with their intended destination preserved for a post-login redirect.
 */
export default function ProtectedRoute({ role, children }) {
  const { isAuthenticated, principal } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (role === 'participant' && !PARTICIPANT_TYPES.has(principal?.principalType)) {
    return <Navigate to="/sponsor" replace />;
  }

  if (role === 'sponsor' && !SPONSOR_TYPES.has(principal?.principalType)) {
    return <Navigate to="/participant" replace />;
  }

  return children;
}
