import React from 'react';
import { Navigate, Route, Routes } from 'react-router-dom';
import LoginPage from './pages/Login/LoginPage.jsx';
import ParticipantDashboard from './pages/Dashboard/Participant/ParticipantDashboard.jsx';
import SponsorDashboard from './pages/Dashboard/Sponsor/SponsorDashboard.jsx';
import NotFoundPage from './pages/NotFoundPage.jsx';
import ProtectedRoute from './routes/ProtectedRoute.jsx';
import { useAuth } from './context/AuthContext.jsx';

function RootRedirect() {
  const { isAuthenticated, principal } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  const isSponsor = principal?.principalType === 'plan_sponsor' || principal?.principalType === 'plan_trustee';
  return <Navigate to={isSponsor ? '/sponsor' : '/participant'} replace />;
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/participant/*"
        element={
          <ProtectedRoute role="participant">
            <ParticipantDashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/sponsor/*"
        element={
          <ProtectedRoute role="sponsor">
            <SponsorDashboard />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  );
}
