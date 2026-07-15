import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import { apiClient } from '../../lib/apiClient.js';

const PRINCIPAL_TYPES = [
  { value: 'participant', label: 'Employee (Participant)' },
  { value: 'plan_sponsor', label: 'Plan Administrator' },
];

const TRUST_ITEMS = [
  {
    label: '12-Rule ERISA Compliance Engine',
    detail: 'Every action gates through FAP before execution',
  },
  {
    label: 'SECURE 2.0 & IRC §72(p) Ready',
    detail: 'Roth catch-up, RMD reform, and loan cap enforcement built-in',
  },
  {
    label: 'ERISA §107 Audit Retention',
    detail: '6-year FAP audit trail — DOL-ready on demand',
  },
];

function ShieldIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4 flex-shrink-0 mt-0.5">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}

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

      const firstParticipant = allParticipants[0];
      if (firstParticipant) {
        setParticipantId(firstParticipant.participant_id);
        setPlanId(firstParticipant.plan_id || '');
      }

      const firstPlan = allPlans[0];
      if (firstPlan && !firstParticipant) setPlanId(firstPlan.plan_id || '');
    }
    loadLookups();
    return () => { cancelled = true; };
  }, []);

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
        planId: planId,
      });
    } catch (err) {
      setFormError(err.message || 'Login failed. Please try again.');
    }
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left brand panel ─────────────────────────────────────────────── */}
      <div
        className="hidden lg:flex lg:w-[44%] xl:w-[42%] flex-col justify-between px-12 py-14 relative overflow-hidden"
        style={{ background: '#151B2C' }}
      >
        {/* Subtle grid overlay */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />
        {/* Orange accent glow — top-right */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-32 -right-32 w-72 h-72 rounded-full"
          style={{
            background: 'radial-gradient(circle, rgba(249,115,22,0.18) 0%, transparent 70%)',
          }}
        />

        {/* Logo */}
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl bg-accent flex items-center justify-center text-white font-bold text-base flex-shrink-0 shadow-lg">
              Q
            </div>
            <div>
              <div className="text-white text-xl font-bold leading-tight tracking-tight">Qualgen</div>
              <div className="text-[11px] font-mono" style={{ color: '#F97316', letterSpacing: '0.06em' }}>
                RETIREMENT PLATFORM
              </div>
            </div>
          </div>

          <h1
            className="text-white font-bold leading-tight mb-4"
            style={{ fontSize: 'clamp(28px, 3vw, 38px)' }}
          >
            ERISA-grade&nbsp;401(k)<br />
            administration,<br />
            built for compliance.
          </h1>
          <p className="text-sm leading-relaxed" style={{ color: '#9AA2B4', maxWidth: '340px' }}>
            Every participant action gates through a 12-rule fiduciary compliance
            engine before execution. No exceptions.
          </p>
        </div>

        {/* Trust items */}
        <div className="relative z-10 space-y-5">
          {TRUST_ITEMS.map((item) => (
            <div key={item.label} className="flex items-start gap-3">
              <span style={{ color: '#F97316' }}>
                <ShieldIcon />
              </span>
              <div>
                <div className="text-[13px] font-semibold text-white leading-snug">{item.label}</div>
                <div className="text-[12px] mt-0.5" style={{ color: '#9AA2B4' }}>{item.detail}</div>
              </div>
            </div>
          ))}

          <div
            className="mt-8 pt-6 text-[11px] font-mono"
            style={{ borderTop: '1px solid rgba(255,255,255,0.08)', color: '#5B6478' }}
          >
            qualgen.ai · Demo environment · No real data
          </div>
        </div>
      </div>

      {/* ── Right form panel ─────────────────────────────────────────────── */}
      <div className="flex-1 flex flex-col items-center justify-center px-6 py-10" style={{ background: '#F6F7F9' }}>
        {/* Mobile-only logo */}
        <div className="flex items-center gap-2.5 mb-8 lg:hidden">
          <div className="w-9 h-9 rounded-xl bg-accent flex items-center justify-center text-white font-bold text-sm flex-shrink-0">
            Q
          </div>
          <div>
            <div className="text-[18px] font-bold text-text leading-tight">Qualgen</div>
            <div className="text-[11px] text-accent font-mono" style={{ letterSpacing: '0.06em' }}>RETIREMENT PLATFORM</div>
          </div>
        </div>

        <div className="w-full max-w-[400px]">
          {/* Heading */}
          <div className="mb-8">
            <h2 className="text-[22px] font-bold text-text leading-tight">Sign in</h2>
            <p className="text-sm text-text-muted mt-1">Select your role to access the portal.</p>
          </div>

          <div className="card p-8">
            <form onSubmit={handleSubmit} className="space-y-5">
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

              {/* Participant: select account — plan is auto-derived */}
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
                    {participants.length === 0 && <option value="">Loading…</option>}
                    {participants.map((p) => (
                      <option key={p.participant_id} value={p.participant_id}>
                        {p.display_name || p.participant_id}
                        {p.plan_id ? ` · ${p.plan_id}` : ''}
                      </option>
                    ))}
                  </select>
                  {planId && (
                    <p className="text-[10px] text-text-faint mt-1.5 font-mono">Plan: {planId}</p>
                  )}
                </div>
              )}

              {/* Sponsor: select plan */}
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
                    {plans.length === 0 && <option value="">Loading…</option>}
                    {plans.map((p) => (
                      <option key={p.plan_id} value={p.plan_id}>
                        {p.plan_name || p.plan_id}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {formError && (
                <p className="text-danger text-xs bg-danger/5 border border-danger/20 rounded-md px-3 py-2">
                  {formError}
                </p>
              )}

              <button type="submit" className="btn-primary mt-1" disabled={isLoading}>
                {isLoading ? 'Signing in…' : 'Sign In'}
              </button>
            </form>
          </div>

          <p className="text-[11px] text-text-faint mt-5 text-center font-mono">
            Demo login — no password required
          </p>
        </div>
      </div>
    </div>
  );
}
