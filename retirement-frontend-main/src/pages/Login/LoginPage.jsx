import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import { apiClient } from '../../lib/apiClient.js';

const PRINCIPAL_TYPES = [
  { value: 'participant', label: 'Employee (Participant)' },
  { value: 'plan_sponsor', label: 'Plan Administrator' },
];

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [principalType, setPrincipalType] = useState('participant');
  const [participantId, setParticipantId] = useState('');
  const [planId, setPlanId] = useState('');
  const [participants, setParticipants] = useState([]);
  const [plans, setPlans] = useState([]);
  const [formError, setFormError] = useState(null);

  const isParticipant = principalType === 'participant';
  const isSponsor = principalType === 'plan_sponsor';

  useEffect(() => {
    if (isAuthenticated) {
      const dest = location.state?.from?.pathname || (isSponsor ? '/sponsor' : '/participant');
      navigate(dest, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  useEffect(() => {
    let cancelled = false;
    async function loadLookups() {
      const [participantsRes, plansRes] = await Promise.all([
        apiClient.listParticipants(),
        apiClient.listPlans(),
      ]);
      if (cancelled) return;
      const allParticipants = participantsRes.participants || [];
      const allPlans = plansRes.plans || [];
      setParticipants(allParticipants);
      setPlans(allPlans);

      // Default participant to first on list; plan derives from participant.
      const firstParticipant = allParticipants[0];
      if (firstParticipant) {
        setParticipantId(firstParticipant.participant_id);
        setPlanId(firstParticipant.plan_id || '');
      }

      // Default sponsor plan to first available plan.
      const firstPlan = allPlans[0];
      if (firstPlan && !firstParticipant) setPlanId(firstPlan.plan_id || '');
    }
    loadLookups();
    return () => { cancelled = true; };
  }, []);

  // When a participant is selected, their plan is auto-derived.
  function handleParticipantChange(id) {
    setParticipantId(id);
    const match = participants.find((p) => p.participant_id === id);
    if (match) setPlanId(match.plan_id || '');
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError(null);
    try {
      await login({
        principalType,
        participantId: isParticipant ? participantId : null,
        planId: isSponsor ? planId : planId, // always pass planId; derived for participant
      });
    } catch (err) {
      setFormError(err.message || 'Login failed. Please try again.');
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center px-4"
      style={{
        background: 'linear-gradient(160deg, #FFF7ED 0%, #F6F7F9 45%, #F1F3F6 100%)',
      }}
    >
      <div className="card w-full max-w-[400px] p-10">
        {/* Brand */}
        <div className="flex items-center gap-3 mb-7">
          <div className="w-9 h-9 rounded-lg bg-accent flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            A
          </div>
          <div>
            <div className="text-[20px] font-bold text-text leading-tight">Aldergate</div>
            <div className="text-[11px] text-text-faint">ERISA 401(k) Compliance Console</div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Role */}
          <div>
            <label className="label-mono" htmlFor="principalType">
              I am a
            </label>
            <select
              id="principalType"
              className="input-field"
              value={principalType}
              onChange={(e) => setPrincipalType(e.target.value)}
            >
              {PRINCIPAL_TYPES.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Participant: select your account — plan is auto-derived */}
          {isParticipant && (
            <div>
              <label className="label-mono" htmlFor="participantId">
                Your account
              </label>
              <select
                id="participantId"
                className="input-field"
                value={participantId}
                onChange={(e) => handleParticipantChange(e.target.value)}
              >
                {participants.length === 0 && <option value="">Loading participants…</option>}
                {participants.map((p) => (
                  <option key={p.participant_id} value={p.participant_id}>
                    {p.display_name || p.participant_id}
                    {p.plan_id ? ` · ${p.plan_id}` : ''}
                  </option>
                ))}
              </select>
              {planId && (
                <p className="text-[10px] text-text-faint mt-1.5 font-mono">
                  Plan: {planId}
                </p>
              )}
            </div>
          )}

          {/* Sponsor: select the plan to manage */}
          {isSponsor && (
            <div>
              <label className="label-mono" htmlFor="planId">
                Plan to manage
              </label>
              <select
                id="planId"
                className="input-field"
                value={planId}
                onChange={(e) => setPlanId(e.target.value)}
              >
                {plans.length === 0 && <option value="">Loading plans…</option>}
                {plans.map((p) => (
                  <option key={p.plan_id} value={p.plan_id}>
                    {p.plan_name || p.plan_id}
                  </option>
                ))}
              </select>
            </div>
          )}

          {formError && <p className="text-danger text-xs">{formError}</p>}

          <button type="submit" className="btn-primary mt-2" disabled={isLoading}>
            {isLoading ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        <p className="text-[11px] text-text-faint mt-5 font-mono leading-relaxed">
          Demo login — no password required. Sessions reflect the FastAPI /auth/login contract.
        </p>
      </div>
    </div>
  );
}
