import React, { useState } from 'react';
import { titleCase } from '../../lib/format.js';

/**
 * Shared approve/deny modal for a single queue entry. `mode` is either
 * "approve" or "deny" and only changes the copy/accent colour — the note
 * field and submit flow are identical, matching SWAGGER_GUIDE.md's Step
 * 6d/6e ({ "note": "..." } body).
 */
export default function DecisionDialog({ entry, mode, onSubmit, onCancel, isSubmitting }) {
  const [note, setNote] = useState('');
  const isApprove = mode === 'approve';

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4 modal-backdrop">
      <div className="modal-panel bg-bg-surface border border-border-strong rounded-lg p-5 w-full max-w-md shadow-card-hover">
        <h3 className="text-sm font-semibold text-text mb-1">
          {isApprove ? 'Approve Request' : 'Deny Request'}
        </h3>
        <p className="text-xs text-text-muted mb-4">
          {entry.entry_id} · {titleCase(entry.action)} · {entry.participant_id}
        </p>

        <label className="block mb-4">
          <span className="label-mono">Note</span>
          <textarea
            className="input-field min-h-[80px] resize-none"
            placeholder={isApprove ? 'e.g. Documentation reviewed and verified' : 'e.g. Insufficient documentation provided'}
            value={note}
            onChange={(e) => setNote(e.target.value)}
          />
        </label>

        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => onSubmit(note)}
            disabled={isSubmitting}
            className={`px-4 py-2 rounded-md text-[13px] font-medium text-white transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${
              isApprove ? 'bg-success hover:bg-success/80' : 'bg-danger hover:bg-danger/80'
            }`}
          >
            {isSubmitting ? 'Submitting…' : isApprove ? 'Approve' : 'Deny'}
          </button>
          <button type="button" onClick={onCancel} disabled={isSubmitting} className="btn-secondary">
            Cancel
          </button>
        </div>
      </div>
    </div>
  );
}
