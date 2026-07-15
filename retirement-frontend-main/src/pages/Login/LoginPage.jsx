import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import { apiClient } from '../../lib/apiClient.js';

const TRUST_ITEMS = [
  { label: '12-Rule ERISA Compliance Engine', detail: 'Every action gates through FAP before execution' },
  { label: 'SECURE 2.0 & IRC §72(p) Ready', detail: 'Roth catch-up, RMD reform, loan cap enforcement built-in' },
  { label: 'ERISA §107 Audit Retention', detail: '6-year FAP audit trail — DOL-ready on demand' },
];

function PersonIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ width: 22, height: 22 }}>
      <circle cx="12" cy="8" r="4" /><path d="M4 20c0-4 3.6-7 8-7s8 3 8 7" />
    </svg>
  );
}

function BuildingIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ width: 22, height: 22 }}>
      <rect x="3" y="3" width="18" height="18" rx="2" /><path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01M9 3v18M3 9h18" />
    </svg>
  );
}

function ArrowRight() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={{ width: 16, height: 16 }}>
      <path d="M5 12h14M13 6l6 6-6 6" />
    </svg>
  );
}

function ChevronLeft() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={{ width: 14, height: 14 }}>
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}

const ROLES = [
  {
    value: 'participant',
    label: 'Employee',
    sub: 'Participant',
    desc: 'View your account, request loans, change contributions',
    Icon: PersonIcon,
  },
  {
    value: 'plan_sponsor',
    label: 'Administrator',
    sub: 'Plan Sponsor',
    desc: 'Manage the plan, approve requests, view the audit log',
    Icon: BuildingIcon,
  },
];

// Detect mobile so we skip the hero animation
function isMobile() {
  return typeof window !== 'undefined' && window.innerWidth < 1024;
}

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  // 'hero' → 'split' (desktop only); mobile always starts in 'split'
  const [phase, setPhase] = useState(() => (isMobile() ? 'split' : 'hero'));
  // Within the form: null → 'participant' | 'plan_sponsor'
  const [principalType, setPrincipalType] = useState(null);
  const [participantId, setParticipantId] = useState('');
  const [planId, setPlanId] = useState('');
  const [participants, setParticipants] = useState([]);
  const [plans, setPlans] = useState([]);
  const [formError, setFormError] = useState(null);
  // Stagger the entrance of hero content
  const [heroIn, setHeroIn] = useState(false);
  // Stagger form content after panel slides in
  const [formIn, setFormIn] = useState(false);

  useEffect(() => { setTimeout(() => setHeroIn(true), 60); }, []);

  useEffect(() => {
    if (isAuthenticated) {
      const dest = location.state?.from?.pathname || (principalType === 'plan_sponsor' ? '/sponsor' : '/participant');
      navigate(dest, { replace: true });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated]);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [pRes, plRes] = await Promise.all([apiClient.listParticipants(), apiClient.listPlans()]);
        if (cancelled) return;
        const ps = pRes.participants || [];
        const pls = plRes.plans || [];
        setParticipants(ps);
        setPlans(pls);
        if (ps[0]) { setParticipantId(ps[0].participant_id); setPlanId(ps[0].plan_id || ''); }
        else if (pls[0]) setPlanId(pls[0].plan_id || '');
      } catch { /* silent */ }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  function handleParticipantChange(id) {
    setParticipantId(id);
    const m = participants.find(p => p.participant_id === id);
    if (m) setPlanId(m.plan_id || '');
  }

  function selectRole(role) {
    setPrincipalType(role);
    if (role === 'plan_sponsor' && plans[0]) setPlanId(plans[0].plan_id);
    setFormError(null);
  }

  function openPortal() {
    setPhase('split');
    setTimeout(() => setFormIn(true), 500);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError(null);
    try {
      await login({ principalType, participantId: principalType === 'participant' ? participantId : null, planId });
    } catch (err) {
      setFormError(err.message || 'Login failed. Please try again.');
    }
  }

  const isSplit = phase === 'split';

  return (
    <>
      <style>{`
        @keyframes orb-drift-a {
          0%,100% { transform: translate(0px, 0px) scale(1); }
          30%      { transform: translate(-28px, 22px) scale(1.06); }
          60%      { transform: translate(22px, -16px) scale(0.94); }
        }
        @keyframes orb-drift-b {
          0%,100% { transform: translate(0px, 0px) scale(1); }
          35%     { transform: translate(18px, -24px) scale(0.96); }
          70%     { transform: translate(-14px, 12px) scale(1.04); }
        }
        @keyframes orb-drift-c {
          0%,100% { transform: translate(0px, 0px); }
          50%     { transform: translate(10px, -10px); }
        }
        @keyframes hero-in {
          from { opacity: 0; transform: translateY(28px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes form-slide-in {
          from { opacity: 0; transform: translateY(18px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes role-pop {
          from { opacity: 0; transform: translateY(12px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        .role-card { transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease; }
        .role-card:hover { border-color: #F97316 !important; box-shadow: 0 4px 16px rgba(249,115,22,0.14); transform: translateY(-1px); }
        .access-btn:hover { background: #EA6C0C !important; box-shadow: 0 6px 28px rgba(249,115,22,0.42) !important; transform: translateY(-1px); }
        .access-btn:active { transform: translateY(0); }
        .back-link { transition: color 0.15s ease; }
        .back-link:hover { color: #F97316 !important; }
        .sign-in-btn { transition: background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease; }
        .sign-in-btn:hover:not(:disabled) { background: #EA6C0C !important; transform: translateY(-1px); box-shadow: 0 4px 16px rgba(249,115,22,0.3); }
        .sign-in-btn:active:not(:disabled) { transform: translateY(0); }
      `}</style>

      <div style={{
        minHeight: '100vh', display: 'flex', overflow: 'hidden',
        background: '#151B2C',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      }}>

        {/* ── Left Brand Panel ─────────────────────────────────────────── */}
        <div style={{
          width: isSplit ? '44%' : '100%',
          minWidth: isSplit ? 0 : undefined,
          flexShrink: 0,
          position: 'relative',
          overflow: 'hidden',
          background: '#151B2C',
          display: 'flex',
          flexDirection: 'column',
          padding: isSplit ? '48px 44px' : '64px 80px',
          justifyContent: isSplit ? 'center' : 'space-between',
          transition: 'width 0.8s cubic-bezier(0.16, 1, 0.3, 1), padding 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>

          {/* Ambient orbs */}
          <div aria-hidden="true" style={{
            position: 'absolute', top: '-20%', right: '-12%',
            width: 480, height: 480, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(249,115,22,0.16) 0%, transparent 68%)',
            animation: 'orb-drift-a 20s ease-in-out infinite',
            pointerEvents: 'none',
          }} />
          <div aria-hidden="true" style={{
            position: 'absolute', bottom: '-18%', left: '-12%',
            width: 400, height: 400, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(249,115,22,0.09) 0%, transparent 68%)',
            animation: 'orb-drift-b 26s ease-in-out infinite',
            pointerEvents: 'none',
          }} />
          <div aria-hidden="true" style={{
            position: 'absolute', top: '40%', right: '5%',
            width: 180, height: 180, borderRadius: '50%',
            background: 'radial-gradient(circle, rgba(255,255,255,0.03) 0%, transparent 70%)',
            animation: 'orb-drift-c 14s ease-in-out infinite',
            pointerEvents: 'none',
          }} />

          {/* Grid */}
          <div aria-hidden="true" style={{
            position: 'absolute', inset: 0, pointerEvents: 'none',
            backgroundImage: 'linear-gradient(rgba(255,255,255,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.025) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }} />

          {/* Logo */}
          <div style={{
            position: 'relative', zIndex: 10,
            opacity: heroIn ? 1 : 0,
            transform: heroIn ? 'translateY(0)' : 'translateY(16px)',
            transition: 'opacity 0.55s ease-out, transform 0.55s ease-out',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 42, height: 42, borderRadius: 11, background: '#F97316',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontWeight: 800, fontSize: 17, flexShrink: 0,
                boxShadow: '0 2px 12px rgba(249,115,22,0.35)',
              }}>Q</div>
              <div>
                <div style={{ color: '#fff', fontSize: 20, fontWeight: 700, lineHeight: 1 }}>Qualgen</div>
                <div style={{ color: '#F97316', fontSize: 10, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.08em', marginTop: 2 }}>RETIREMENT PLATFORM</div>
              </div>
            </div>
          </div>

          {/* ── HERO content (only in hero phase) ── */}
          {!isSplit && (
            <div style={{
              position: 'relative', zIndex: 10,
              flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center',
              maxWidth: 560,
              opacity: heroIn ? 1 : 0,
              animation: heroIn ? 'hero-in 0.65s ease-out 0.15s both' : 'none',
            }}>
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                background: 'rgba(249,115,22,0.12)', border: '1px solid rgba(249,115,22,0.25)',
                borderRadius: 999, padding: '5px 14px', marginBottom: 28,
                width: 'fit-content',
              }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F97316' }} />
                <span style={{ color: '#F97316', fontSize: 11, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.06em' }}>
                  ERISA-COMPLIANT · SECURE 2.0 READY
                </span>
              </div>

              <h1 style={{
                color: '#fff', fontWeight: 800, lineHeight: 1.08,
                fontSize: 'clamp(38px, 5.5vw, 62px)',
                marginBottom: 22, letterSpacing: '-0.02em',
              }}>
                401(k) administration<br />
                <span style={{ color: '#F97316' }}>built for trust.</span>
              </h1>

              <p style={{ color: '#9AA2B4', fontSize: 17, lineHeight: 1.7, maxWidth: 440, marginBottom: 48 }}>
                Every participant action gates through a 12-rule fiduciary compliance engine before execution. No exceptions.
              </p>

              {/* Trust items */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 18, marginBottom: 56 }}>
                {TRUST_ITEMS.map((item, i) => (
                  <div key={item.label} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 14,
                    opacity: heroIn ? 1 : 0,
                    animation: heroIn ? `hero-in 0.5s ease-out ${0.3 + i * 0.08}s both` : 'none',
                  }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: 6,
                      background: 'rgba(249,115,22,0.12)',
                      border: '1px solid rgba(249,115,22,0.2)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      flexShrink: 0,
                    }}>
                      <div style={{ width: 7, height: 7, borderRadius: '50%', background: '#F97316' }} />
                    </div>
                    <div>
                      <div style={{ color: '#fff', fontSize: 14, fontWeight: 600 }}>{item.label}</div>
                      <div style={{ color: '#9AA2B4', fontSize: 12, marginTop: 2 }}>{item.detail}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* CTA */}
              <button
                className="access-btn"
                onClick={openPortal}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 10,
                  background: '#F97316', color: '#fff', border: 'none',
                  borderRadius: 12, padding: '15px 32px',
                  fontSize: 16, fontWeight: 700, cursor: 'pointer',
                  width: 'fit-content',
                  boxShadow: '0 4px 20px rgba(249,115,22,0.3)',
                  animation: heroIn ? 'hero-in 0.5s ease-out 0.55s both' : 'none',
                  transition: 'background 0.2s ease, box-shadow 0.2s ease, transform 0.15s ease',
                }}
              >
                Access Portal <ArrowRight />
              </button>
            </div>
          )}

          {/* ── COMPACT content (inside split phase) ── */}
          {isSplit && (
            <div style={{
              position: 'relative', zIndex: 10, marginTop: 40,
              animation: 'hero-in 0.5s ease-out 0.1s both',
            }}>
              <h2 style={{
                color: '#fff', fontWeight: 700, fontSize: 26,
                lineHeight: 1.2, letterSpacing: '-0.01em', marginBottom: 28,
              }}>
                401(k)<br />administration<br />
                <span style={{ color: '#F97316' }}>built for trust.</span>
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {TRUST_ITEMS.map(item => (
                  <div key={item.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F97316', marginTop: 5, flexShrink: 0 }} />
                    <div>
                      <div style={{ color: '#fff', fontSize: 12, fontWeight: 600 }}>{item.label}</div>
                      <div style={{ color: '#9AA2B4', fontSize: 11, marginTop: 1 }}>{item.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{
                marginTop: 40, paddingTop: 20,
                borderTop: '1px solid rgba(255,255,255,0.07)',
                color: '#5B6478', fontSize: 10, fontFamily: 'ui-monospace, monospace',
              }}>
                qualgen.ai · Demo environment · No real data
              </div>
            </div>
          )}
        </div>

        {/* ── Right Form Panel ─────────────────────────────────────────── */}
        <div style={{
          flex: isSplit ? 1 : 0,
          minWidth: 0,
          overflow: 'hidden',
          background: '#F6F7F9',
          display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
          padding: isSplit ? '48px 40px' : '0',
          opacity: isSplit ? 1 : 0,
          transition: 'flex 0.8s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.45s ease-out 0.35s, padding 0.8s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>
          <div style={{
            width: '100%', maxWidth: 400,
            transform: formIn ? 'translateX(0)' : 'translateX(32px)',
            opacity: formIn ? 1 : 0,
            transition: 'transform 0.55s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.45s ease-out',
          }}>
            {/* Form heading */}
            <div style={{ marginBottom: 28 }}>
              <h2 style={{ fontSize: 22, fontWeight: 700, color: '#151B2C', margin: 0 }}>Sign in</h2>
              <p style={{ fontSize: 13, color: '#9AA2B4', marginTop: 5 }}>
                {principalType ? 'Enter your details below.' : 'Choose your role to continue.'}
              </p>
            </div>

            {/* Role cards — shown when no role selected */}
            {!principalType && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {ROLES.map((role, i) => (
                  <button
                    key={role.value}
                    className="role-card"
                    onClick={() => selectRole(role.value)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 16,
                      padding: '18px 20px',
                      background: '#fff', border: '1.5px solid #E5E8EF',
                      borderRadius: 14, cursor: 'pointer', textAlign: 'left', width: '100%',
                      animation: formIn ? `role-pop 0.4s cubic-bezier(0.16,1,0.3,1) ${0.05 + i * 0.07}s both` : 'none',
                    }}
                  >
                    <div style={{
                      width: 44, height: 44, borderRadius: 10,
                      background: '#FFF7ED', color: '#C2410C',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      <role.Icon />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                        <span style={{ fontSize: 15, fontWeight: 700, color: '#151B2C' }}>{role.label}</span>
                        <span style={{ fontSize: 11, color: '#9AA2B4', fontFamily: 'ui-monospace, monospace' }}>{role.sub}</span>
                      </div>
                      <div style={{ fontSize: 12, color: '#9AA2B4', marginTop: 2, lineHeight: 1.4 }}>{role.desc}</div>
                    </div>
                    <div style={{ color: '#D4D9E3', flexShrink: 0 }}><ArrowRight /></div>
                  </button>
                ))}
              </div>
            )}

            {/* Form — shown after role selected */}
            {principalType && (
              <div style={{ animation: 'form-slide-in 0.35s cubic-bezier(0.16, 1, 0.3, 1)' }}>
                {/* Back to role select */}
                <button
                  className="back-link"
                  onClick={() => { setPrincipalType(null); setFormError(null); }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    color: '#9AA2B4', fontSize: 12, cursor: 'pointer',
                    background: 'none', border: 'none', padding: 0, marginBottom: 20,
                  }}
                >
                  <ChevronLeft />
                  {ROLES.find(r => r.value === principalType)?.label}
                </button>

                <div style={{
                  background: '#fff', borderRadius: 16,
                  border: '1px solid #E5E8EF',
                  padding: '28px 24px',
                  boxShadow: '0 1px 3px rgba(16,24,40,0.06)',
                }}>
                  <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
                    {principalType === 'participant' ? (
                      <div>
                        <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#9AA2B4', letterSpacing: '0.06em', marginBottom: 7 }}>
                          YOUR ACCOUNT
                        </label>
                        <select
                          className="input-field"
                          value={participantId}
                          onChange={e => handleParticipantChange(e.target.value)}
                        >
                          {participants.length === 0 && <option>Loading…</option>}
                          {participants.map(p => (
                            <option key={p.participant_id} value={p.participant_id}>
                              {p.display_name || p.participant_id}{p.plan_id ? ` · ${p.plan_id}` : ''}
                            </option>
                          ))}
                        </select>
                        {planId && (
                          <p style={{ fontSize: 10, color: '#9AA2B4', marginTop: 5, fontFamily: 'ui-monospace, monospace' }}>Plan: {planId}</p>
                        )}
                      </div>
                    ) : (
                      <div>
                        <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#9AA2B4', letterSpacing: '0.06em', marginBottom: 7 }}>
                          PLAN TO MANAGE
                        </label>
                        <select
                          className="input-field"
                          value={planId}
                          onChange={e => setPlanId(e.target.value)}
                        >
                          {plans.length === 0 && <option>Loading…</option>}
                          {plans.map(p => (
                            <option key={p.plan_id} value={p.plan_id}>
                              {p.plan_name || p.plan_id}
                            </option>
                          ))}
                        </select>
                      </div>
                    )}

                    {formError && (
                      <div style={{
                        fontSize: 12, color: '#DC2626', background: '#FEF2F2',
                        border: '1px solid #FECACA', borderRadius: 8, padding: '10px 12px',
                      }}>
                        {formError}
                      </div>
                    )}

                    <button
                      type="submit"
                      className="sign-in-btn"
                      disabled={isLoading}
                      style={{
                        background: '#F97316', color: '#fff', border: 'none',
                        borderRadius: 10, padding: '13px',
                        fontSize: 15, fontWeight: 700, cursor: isLoading ? 'not-allowed' : 'pointer',
                        opacity: isLoading ? 0.65 : 1,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8,
                        boxShadow: '0 2px 10px rgba(249,115,22,0.22)',
                      }}
                    >
                      {isLoading ? 'Signing in…' : <>Sign In <ArrowRight /></>}
                    </button>
                  </form>
                </div>

                <p style={{ fontSize: 10, color: '#9AA2B4', textAlign: 'center', marginTop: 16, fontFamily: 'ui-monospace, monospace' }}>
                  Demo login — no password required
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
