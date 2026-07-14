import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';

/**
 * Landing page for each action type (Loan, Hardship, etc.).
 * Shows what the participant needs to tell the assistant, lets them pick
 * an example query or write their own, then navigates to chat with it
 * pre-filled — no auto-submit.
 */
export default function ActionGuidePage({ icon, title, description, fields, examples, citation }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState('');

  function launchChat(text) {
    navigate('/participant/chat', { state: { chatDraft: text } });
  }

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header card */}
      <div className="card p-7">
        <div className="flex items-start gap-4">
          <div className="w-12 h-12 rounded-xl bg-accent-light text-accent-dark flex items-center justify-center flex-shrink-0">
            {icon}
          </div>
          <div className="min-w-0">
            <h2 className="text-[17px] font-bold text-text">{title}</h2>
            <p className="text-sm text-text-muted mt-1 leading-relaxed">{description}</p>
            {citation && (
              <span className="inline-block mt-2 text-[10px] font-mono text-text-faint bg-bg-s2 border border-border px-2 py-0.5 rounded">
                {citation}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* What to include */}
      {fields && fields.length > 0 && (
        <div className="card p-6">
          <h3 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-4">
            What to mention
          </h3>
          <ul className="space-y-2.5">
            {fields.map((f) => (
              <li key={f.label} className="flex items-start gap-3">
                <div className="w-5 h-5 rounded-full bg-accent-light flex items-center justify-center flex-shrink-0 mt-0.5">
                  <span className="text-[9px] font-bold text-accent-dark">{f.required ? '!' : '?'}</span>
                </div>
                <div>
                  <span className="text-sm font-medium text-text">{f.label}</span>
                  {f.hint && <span className="text-xs text-text-muted ml-1.5">— {f.hint}</span>}
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
      )}

      {/* Example queries */}
      {examples && examples.length > 0 && (
        <div className="card p-6">
          <h3 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-4">
            Example queries — click to use
          </h3>
          <div className="space-y-2">
            {examples.map((ex) => (
              <button
                key={ex}
                type="button"
                onClick={() => setQuery(ex)}
                className={[
                  'w-full text-left text-sm px-4 py-3 rounded-lg border transition-colors duration-150',
                  query === ex
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
      )}

      {/* Custom query + launch */}
      <div className="card p-6">
        <h3 className="text-xs font-mono uppercase tracking-widest text-text-faint mb-3">
          Or write your own
        </h3>
        <textarea
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={`Describe what you need — e.g. "${examples?.[0] || title}"`}
          className="w-full border border-border-strong rounded-xl px-4 py-3 text-sm text-text bg-bg
            outline-none resize-none focus:border-accent focus:ring-2 focus:ring-accent/10
            placeholder:text-text-faint leading-relaxed transition-all duration-150"
        />
        <button
          type="button"
          onClick={() => { if (query.trim()) launchChat(query.trim()); }}
          disabled={!query.trim()}
          className="mt-3 w-full btn-primary flex items-center justify-center gap-2"
        >
          <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
          </svg>
          Send to chat
        </button>
      </div>
    </div>
  );
}
