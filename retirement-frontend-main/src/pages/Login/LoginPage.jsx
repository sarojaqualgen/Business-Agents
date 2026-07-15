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

function ArrowRight({ size = 16 }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" style={{ width: size, height: size }}>
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
  { value: 'participant',  label: 'Employee',       sub: 'Participant',  desc: 'View your account, request loans, change contributions', Icon: PersonIcon },
  { value: 'plan_sponsor', label: 'Administrator',  sub: 'Plan Sponsor', desc: 'Manage the plan, approve requests, view the audit log',  Icon: BuildingIcon },
];

function isMobile() {
  return typeof window !== 'undefined' && window.innerWidth < 1024;
}

// Dark charcoal with a barely-visible diagonal technical-drawing stripe.
// No gradient blobs — those read as generic AI design.
const PANEL_BG = '#0C0E14';
const STRIPE_BG = `
  ${PANEL_BG}
`;
const STRIPE_TEXTURE = `repeating-linear-gradient(
  -52deg,
  transparent,
  transparent 18px,
  rgba(255,255,255,0.018) 18px,
  rgba(255,255,255,0.018) 19px
)`;

export default function LoginPage() {
  const { login, isAuthenticated, isLoading } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [phase, setPhase]               = useState(() => (isMobile() ? 'split' : 'hero'));
  const [principalType, setPrincipalType] = useState(null);
  const [participantId, setParticipantId] = useState('');
  const [planId, setPlanId]               = useState('');
  const [participants, setParticipants]   = useState([]);
  const [plans, setPlans]                 = useState([]);
  const [formError, setFormError]         = useState(null);
  const [heroIn, setHeroIn]               = useState(false);
  const [formIn, setFormIn]               = useState(false);

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
        const ps  = pRes.participants || [];
        const pls = plRes.plans || [];
        setParticipants(ps);
        setPlans(pls);
        if (ps[0])       { setParticipantId(ps[0].participant_id); setPlanId(ps[0].plan_id || ''); }
        else if (pls[0]) { setPlanId(pls[0].plan_id || ''); }
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
    setTimeout(() => setFormIn(true), 480);
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
        @keyframes hero-in {
          from { opacity: 0; transform: translateY(24px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes form-slide-in {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes role-pop {
          from { opacity: 0; transform: translateY(10px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        /* Subtle left-border accent line crawls in on load */
        @keyframes line-grow {
          from { height: 0; }
          to   { height: 80px; }
        }
        .portal-btn {
          transition: background 0.18s ease, box-shadow 0.18s ease, transform 0.15s ease;
        }
        .portal-btn:hover {
          background: rgba(249,115,22,0.15) !important;
          box-shadow: 0 0 0 1px rgba(249,115,22,0.4);
          transform: translateX(2px);
        }
        .role-card {
          transition: border-color 0.16s ease, box-shadow 0.16s ease, transform 0.16s ease;
        }
        .role-card:hover {
          border-color: #F97316 !important;
          box-shadow: 0 0 0 1px rgba(249,115,22,0.25), 0 4px 14px rgba(249,115,22,0.1);
          transform: translateY(-1px);
        }
        .back-link:hover { color: #F97316 !important; }
        .sign-in-btn { transition: background 0.18s ease, transform 0.15s ease, box-shadow 0.15s ease; }
        .sign-in-btn:hover:not(:disabled) {
          background: #EA6C0C !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(249,115,22,0.28);
        }
        .sign-in-btn:active:not(:disabled) { transform: translateY(0); }
      `}</style>

      <div style={{
        minHeight: '100vh', display: 'flex', overflow: 'hidden',
        background: PANEL_BG,
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
      }}>

        {/* ══════════════════════════════════════════════════════════
            LEFT BRAND PANEL
        ══════════════════════════════════════════════════════════ */}
        <div style={{
          width: isSplit ? '44%' : '100%',
          flexShrink: 0,
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          // Diagonal stripe on top of solid base
          background: PANEL_BG,
          backgroundImage: STRIPE_TEXTURE,
          transition: 'width 0.82s cubic-bezier(0.16, 1, 0.3, 1)',
        }}>

          {/* Left-edge accent bar — always visible, draws on load */}
          <div style={{
            position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
            width: 3, height: heroIn ? 80 : 0,
            background: 'linear-gradient(180deg, transparent, #F97316, transparent)',
            transition: 'height 0.7s ease-out 0.3s',
            borderRadius: 2,
          }} />

          {/* ── HEADER ROW: logo left + portal button right ── */}
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            padding: isSplit ? '32px 44px 0' : '44px 72px 0',
            position: 'relative', zIndex: 10,
            opacity: heroIn ? 1 : 0,
            transform: heroIn ? 'translateY(0)' : 'translateY(-10px)',
            transition: 'opacity 0.5s ease-out, transform 0.5s ease-out, padding 0.82s cubic-bezier(0.16,1,0.3,1)',
          }}>
            {/* Logo */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{
                width: 38, height: 38, borderRadius: 10,
                background: '#F97316',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: '#fff', fontWeight: 800, fontSize: 16, flexShrink: 0,
                boxShadow: '0 2px 10px rgba(249,115,22,0.3)',
              }}>Q</div>
              <div>
                <div style={{ color: '#fff', fontSize: 18, fontWeight: 700, lineHeight: 1 }}>Qualgen</div>
                <div style={{ color: '#F97316', fontSize: 9, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.09em', marginTop: 3 }}>
                  RETIREMENT PLATFORM
                </div>
              </div>
            </div>

            {/* Access Portal — top right, hidden when already split */}
            {!isSplit && (
              <button
                className="portal-btn"
                onClick={openPortal}
                style={{
                  display: 'inline-flex', alignItems: 'center', gap: 7,
                  background: 'rgba(249,115,22,0.08)',
                  border: '1px solid rgba(249,115,22,0.28)',
                  borderRadius: 8,
                  padding: '8px 16px',
                  color: '#F97316', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  letterSpacing: '0.01em',
                }}
              >
                Access Portal <ArrowRight size={13} />
              </button>
            )}
          </div>

          {/* ── HERO BODY (landing phase) ── */}
          {!isSplit && (
            <div style={{
              position: 'relative', zIndex: 10,
              flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center',
              padding: '0 72px',
              maxWidth: 600,
            }}>
              {/* ERISA pill — more space from logo (padding-top on parent does it naturally) */}
              <div style={{
                display: 'inline-flex', alignItems: 'center', gap: 8,
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 6, padding: '5px 12px',
                marginBottom: 28, width: 'fit-content',
                opacity: heroIn ? 1 : 0,
                animation: heroIn ? 'hero-in 0.5s ease-out 0.05s both' : 'none',
              }}>
                <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#F97316', flexShrink: 0 }} />
                <span style={{ color: 'rgba(255,255,255,0.45)', fontSize: 10, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.07em' }}>
                  ERISA-COMPLIANT · SECURE 2.0 READY
                </span>
              </div>

              <h1 style={{
                color: '#fff', fontWeight: 800, lineHeight: 1.06,
                fontSize: 'clamp(40px, 5.5vw, 64px)',
                letterSpacing: '-0.025em', marginBottom: 20,
                opacity: heroIn ? 1 : 0,
                animation: heroIn ? 'hero-in 0.55s ease-out 0.12s both' : 'none',
              }}>
                401(k) administration<br />
                <span style={{ color: '#F97316' }}>built for trust.</span>
              </h1>

              <p style={{
                color: 'rgba(255,255,255,0.42)', fontSize: 16, lineHeight: 1.75,
                maxWidth: 420, marginBottom: 52,
                opacity: heroIn ? 1 : 0,
                animation: heroIn ? 'hero-in 0.5s ease-out 0.2s both' : 'none',
              }}>
                Every participant action gates through a 12-rule fiduciary
                compliance engine before execution. No exceptions.
              </p>

              {/* Trust items */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
                {TRUST_ITEMS.map((item, i) => (
                  <div key={item.label} style={{
                    display: 'flex', alignItems: 'flex-start', gap: 14,
                    opacity: heroIn ? 1 : 0,
                    animation: heroIn ? `hero-in 0.45s ease-out ${0.28 + i * 0.08}s both` : 'none',
                  }}>
                    {/* Small square bracket accent — not a blob */}
                    <div style={{
                      width: 4, height: 4, borderRadius: 1,
                      background: '#F97316', marginTop: 7, flexShrink: 0,
                    }} />
                    <div>
                      <div style={{ color: 'rgba(255,255,255,0.88)', fontSize: 13, fontWeight: 600 }}>{item.label}</div>
                      <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, marginTop: 2, lineHeight: 1.5 }}>{item.detail}</div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Footer line */}
              <div style={{
                marginTop: 56, paddingTop: 20,
                borderTop: '1px solid rgba(255,255,255,0.06)',
                color: 'rgba(255,255,255,0.2)', fontSize: 10,
                fontFamily: 'ui-monospace, monospace',
                opacity: heroIn ? 1 : 0,
                animation: heroIn ? 'hero-in 0.4s ease-out 0.55s both' : 'none',
              }}>
                qualgen.ai · Demo environment · No real data
              </div>
            </div>
          )}

          {/* ── COMPACT content (split phase) ── */}
          {isSplit && (
            <div style={{
              position: 'relative', zIndex: 10,
              flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center',
              padding: '32px 44px 44px',
              animation: 'hero-in 0.5s ease-out 0.15s both',
            }}>
              <h2 style={{
                color: '#fff', fontWeight: 700, fontSize: 24,
                lineHeight: 1.2, letterSpacing: '-0.015em', marginBottom: 28,
              }}>
                401(k)<br />administration<br />
                <span style={{ color: '#F97316' }}>built for trust.</span>
              </h2>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                {TRUST_ITEMS.map(item => (
                  <div key={item.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
                    <div style={{ width: 4, height: 4, borderRadius: 1, background: '#F97316', marginTop: 6, flexShrink: 0 }} />
                    <div>
                      <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: 12, fontWeight: 600 }}>{item.label}</div>
                      <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, marginTop: 1 }}>{item.detail}</div>
                    </div>
                  </div>
                ))}
              </div>
              <div style={{
                marginTop: 48, paddingTop: 20,
                borderTop: '1px solid rgba(255,255,255,0.06)',
                color: 'rgba(255,255,255,0.18)', fontSize: 10,
                fontFamily: 'ui-monospace, monospace',
              }}>
                qualgen.ai · Demo environment · No real data
              </div>
            </div>
          )}
        </div>

        {/* ══════════════════════════════════════════════════════════
            RIGHT FORM PANEL
        ══════════════════════════════════════════════════════════ */}
        <div style={{
          flex: isSplit ? 1 : 0,
          minWidth: 0,
          overflow: 'hidden',
          background: '#F6F7F9',
          display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center',
          padding: isSplit ? '48px 40px' : '0',
          opacity: isSplit ? 1 : 0,
          transition: [
            'flex 0.82s cubic-bezier(0.16,1,0.3,1)',
            'opacity 0.4s ease-out 0.38s',
            'padding 0.82s cubic-bezier(0.16,1,0.3,1)',
          ].join(', '),
        }}>
          <div style={{
            width: '100%', maxWidth: 400,
            transform: formIn ? 'translateX(0)' : 'translateX(28px)',
            opacity: formIn ? 1 : 0,
            transition: 'transform 0.55s cubic-bezier(0.16,1,0.3,1), opacity 0.4s ease-out',
          }}>
            <div style={{ marginBottom: 26 }}>
              <h2 style={{ fontSize: 21, fontWeight: 700, color: '#0C0E14', margin: 0 }}>Sign in</h2>
              <p style={{ fontSize: 13, color: '#9AA2B4', marginTop: 4 }}>
                {principalType ? 'Enter your details below.' : 'Choose your role to continue.'}
              </p>
            </div>

            {/* Role cards */}
            {!principalType && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {ROLES.map((role, i) => (
                  <button
                    key={role.value}
                    className="role-card"
                    onClick={() => selectRole(role.value)}
                    style={{
                      display: 'flex', alignItems: 'center', gap: 14,
                      padding: '17px 18px',
                      background: '#fff', border: '1.5px solid #E5E8EF',
                      borderRadius: 12, cursor: 'pointer',
                      textAlign: 'left', width: '100%',
                      animation: formIn ? `role-pop 0.38s cubic-bezier(0.16,1,0.3,1) ${0.04 + i * 0.07}s both` : 'none',
                    }}
                  >
                    <div style={{
                      width: 42, height: 42, borderRadius: 9,
                      background: '#FFF7ED', color: '#C2410C',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
                    }}>
                      <role.Icon />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ display: 'flex', alignItems: 'baseline', gap: 7 }}>
                        <span style={{ fontSize: 14, fontWeight: 700, color: '#0C0E14' }}>{role.label}</span>
                        <span style={{ fontSize: 10, color: '#B0B8C8', fontFamily: 'ui-monospace, monospace' }}>{role.sub}</span>
                      </div>
                      <div style={{ fontSize: 11, color: '#9AA2B4', marginTop: 2, lineHeight: 1.4 }}>{role.desc}</div>
                    </div>
                    <div style={{ color: '#D4D9E3', flexShrink: 0 }}><ArrowRight /></div>
                  </button>
                ))}
              </div>
            )}

            {/* Form after role selected */}
            {principalType && (
              <div style={{ animation: 'form-slide-in 0.32s cubic-bezier(0.16,1,0.3,1)' }}>
                <button
                  className="back-link"
                  onClick={() => { setPrincipalType(null); setFormError(null); }}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 5,
                    color: '#B0B8C8', fontSize: 12, cursor: 'pointer',
                    background: 'none', border: 'none', padding: 0, marginBottom: 18,
                    transition: 'color 0.15s ease',
                  }}
                >
                  <ChevronLeft /> {ROLES.find(r => r.value === principalType)?.label}
                </button>

                <div style={{
                  background: '#fff', borderRadius: 14,
                  border: '1px solid #E5E8EF',
                  padding: '24px 22px',
                  boxShadow: '0 1px 4px rgba(16,24,40,0.05)',
                }}>
                  <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                    {principalType === 'participant' ? (
                      <div>
                        <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#B0B8C8', letterSpacing: '0.07em', marginBottom: 7 }}>
                          YOUR ACCOUNT
                        </label>
                        <select className="input-field" value={participantId} onChange={e => handleParticipantChange(e.target.value)}>
                          {participants.length === 0 && <option>Loading…</option>}
                          {participants.map(p => (
                            <option key={p.participant_id} value={p.participant_id}>
                              {p.display_name || p.participant_id}{p.plan_id ? ` · ${p.plan_id}` : ''}
                            </option>
                          ))}
                        </select>
                        {planId && <p style={{ fontSize: 10, color: '#B0B8C8', marginTop: 5, fontFamily: 'ui-monospace, monospace' }}>Plan: {planId}</p>}
                      </div>
                    ) : (
                      <div>
                        <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#B0B8C8', letterSpacing: '0.07em', marginBottom: 7 }}>
                          PLAN TO MANAGE
                        </label>
                        <select className="input-field" value={planId} onChange={e => setPlanId(e.target.value)}>
                          {plans.length === 0 && <option>Loading…</option>}
                          {plans.map(p => (
                            <option key={p.plan_id} value={p.plan_id}>{p.plan_name || p.plan_id}</option>
                          ))}
                        </select>
                      </div>
                    )}

                    {formError && (
                      <div style={{
                        fontSize: 12, color: '#DC2626',
                        background: '#FEF2F2', border: '1px solid #FECACA',
                        borderRadius: 8, padding: '9px 12px',
                      }}>{formError}</div>
                    )}

                    <button
                      type="submit"
                      className="sign-in-btn"
                      disabled={isLoading}
                      style={{
                        background: '#F97316', color: '#fff', border: 'none',
                        borderRadius: 9, padding: '13px',
                        fontSize: 14, fontWeight: 700,
                        cursor: isLoading ? 'not-allowed' : 'pointer',
                        opacity: isLoading ? 0.65 : 1,
                        display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7,
                        boxShadow: '0 2px 10px rgba(249,115,22,0.2)',
                        marginTop: 4,
                      }}
                    >
                      {isLoading ? 'Signing in…' : <><span>Sign In</span><ArrowRight size={14} /></>}
                    </button>
                  </form>
                </div>

                <p style={{ fontSize: 10, color: '#C8D0DC', textAlign: 'center', marginTop: 14, fontFamily: 'ui-monospace, monospace' }}>
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
