import React, { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext.jsx';
import { apiClient } from '../../lib/apiClient.js';
import QualGenLogo from '../../assets/QualGenLogo.jsx';

const TRUST_ITEMS = [
  { label: '12-Rule ERISA Compliance Engine', detail: 'Every action gates through FAP before execution' },
  { label: 'SECURE 2.0 & IRC §72(p) Ready',  detail: 'Roth catch-up, RMD reform, loan cap enforcement built-in' },
  { label: 'ERISA §107 Audit Retention',      detail: '6-year FAP audit trail — DOL-ready on demand' },
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
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <path d="M9 9h.01M15 9h.01M9 15h.01M15 15h.01M9 3v18M3 9h18" />
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

function ShieldCheckIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" style={{ width: 28, height: 28 }}>
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <polyline points="9 12 11 14 15 10" />
    </svg>
  );
}

const ROLES = [
  { value: 'participant',  label: 'Employee',      sub: 'Participant',  desc: 'View your account, request loans, change contributions', Icon: PersonIcon },
  { value: 'plan_sponsor', label: 'Administrator', sub: 'Plan Administrator', desc: 'Manage the plan, approve requests, view the audit log',  Icon: BuildingIcon },
];

const PANEL_BG       = '#0C0E14';
const STRIPE_TEXTURE = `repeating-linear-gradient(-52deg, transparent, transparent 18px, rgba(255,255,255,0.018) 18px, rgba(255,255,255,0.018) 19px)`;

function isMobile() {
  return typeof window !== 'undefined' && window.innerWidth < 1024;
}

export default function LoginPage() {
  const { login, isAuthenticated, isLoading, principal } = useAuth();
  const navigate  = useNavigate();
  const location  = useLocation();

  // 'hero' → 'form'. On mobile we skip directly to 'form'.
  const [phase, setPhase]                 = useState(() => (isMobile() ? 'form' : 'hero'));
  const [principalType, setPrincipalType] = useState(null);
  const [participantId, setParticipantId] = useState('');
  const [planId, setPlanId]               = useState('');
  const [password, setPassword]           = useState('');
  const [showPassword, setShowPassword]   = useState(false);
  const [participants, setParticipants]   = useState([]);
  const [plans, setPlans]                 = useState([]);
  const [formError, setFormError]         = useState(null);
  const [heroIn, setHeroIn]               = useState(false);
  const [formContentIn, setFormContentIn] = useState(false);
  const [loginSuccess, setLoginSuccess]   = useState(false);
  const [overlayIn, setOverlayIn]         = useState(false);

  useEffect(() => { setTimeout(() => setHeroIn(true), 60); }, []);

  useEffect(() => {
    if (!isAuthenticated) return;
    setLoginSuccess(true);
    const t1 = setTimeout(() => setOverlayIn(true), 420);
    const dest = location.state?.from?.pathname || (principal?.principalType === 'plan_sponsor' ? '/sponsor' : '/participant');
    const t2 = setTimeout(() => navigate(dest, { replace: true }), 900);
    return () => { clearTimeout(t1); clearTimeout(t2); };
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
    setPassword('');
  }

  function openPortal() {
    setPhase('form');
    setTimeout(() => setFormContentIn(true), 320);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setFormError(null);
    try {
      await login({ principalType, participantId: principalType === 'participant' ? participantId : null, planId, password });
    } catch (err) {
      setFormError(err.message || 'Login failed. Please try again.');
    }
  }

  const isHero = phase === 'hero';

  const rightBg     = isHero ? 'rgba(255,255,255,0.03)' : '#F6F7F9';
  const rightBorder = isHero ? '1px solid rgba(255,255,255,0.06)' : '1px solid #E5E8EF';

  return (
    <>
      <style>{`
        @keyframes hero-in {
          from { opacity: 0; transform: translateY(22px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes form-in {
          from { opacity: 0; transform: translateY(14px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes role-pop {
          from { opacity: 0; transform: translateY(8px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0) scale(1); }
        }
        @keyframes check-pop {
          0%   { transform: scale(0.5); opacity: 0; }
          70%  { transform: scale(1.12); opacity: 1; }
          100% { transform: scale(1); opacity: 1; }
        }

        .portal-cta {
          transition: background 0.2s ease, transform 0.15s ease, box-shadow 0.2s ease;
        }
        .portal-cta:hover {
          background: #EA6C0C !important;
          transform: translateY(-2px);
          box-shadow: 0 8px 24px rgba(249,115,22,0.35) !important;
        }
        .portal-cta:active { transform: translateY(0); }

        .role-card { transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.15s ease; }
        .role-card:hover {
          border-color: #F97316 !important;
          box-shadow: 0 0 0 1px rgba(249,115,22,0.22), 0 4px 14px rgba(249,115,22,0.09);
          transform: translateY(-1px);
        }

        .back-link { transition: color 0.15s ease; }
        .back-link:hover { color: #F97316 !important; }

        .sign-in-btn { transition: background 0.18s ease, transform 0.15s ease, box-shadow 0.15s ease; }
        .sign-in-btn:hover:not(:disabled) {
          background: #EA6C0C !important;
          transform: translateY(-1px);
          box-shadow: 0 4px 14px rgba(249,115,22,0.28);
        }
        .sign-in-btn:active:not(:disabled) { transform: translateY(0); }
      `}</style>

      {/* ── Root shell ─────────────────────────────────────────────────────── */}
      <div style={{
        minHeight: '100vh', display: 'flex', overflow: 'hidden',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        background: PANEL_BG, backgroundImage: STRIPE_TEXTURE,
      }}>

        {/* ══ LEFT — brand panel ══════════════════════════════════════════════ */}
        <div style={{
          width: '56%', flexShrink: 0, position: 'relative', overflow: 'hidden',
          display: 'flex', flexDirection: 'column', padding: '44px 64px',
        }}>
          {/* Left-edge accent bar */}
          <div style={{
            position: 'absolute', left: 0, top: '50%', transform: 'translateY(-50%)',
            width: 3, height: heroIn ? 72 : 0,
            background: 'linear-gradient(180deg, transparent, #F97316, transparent)',
            transition: 'height 0.7s ease-out 0.4s', borderRadius: 2,
          }} />

          {/* Logo */}
          <div style={{
            display: 'flex', flexDirection: 'column', gap: 5, marginBottom: 0,
            opacity: heroIn ? 1 : 0,
            transform: heroIn ? 'translateY(0)' : 'translateY(-10px)',
            transition: 'opacity 0.5s ease-out, transform 0.5s ease-out',
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <QualGenLogo height={30} iconOnly={true} />
              <span style={{ fontFamily: 'Inter, system-ui, -apple-system, sans-serif', fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', lineHeight: 1, color: '#fff' }}>
                QRetire
              </span>
            </div>
            <div style={{ color: 'rgba(255,255,255,0.35)', fontSize: 11, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.06em', paddingLeft: 3 }}>
              Powered by Qualgen.ai
            </div>
          </div>

          {/* Hero headline + trust items */}
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', paddingTop: 16 }}>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 8, border: '1px solid rgba(255,255,255,0.1)', borderRadius: 6, padding: '5px 12px', marginBottom: 24, width: 'fit-content', opacity: heroIn ? 1 : 0, animation: heroIn ? 'hero-in 0.5s ease-out 0.08s both' : 'none' }}>
              <div style={{ width: 5, height: 5, borderRadius: '50%', background: '#F97316', flexShrink: 0 }} />
              <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: 10, fontFamily: 'ui-monospace, monospace', letterSpacing: '0.07em' }}>
                ERISA-COMPLIANT · SECURE 2.0 READY
              </span>
            </div>

            <h1 style={{ color: '#fff', fontWeight: 800, lineHeight: 1.07, fontSize: 'clamp(34px, 4vw, 56px)', letterSpacing: '-0.025em', marginBottom: 18, opacity: heroIn ? 1 : 0, animation: heroIn ? 'hero-in 0.55s ease-out 0.14s both' : 'none' }}>
              401(k) administration<br />
              <span style={{ color: '#F97316' }}>built for trust.</span>
            </h1>

            <p style={{ color: 'rgba(255,255,255,0.4)', fontSize: 15, lineHeight: 1.75, maxWidth: 380, marginBottom: 44, opacity: heroIn ? 1 : 0, animation: heroIn ? 'hero-in 0.5s ease-out 0.2s both' : 'none' }}>
              Every participant action gates through a 12-rule fiduciary
              compliance engine before execution. No exceptions.
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: 18 }}>
              {TRUST_ITEMS.map((item, i) => (
                <div key={item.label} style={{ display: 'flex', alignItems: 'flex-start', gap: 12, opacity: heroIn ? 1 : 0, animation: heroIn ? `hero-in 0.45s ease-out ${0.28 + i * 0.07}s both` : 'none' }}>
                  <div style={{ width: 4, height: 4, borderRadius: 1, background: '#F97316', marginTop: 7, flexShrink: 0 }} />
                  <div>
                    <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: 13, fontWeight: 600 }}>{item.label}</div>
                    <div style={{ color: 'rgba(255,255,255,0.33)', fontSize: 11, marginTop: 2, lineHeight: 1.5 }}>{item.detail}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div style={{ color: 'rgba(255,255,255,0.18)', fontSize: 10, fontFamily: 'ui-monospace, monospace', opacity: heroIn ? 1 : 0, animation: heroIn ? 'hero-in 0.4s ease-out 0.52s both' : 'none' }}>
            QRetire · Powered by Qualgen.ai · Demo environment · No real data
          </div>
        </div>

        {/* ══ RIGHT — CTA in hero phase, form in form phase ═══════════════════ */}
        <div style={{
          flex: 1, minWidth: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
          padding: '44px 40px', borderLeft: rightBorder, background: rightBg,
          transition: 'background 0.55s ease, border-color 0.55s ease', position: 'relative',
        }}>

          {/* ── HERO phase ── */}
          {isHero && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', maxWidth: 300, gap: 0, opacity: heroIn ? 1 : 0, animation: heroIn ? 'hero-in 0.55s ease-out 0.35s both' : 'none' }}>
              <div style={{ width: 64, height: 64, borderRadius: 18, background: 'rgba(249,115,22,0.1)', border: '1px solid rgba(249,115,22,0.2)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#F97316', marginBottom: 22 }}>
                <ShieldCheckIcon />
              </div>
              <div style={{ color: 'rgba(255,255,255,0.7)', fontSize: 16, fontWeight: 700, marginBottom: 8 }}>Ready to sign in?</div>
              <div style={{ color: 'rgba(255,255,255,0.32)', fontSize: 12, lineHeight: 1.6, marginBottom: 32 }}>
                Access your participant portal or the plan administrator console.
              </div>
              <button className="portal-cta" onClick={openPortal} style={{ display: 'inline-flex', alignItems: 'center', gap: 9, background: '#F97316', color: '#fff', border: 'none', borderRadius: 11, padding: '14px 28px', fontSize: 14, fontWeight: 700, cursor: 'pointer', boxShadow: '0 4px 18px rgba(249,115,22,0.28)', width: '100%', justifyContent: 'center' }}>
                Access Portal <ArrowRight size={15} />
              </button>
              <div style={{ display: 'flex', gap: 24, marginTop: 36, paddingTop: 24, borderTop: '1px solid rgba(255,255,255,0.07)', width: '100%', justifyContent: 'center' }}>
                {[['12', 'ERISA rules'], ['6yr', 'Audit log'], ['§404(c)', 'Protected']].map(([val, lbl]) => (
                  <div key={lbl} style={{ textAlign: 'center' }}>
                    <div style={{ color: '#F97316', fontSize: 14, fontWeight: 700, fontFamily: 'ui-monospace, monospace' }}>{val}</div>
                    <div style={{ color: 'rgba(255,255,255,0.28)', fontSize: 10, marginTop: 2 }}>{lbl}</div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── FORM phase ── */}
          {!isHero && (
            <div style={{ width: '100%', maxWidth: 380, opacity: formContentIn ? 1 : 0, transform: formContentIn ? 'translateY(0)' : 'translateY(16px)', transition: 'opacity 0.4s ease-out, transform 0.4s ease-out' }}>

              {/* Welcome success state */}
              {loginSuccess && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 0, animation: 'form-in 0.3s ease-out' }}>
                  <div style={{ width: 64, height: 64, borderRadius: '50%', background: 'rgba(21,128,61,0.12)', border: '2px solid rgba(21,128,61,0.3)', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: 20, animation: 'check-pop 0.45s cubic-bezier(0.16,1,0.3,1)' }}>
                    <svg viewBox="0 0 24 24" fill="none" stroke="#15803D" strokeWidth={2.5} strokeLinecap="round" strokeLinejoin="round" style={{ width: 28, height: 28 }}>
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  </div>
                  <div style={{ fontSize: 18, fontWeight: 700, color: '#0C0E14', marginBottom: 6 }}>Welcome back</div>
                  <div style={{ fontSize: 13, color: '#9AA2B4' }}>Signing you in…</div>
                </div>
              )}

              {!loginSuccess && (
                <div style={{ marginBottom: 26 }}>
                  <h2 style={{ fontSize: 21, fontWeight: 700, color: '#0C0E14', margin: 0 }}>Sign in</h2>
                  <p style={{ fontSize: 13, color: '#9AA2B4', marginTop: 4 }}>
                    {principalType ? 'Enter your password to continue.' : 'Choose your role to continue.'}
                  </p>
                </div>
              )}

              {/* Role cards */}
              {!loginSuccess && !principalType && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                  {ROLES.map((role, i) => (
                    <button key={role.value} className="role-card" onClick={() => selectRole(role.value)} style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '17px 18px', background: '#fff', border: '1.5px solid #E5E8EF', borderRadius: 12, cursor: 'pointer', textAlign: 'left', width: '100%', animation: formContentIn ? `role-pop 0.36s cubic-bezier(0.16,1,0.3,1) ${0.04 + i * 0.07}s both` : 'none' }}>
                      <div style={{ width: 42, height: 42, borderRadius: 9, background: '#FFF7ED', color: '#C2410C', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
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
              {!loginSuccess && principalType && (
                <div style={{ animation: 'form-in 0.3s ease-out' }}>
                  <button className="back-link" onClick={() => { setPrincipalType(null); setFormError(null); setPassword(''); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 5, color: '#B0B8C8', fontSize: 12, cursor: 'pointer', background: 'none', border: 'none', padding: 0, marginBottom: 18 }}>
                    <ChevronLeft /> {ROLES.find(r => r.value === principalType)?.label}
                  </button>

                  <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #E5E8EF', padding: '24px 22px', boxShadow: '0 1px 4px rgba(16,24,40,0.05)' }}>
                    <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

                      {/* Account selector */}
                      {principalType === 'participant' ? (
                        <div>
                          <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#B0B8C8', letterSpacing: '0.07em', marginBottom: 7 }}>YOUR ACCOUNT</label>
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
                          <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#B0B8C8', letterSpacing: '0.07em', marginBottom: 7 }}>PLAN TO MANAGE</label>
                          <select className="input-field" value={planId} onChange={e => setPlanId(e.target.value)}>
                            {plans.length === 0 && <option>Loading…</option>}
                            {plans.map(p => (
                              <option key={p.plan_id} value={p.plan_id}>{p.plan_name || p.plan_id}</option>
                            ))}
                          </select>
                        </div>
                      )}

                      {/* Password */}
                      <div>
                        <label style={{ display: 'block', fontSize: 10, fontFamily: 'ui-monospace, monospace', color: '#B0B8C8', letterSpacing: '0.07em', marginBottom: 7 }}>PASSWORD</label>
                        <div style={{ position: 'relative' }}>
                          <input
                            className="input-field"
                            type={showPassword ? 'text' : 'password'}
                            autoComplete="current-password"
                            placeholder="••••••••••"
                            value={password}
                            onChange={e => setPassword(e.target.value)}
                            required
                            style={{ width: '100%', boxSizing: 'border-box', paddingRight: 40 }}
                          />
                          <button type="button" onClick={() => setShowPassword(v => !v)} style={{ position: 'absolute', right: 10, top: '50%', transform: 'translateY(-50%)', background: 'none', border: 'none', cursor: 'pointer', color: '#B0B8C8', padding: 2, lineHeight: 1 }} title={showPassword ? 'Hide' : 'Show'}>
                            {showPassword ? (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ width: 15, height: 15 }}>
                                <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/>
                              </svg>
                            ) : (
                              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" style={{ width: 15, height: 15 }}>
                                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>
                              </svg>
                            )}
                          </button>
                        </div>
                      </div>

                      {formError && (
                        <div style={{ fontSize: 12, color: '#DC2626', background: '#FEF2F2', border: '1px solid #FECACA', borderRadius: 8, padding: '9px 12px' }}>{formError}</div>
                      )}

                      <button type="submit" className="sign-in-btn" disabled={isLoading || !password} style={{ background: '#F97316', color: '#fff', border: 'none', borderRadius: 9, padding: '13px', fontSize: 14, fontWeight: 700, cursor: (isLoading || !password) ? 'not-allowed' : 'pointer', opacity: (isLoading || !password) ? 0.65 : 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 7, boxShadow: '0 2px 10px rgba(249,115,22,0.2)', marginTop: 4 }}>
                        {isLoading ? 'Signing in…' : <><span>Sign In</span><ArrowRight size={14} /></>}
                      </button>
                    </form>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* ── Exit overlay ─────────────────────────────────────────────────────── */}
      <div style={{ position: 'fixed', inset: 0, zIndex: 200, background: '#0C0E14', opacity: overlayIn ? 1 : 0, pointerEvents: overlayIn ? 'all' : 'none', transition: 'opacity 0.45s ease-in' }} />
    </>
  );
}
