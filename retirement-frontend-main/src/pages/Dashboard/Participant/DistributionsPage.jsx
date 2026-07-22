import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

// ── Icons ─────────────────────────────────────────────────────────────────────

function BriefcaseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2" />
      <line x1="12" y1="12" x2="12" y2="12.01" />
    </svg>
  );
}

function DoorIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M13 4H6a2 2 0 0 0-2 2v14h16V6a2 2 0 0 0-2-2h-1" />
      <path d="M13 4v16" />
      <circle cx="16" cy="12" r="1" fill="currentColor" stroke="none" />
    </svg>
  );
}

function ClockIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </svg>
  );
}

function ScaleIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round" className="w-5 h-5">
      <path d="M12 3v18M3 6l4.5 9M20.5 6 16 15" />
      <path d="M3 6h9M15 6h6" />
      <path d="M7.5 15H3a4.5 4.5 0 0 0 9 0H7.5Z" />
      <path d="M16.5 15H12a4.5 4.5 0 0 0 9 0h-4.5Z" />
    </svg>
  );
}

function ChevronDown() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M6 9l6 6 6-6" />
    </svg>
  );
}

function ChevronUp() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" className="w-4 h-4">
      <path d="M18 15l-6-6-6 6" />
    </svg>
  );
}

function SendIcon() {
  return (
    <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white">
      <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
    </svg>
  );
}

// ── Distribution type definitions ─────────────────────────────────────────────

const DIST_TYPES = [
  {
    key: 'in-service',
    icon: <BriefcaseIcon />,
    title: 'In-Service Distribution',
    badge: 'Age 59½+ only',
    badgeColor: 'bg-blue-50 text-blue-700 border-blue-200',
    description:
      'Withdraw from your account while still actively employed. Only available once you reach age 59½. No qualifying expense is required. Subject to ordinary income tax; the 10% early withdrawal penalty (IRC §72(t)) does not apply.',
    citation: 'IRC §401(k)(2)(B)(i)(I) · IRC §72(t)',
    autonomy: 'Queued for plan sponsor review',
    autonomyIcon: '📋',
    fields: [
      { label: 'Amount', hint: 'any dollar amount from your vested balance', required: true },
      { label: 'Confirm still employed', hint: 'let the assistant know you are currently active', required: true },
      { label: 'Tax acknowledgment', hint: 'you will be prompted to confirm this is a taxable event', required: true },
    ],
    examples: [
      "I want to take $10,000 out while I'm still working — I'm 62",
      "In-service withdrawal of $15,000, I'm 60 years old",
      "Can I withdraw $20,000? I'm still employed and I'm 61",
    ],
  },
  {
    key: 'separation',
    icon: <DoorIcon />,
    title: 'Separation Distribution',
    badge: 'After leaving employment',
    badgeColor: 'bg-amber-50 text-amber-700 border-amber-200',
    description:
      'Distribute your vested balance after separating from service — resignation, termination, or retirement. Subject to ordinary income tax and mandatory 20% federal withholding on eligible rollover amounts. Eligible for rollover to an IRA or new employer plan to defer taxes.',
    citation: 'IRC §402(a) · IRC §3405 · ERISA §205',
    autonomy: 'Queued for plan sponsor review',
    autonomyIcon: '📋',
    fields: [
      { label: 'Amount', hint: 'specific dollar amount, or "full vested balance"', required: true },
      { label: 'Separation date', hint: 'when you left or are leaving employment', required: false },
      { label: 'Tax acknowledgment', hint: 'you will be prompted to confirm this is a taxable event', required: true },
      { label: 'Rollover preference', hint: 'lump sum to you, or rollover to IRA / new plan', required: false },
    ],
    examples: [
      "I left my job last month, I want to withdraw $30,000",
      "Separation distribution of $50,000 — I resigned last week",
      "I'm no longer employed, please distribute my full vested balance",
      "I retired last month and want to roll my balance over to an IRA",
    ],
  },
  {
    key: 'rmd',
    icon: <ClockIcon />,
    title: 'Required Minimum Distribution (RMD)',
    badge: 'Age 73+, mandatory',
    badgeColor: 'bg-purple-50 text-purple-700 border-purple-200',
    description:
      'Federal law requires you to begin withdrawing a minimum amount from your account each year starting at age 73 (SECURE 2.0). The plan calculates your RMD based on your account balance and IRS life-expectancy tables. Subject to ordinary income tax; failure to take the RMD results in a 25% excise tax on the shortfall.',
    citation: 'IRC §401(a)(9) · SECURE 2.0 Act §107',
    autonomy: 'Queued for plan sponsor review',
    autonomyIcon: '📋',
    fields: [
      { label: 'RMD amount', hint: 'or say "calculate my RMD" — the plan will determine the figure', required: false },
      { label: 'Tax acknowledgment', hint: 'you will be prompted to confirm this is a taxable event', required: true },
    ],
    examples: [
      "I need my required minimum distribution for this year",
      "Calculate and process my RMD — I'm 75",
      "What is my RMD amount for this year?",
      "Process my annual required minimum distribution",
    ],
  },
  {
    key: 'qdro',
    icon: <ScaleIcon />,
    title: 'QDRO Transfer',
    badge: 'Court order required',
    badgeColor: 'bg-rose-50 text-rose-700 border-rose-200',
    description:
      'A Qualified Domestic Relations Order (QDRO) divides your retirement account between you and an alternate payee (typically a former spouse) as directed by a divorce or separation court order. Taxes fall on the alternate payee, not you. Requires uploading the court order document. Plan sponsor must issue a determination within 18 months.',
    citation: 'ERISA §206(d)(3) · IRC §414(p)',
    autonomy: 'Queued for plan sponsor review + document verification',
    autonomyIcon: '🔍',
    fields: [
      { label: 'Alternate payee name', hint: 'full legal name of the person receiving funds', required: true },
      { label: 'Transfer percentage', hint: '1–100% of your vested balance per the court order', required: true },
      { label: 'Court order document', hint: 'you will be prompted to upload the QDRO document after submitting', required: true },
    ],
    examples: [
      "Process a QDRO for Jane Smith, 50% of my vested balance",
      "I have a court order — transfer 40% to my ex-spouse Robert Jones",
      "QDRO transfer of 35% to alternate payee Sarah Miller",
    ],
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function DistributionsPage() {
  const navigate = useNavigate();
  const [expanded, setExpanded] = useState(null);
  const [queries, setQueries] = useState({});

  function toggle(key) {
    setExpanded(prev => (prev === key ? null : key));
  }

  function setQuery(key, val) {
    setQueries(prev => ({ ...prev, [key]: val }));
  }

  function launchChat(text) {
    navigate('/participant/chat', { state: { chatDraft: text } });
  }

  return (
    <div className="max-w-2xl mx-auto space-y-4">
      {/* Page intro */}
      <div className="card p-5">
        <p className="text-sm text-text-muted leading-relaxed">
          Select the distribution type that fits your situation. Each type has different eligibility
          rules, tax treatment, and review requirements. All distributions are subject to ordinary
          income tax — the chat will ask you to confirm before submitting.
        </p>
      </div>

      {/* Distribution type cards */}
      {DIST_TYPES.map((dt) => {
        const isOpen = expanded === dt.key;
        const q = queries[dt.key] || '';

        return (
          <div key={dt.key} className={[
            'card overflow-hidden transition-shadow duration-200',
            isOpen ? 'shadow-card-hover border-accent/30' : '',
          ].join(' ')}>

            {/* ── Card header (always visible) ── */}
            <button
              type="button"
              onClick={() => toggle(dt.key)}
              className="w-full flex items-center gap-4 p-5 text-left hover:bg-bg-s2 transition-colors duration-150 focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/30"
            >
              <div className={[
                'w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0 transition-all duration-200',
                isOpen ? 'bg-accent text-white shadow-md' : 'bg-accent-light text-accent-dark',
              ].join(' ')}>
                {dt.icon}
              </div>

              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-[15px] font-semibold text-text">{dt.title}</span>
                  <span className={['text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full border', dt.badgeColor].join(' ')}>
                    {dt.badge}
                  </span>
                </div>
                <p className="text-xs text-text-faint mt-0.5 line-clamp-1">{dt.citation}</p>
              </div>

              <span className="text-text-faint flex-shrink-0">
                {isOpen ? <ChevronUp /> : <ChevronDown />}
              </span>
            </button>

            {/* ── Expanded detail ── */}
            {isOpen && (
              <div className="border-t border-border px-5 pb-5 space-y-5 pt-4">

                {/* Description + review note */}
                <div>
                  <p className="text-sm text-text-muted leading-relaxed">{dt.description}</p>
                  <div className="mt-3 inline-flex items-center gap-1.5 text-xs text-text-faint bg-bg-s2 border border-border px-3 py-1 rounded-full">
                    <span>{dt.autonomyIcon}</span>
                    <span>{dt.autonomy}</span>
                  </div>
                </div>

                {/* What to mention */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-3">
                    What to mention
                  </h4>
                  <ul className="space-y-2">
                    {dt.fields.map((f) => (
                      <li key={f.label} className="flex items-start gap-3">
                        <div className={[
                          'w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5',
                          f.required ? 'bg-accent-light' : 'bg-bg-s3',
                        ].join(' ')}>
                          <span className={['text-[9px] font-bold', f.required ? 'text-accent-dark' : 'text-text-faint'].join(' ')}>
                            {f.required ? '!' : '?'}
                          </span>
                        </div>
                        <div>
                          <span className="text-sm font-medium text-text">{f.label}</span>
                          {f.hint && (
                            <span className="text-xs text-text-muted ml-1.5">— {f.hint}</span>
                          )}
                          {!f.required && (
                            <span className="ml-1.5 text-[10px] font-mono text-text-faint bg-bg-s3 px-1.5 py-0.5 rounded">
                              optional
                            </span>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Example queries */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-3">
                    Example queries — click to use
                  </h4>
                  <div className="space-y-2">
                    {dt.examples.map((ex) => (
                      <button
                        key={ex}
                        type="button"
                        onClick={() => setQuery(dt.key, ex)}
                        className={[
                          'w-full text-left text-sm px-4 py-3 rounded-lg border transition-colors duration-150',
                          q === ex
                            ? 'border-accent bg-accent-light text-accent-dark font-medium'
                            : 'border-border text-text-muted hover:border-accent/40 hover:bg-bg-s2 hover:text-text',
                        ].join(' ')}
                      >
                        <span className="font-mono text-accent opacity-60 mr-2">"</span>
                        {ex}
                        <span className="font-mono text-accent opacity-60 ml-0.5">"</span>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Custom query + launch */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-2">
                    Or write your own
                  </h4>
                  <textarea
                    rows={2}
                    value={q}
                    onChange={(e) => setQuery(dt.key, e.target.value)}
                    placeholder={`e.g. "${dt.examples[0]}"`}
                    className="w-full border border-border-strong rounded-xl px-4 py-3 text-sm text-text bg-bg
                      outline-none resize-none focus:border-accent focus:ring-2 focus:ring-accent/10
                      placeholder:text-text-faint leading-relaxed transition-all duration-150"
                  />
                  <button
                    type="button"
                    onClick={() => { if (q.trim()) launchChat(q.trim()); }}
                    disabled={!q.trim()}
                    className="mt-2 w-full btn-primary flex items-center justify-center gap-2"
                  >
                    <SendIcon />
                    Send to chat
                  </button>
                </div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
