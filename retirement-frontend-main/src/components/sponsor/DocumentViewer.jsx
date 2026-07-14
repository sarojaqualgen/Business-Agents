import React, { useState } from 'react';
import EmptyState from '../ui/EmptyState.jsx';
import Badge from '../ui/Badge.jsx';

function formatDate(value) {
  if (!value) return '\u2014';
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

const VERIFICATION_TONE = {
  verified: 'approved',
  needs_review: 'pending',
};

/**
 * "Submitted Documents" section for the plan sponsor — lets a sponsor see
 * every document a participant uploaded in support of a pending request.
 * Mock data only (see mocks/data.js) with no backend wiring, per the
 * latest UI feedback: this is a viewer, not a workflow.
 */
export default function DocumentViewer({ documents }) {
  const [active, setActive] = useState(null);

  if (documents.length === 0) {
    return (
      <EmptyState
        title="No submitted documents"
        description="Documents participants attach to hardship or QDRO requests will appear here."
      />
    );
  }

  return (
    <div>
      <ul className="divide-y divide-border">
        {documents.map((doc) => (
          <li key={doc.doc_id} className="flex items-center justify-between gap-4 py-3.5">
            <div className="flex items-center gap-3 min-w-0">
              <div className="w-9 h-9 rounded-lg bg-bg-s2 text-text-muted flex items-center justify-center flex-shrink-0">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-4.5 h-4.5">
                  <path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
                  <path d="M14 3.5V8h4" />
                </svg>
              </div>
              <div className="min-w-0">
                <div className="text-sm font-medium text-text truncate">{doc.file_name}</div>
                <div className="text-xs text-text-faint truncate">
                  {doc.doc_type} · {doc.participant_id} · {formatDate(doc.uploaded_at)}
                </div>
              </div>
            </div>
            <div className="flex items-center gap-3 flex-shrink-0">
              <Badge tone={VERIFICATION_TONE[doc.verification] || 'default'}>
                {doc.verification === 'verified' ? 'Verified' : 'Needs Review'}
              </Badge>
              <button
                type="button"
                onClick={() => setActive(doc)}
                className="px-3 py-1.5 rounded-md text-xs font-medium bg-bg-s2 border border-border-strong
                  text-text hover:bg-accent-light hover:text-accent-dark hover:border-accent/40 transition-colors"
              >
                View
              </button>
            </div>
          </li>
        ))}
      </ul>

      {active && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 px-4 modal-backdrop"
          onClick={() => setActive(null)}
        >
          <div
            className="modal-panel bg-bg-surface border border-border-strong rounded-lg p-5 w-full max-w-md shadow-card-hover"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="text-sm font-semibold text-text">{active.file_name}</h3>
                <p className="text-xs text-text-faint mt-0.5">{active.doc_type}</p>
              </div>
              <Badge tone={VERIFICATION_TONE[active.verification] || 'default'}>
                {active.verification === 'verified' ? 'Verified' : 'Needs Review'}
              </Badge>
            </div>

            <div className="bg-bg-s2 border border-border rounded-md p-4 text-sm text-text-muted leading-relaxed mb-4">
              {active.verification_note}
            </div>

            <dl className="text-xs text-text-muted space-y-1.5 mb-5">
              <div className="flex justify-between">
                <dt>Participant</dt>
                <dd className="text-text font-mono">{active.participant_id}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Uploaded</dt>
                <dd className="text-text">{formatDate(active.uploaded_at)}</dd>
              </div>
              <div className="flex justify-between">
                <dt>Queue Entry</dt>
                <dd className="text-text font-mono">{active.entry_id}</dd>
              </div>
            </dl>

            <button type="button" onClick={() => setActive(null)} className="btn-secondary w-full">
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
