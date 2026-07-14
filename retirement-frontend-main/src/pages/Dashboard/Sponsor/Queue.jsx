import React, { useCallback, useEffect, useMemo, useState } from 'react';
// useCallback is also used inside DocsModal via the module-level import above
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { QUEUE_UPDATED_EVENT } from '../../../lib/events.js';
import FilterSelect from '../../../components/ui/FilterSelect.jsx';
import QueueTable from '../../../components/sponsor/QueueTable.jsx';
import DecisionDialog from '../../../components/sponsor/DecisionDialog.jsx';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import { titleCase } from '../../../lib/format.js';

const STATUS_OPTIONS = [
  { value: 'all',                           label: 'All Statuses' },
  { value: 'pending',                       label: 'Pending' },
  { value: 'approved_awaiting_bank_details', label: 'Awaiting Bank Details' },
  { value: 'approved',                      label: 'Approved' },
  { value: 'denied',                        label: 'Denied' },
];

const AUTO_REFRESH_MS = 15000;

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function DocsModal({ entry, onClose, onDocApproved }) {
  const [docs, setDocs] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isApproving, setIsApproving] = useState(false);
  const [approveNote, setApproveNote] = useState('');
  const [error, setError] = useState(null);
  const [approved, setApproved] = useState(false);

  const fetchDocs = useCallback(async () => {
    try {
      const res = await apiClient.getQueueEntryDocs(entry.entry_id);
      setDocs(res.documents || []);
    } catch (err) {
      setError(err.message || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  }, [entry.entry_id]);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  async function handleApproveDocs() {
    setIsApproving(true);
    setError(null);
    try {
      await apiClient.approveQueueEntryDocs(entry.entry_id, approveNote);
      setApproved(true);
      onDocApproved();
      // Refetch so doc cards update their "Sponsor Approved" badge
      await fetchDocs();
    } catch (err) {
      setError(err.message || 'Failed to approve documents');
    } finally {
      setIsApproving(false);
    }
  }

  const allSponsorApproved = docs.length > 0 && docs.every((d) => d.sponsor_doc_approved);
  const showApproveFooter = !isLoading && docs.length > 0 && !allSponsorApproved && !approved;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="bg-bg-surface border border-border-strong rounded-lg w-full max-w-xl shadow-card-hover flex flex-col max-h-[85vh]">

        {/* Header */}
        <div className="px-5 py-4 border-b border-border flex items-start justify-between">
          <div>
            <h3 className="text-sm font-semibold text-text">Supporting Documents</h3>
            <p className="text-xs text-text-muted mt-0.5">
              {titleCase(entry.action)} · {entry.participant_id}
            </p>
            <p className="text-[11px] text-text-faint mt-0.5 font-mono">
              Submitted {formatDate(entry.submitted_at)} · Entry {entry.entry_id}
            </p>
          </div>
          <button type="button" onClick={onClose}
            className="text-text-faint hover:text-text text-xl leading-none ml-4" aria-label="Close">
            ×
          </button>
        </div>

        {/* Body */}
        <div className="overflow-y-auto flex-1 px-5 py-4 space-y-4">
          {isLoading && (
            <p className="text-sm text-text-muted text-center py-8">Loading documents…</p>
          )}
          {!isLoading && docs.length === 0 && (
            <p className="text-sm text-text-muted text-center py-8">
              No documents uploaded yet for this entry.
            </p>
          )}
          {!isLoading && docs.map((doc) => (
            <div key={doc.doc_id} className="border border-border rounded-lg overflow-hidden">
              {/* Doc header */}
              <div className="px-4 py-3 bg-bg-s2 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium text-text truncate">
                    {doc.doc_type_label || doc.doc_type}
                  </p>
                  <p className="text-[11px] text-text-faint font-mono truncate">{doc.filename}</p>
                  {doc.uploaded_at && (
                    <p className="text-[10px] text-text-faint mt-0.5">
                      Uploaded {formatDate(doc.uploaded_at)}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {doc.verified ? (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-success/15 text-success border border-success/30 font-medium">
                      LLM Verified
                    </span>
                  ) : (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-warning/15 text-warning border border-warning/30 font-medium">
                      Needs Review
                    </span>
                  )}
                  {doc.sponsor_doc_approved && (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-accent/15 text-accent border border-accent/30 font-medium">
                      Sponsor ✓
                    </span>
                  )}
                </div>
              </div>

              {/* Download / view */}
              {doc.download_url ? (
                <div className="px-4 py-3 border-t border-border flex items-center gap-3">
                  <a
                    href={doc.download_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium bg-accent text-white hover:bg-accent-dark transition-colors"
                  >
                    <svg viewBox="0 0 20 20" className="w-3.5 h-3.5 fill-current">
                      <path d="M13 8V2H7v6H2l8 8 8-8h-5zM0 18h20v2H0v-2z"/>
                    </svg>
                    Open File
                  </a>
                  <span className="text-[11px] text-text-faint">Opens from MinIO storage</span>
                </div>
              ) : doc.content_preview ? (
                <div className="px-4 py-3 border-t border-border">
                  <p className="text-[10px] font-mono text-text-faint uppercase tracking-wide mb-1">
                    Document Preview
                  </p>
                  <pre className="text-[11px] text-text-muted bg-bg-s2 rounded p-2.5 whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-y-auto border border-border/50">
                    {doc.content_preview}
                  </pre>
                </div>
              ) : null}

              {/* Verification note */}
              {doc.verification_note && (
                <div className="px-4 py-2 border-t border-border/50 bg-bg">
                  <p className="text-xs text-text-muted italic">{doc.verification_note}</p>
                </div>
              )}
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-5 py-4 border-t border-border space-y-3">
          {error && <p className="text-xs text-danger">{error}</p>}
          {(approved || allSponsorApproved) && (
            <p className="text-xs text-success font-medium">
              Documents approved — you can now approve the request.
            </p>
          )}

          {showApproveFooter && (
            <>
              <label className="block">
                <span className="label-mono">Approval Note</span>
                <input
                  type="text"
                  className="input-field"
                  placeholder="e.g. Documentation reviewed and verified"
                  value={approveNote}
                  onChange={(e) => setApproveNote(e.target.value)}
                />
              </label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleApproveDocs}
                  disabled={isApproving}
                  className="px-4 py-2 rounded-md text-[13px] font-medium text-white bg-success hover:bg-success/80 transition-colors disabled:opacity-50"
                >
                  {isApproving ? 'Approving…' : 'Approve Documents'}
                </button>
                <button type="button" onClick={onClose} className="btn-secondary">
                  Close
                </button>
              </div>
            </>
          )}

          {!showApproveFooter && (
            <div className="flex justify-end">
              <button type="button" onClick={onClose} className="btn-secondary">
                Close
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function Queue() {
  const { principal } = useAuth();
  const [entries, setEntries] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('all');
  const [actionFilter, setActionFilter] = useState('all');
  const [dialog, setDialog] = useState(null); // { entry, mode }
  const [docsEntry, setDocsEntry] = useState(null); // entry whose docs are open
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await apiClient.getQueue();
      setEntries(res.entries || []);
    } catch {
      // leave existing state on error
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    function onQueueUpdated() {
      load({ silent: true });
    }
    window.addEventListener(QUEUE_UPDATED_EVENT, onQueueUpdated);
    const interval = setInterval(() => load({ silent: true }), AUTO_REFRESH_MS);
    return () => {
      window.removeEventListener(QUEUE_UPDATED_EVENT, onQueueUpdated);
      clearInterval(interval);
    };
  }, [load]);

  const planScoped = useMemo(
    () => entries.filter((e) => !principal?.planId || e.plan_id === principal.planId),
    [entries, principal?.planId],
  );

  const actionOptions = useMemo(() => {
    const unique = Array.from(new Set(planScoped.map((e) => e.action)));
    return [{ value: 'all', label: 'All Actions' }, ...unique.map((a) => ({ value: a, label: titleCase(a) }))];
  }, [planScoped]);

  const filtered = useMemo(
    () =>
      planScoped.filter(
        (e) =>
          (statusFilter === 'all' || e.status === statusFilter) &&
          (actionFilter === 'all' || e.action === actionFilter),
      ),
    [planScoped, statusFilter, actionFilter],
  );

  async function handleDecision(note) {
    if (!dialog) return;
    setIsSubmitting(true);
    setError(null);
    try {
      if (dialog.mode === 'approve') {
        await apiClient.approveQueueEntry(dialog.entry.entry_id, note);
      } else {
        await apiClient.denyQueueEntry(dialog.entry.entry_id, note);
      }
      setDialog(null);
      await load({ silent: true });
    } catch (err) {
      setError(err.message || 'Failed to submit decision');
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isLoading) {
    return <LoadingState label="Loading review queue…" />;
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm text-text-muted mb-4 max-w-2xl">
          Hardship distributions, QDROs, and beneficiary updates flagged for human review.
        </p>
        <div className="flex flex-wrap items-center gap-3 mb-4">
          <FilterSelect label="Status" value={statusFilter} onChange={setStatusFilter} options={STATUS_OPTIONS} />
          <FilterSelect label="Action" value={actionFilter} onChange={setActionFilter} options={actionOptions} />
          <span className="text-xs text-text-faint sm:ml-auto">
            {filtered.length} of {planScoped.length} entries
          </span>
        </div>

        {error && <p className="text-xs text-danger mb-3">{error}</p>}

        <div className="card p-4 sm:p-6">
          <QueueTable
            entries={filtered}
            onApprove={(entry) => setDialog({ entry, mode: 'approve' })}
            onDeny={(entry) => setDialog({ entry, mode: 'deny' })}
            onViewDocs={(entry) => setDocsEntry(entry)}
          />
        </div>
      </div>

      {dialog && (
        <DecisionDialog
          entry={dialog.entry}
          mode={dialog.mode}
          isSubmitting={isSubmitting}
          onSubmit={handleDecision}
          onCancel={() => setDialog(null)}
        />
      )}

      {docsEntry && (
        <DocsModal
          entry={docsEntry}
          onClose={() => setDocsEntry(null)}
          onDocApproved={() => {
            load({ silent: true });
          }}
        />
      )}
    </div>
  );
}
