import React, { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../../context/AuthContext.jsx';
import { apiClient } from '../../../lib/apiClient.js';
import { ACCOUNT_UPDATED_EVENT } from '../../../lib/events.js';
import LoadingState from '../../../components/ui/LoadingState.jsx';
import EmptyState from '../../../components/ui/EmptyState.jsx';

function formatDate(value) {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' });
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" className="w-5 h-5">
      <path d="M7 3.5h7l4 4V20a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4.5a1 1 0 0 1 1-1Z" />
      <path d="M14 3.5V8h4" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg viewBox="0 0 20 20" className="w-3.5 h-3.5 fill-current">
      <path d="M13 8V2H7v6H2l8 8 8-8h-5zM0 18h20v2H0v-2z" />
    </svg>
  );
}

function DocCard({ doc }) {
  const [expanded, setExpanded] = useState(false);

  const llmVerified = doc.verified;
  const sponsorApproved = doc.sponsor_doc_approved;

  return (
    <div className="card overflow-hidden">
      {/* Header row */}
      <div className="flex items-start gap-3.5 p-4">
        {/* Icon */}
        <div className="w-10 h-10 rounded-lg bg-bg-s2 border border-border text-text-muted flex items-center justify-center flex-shrink-0 mt-0.5">
          <FileIcon />
        </div>

        {/* Main info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div className="min-w-0">
              <p className="text-sm font-medium text-text truncate">{doc.filename}</p>
              <p className="text-[12px] text-text-muted mt-0.5">
                {doc.doc_type_label || doc.doc_type}
              </p>
            </div>

            {/* Status badges */}
            <div className="flex items-center gap-1.5 flex-shrink-0 flex-wrap">
              {llmVerified ? (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-success/12 text-success border border-success/30">
                  <svg viewBox="0 0 12 12" className="w-3 h-3 fill-current"><path d="M10 3L5 8.5 2 5.5l-.7.7 3.7 3.7L10.7 3.7z"/></svg>
                  LLM Verified
                </span>
              ) : (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-warning/12 text-warning border border-warning/30">
                  Needs Review
                </span>
              )}
              {sponsorApproved && (
                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-medium bg-accent/12 text-accent border border-accent/25">
                  <svg viewBox="0 0 12 12" className="w-3 h-3 fill-current"><path d="M10 3L5 8.5 2 5.5l-.7.7 3.7 3.7L10.7 3.7z"/></svg>
                  Sponsor Approved
                </span>
              )}
            </div>
          </div>

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-2 flex-wrap">
            <span className="text-[11px] text-text-faint">
              Uploaded {formatDate(doc.uploaded_at)}
            </span>
            {doc.queue_entry_id && (
              <span className="text-[11px] font-mono text-text-faint">
                Entry {doc.queue_entry_id}
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Action bar */}
      <div className="border-t border-border/60 px-4 py-2.5 bg-bg-s2/40 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          {doc.download_url ? (
            <a
              href={doc.download_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-[12px] font-medium bg-accent text-white hover:bg-accent-dark transition-colors"
            >
              <DownloadIcon />
              Open File
            </a>
          ) : (
            <span className="text-[11px] text-text-faint italic">File preview not available</span>
          )}
          <span className="text-[10px] text-text-faint">Your file, always accessible</span>
        </div>

        {doc.verification_note && (
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="text-[11px] text-text-faint hover:text-text transition-colors"
          >
            {expanded ? 'Hide details ↑' : 'Show verification details ↓'}
          </button>
        )}
      </div>

      {/* Expandable verification note */}
      {expanded && doc.verification_note && (
        <div className="px-4 py-3 border-t border-border/60 bg-bg">
          <p className="text-[10px] font-mono text-text-faint uppercase tracking-wide mb-1.5">
            LLM Verification Note
          </p>
          <p className="text-[12px] text-text-muted leading-relaxed italic">
            {doc.verification_note}
          </p>
        </div>
      )}
    </div>
  );
}

export default function Documents() {
  const { principal } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setIsLoading(true);
    try {
      const res = await apiClient.getParticipantDocuments();
      setDocuments(res.documents || []);
    } catch {
      setDocuments([]);
    } finally {
      if (!silent) setIsLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    function onUpdate(event) {
      if (event.detail?.participantId === principal?.participantId) load({ silent: true });
    }
    window.addEventListener(ACCOUNT_UPDATED_EVENT, onUpdate);
    return () => window.removeEventListener(ACCOUNT_UPDATED_EVENT, onUpdate);
  }, [principal?.participantId, load]);

  if (isLoading) return <LoadingState label="Loading your documents…" />;

  return (
    <div className="max-w-2xl space-y-5">
      <p className="text-sm text-text-muted max-w-xl">
        Documents you've submitted in support of a hardship or QDRO request.
        Click <strong>Open File</strong> to view the original file from secure storage.
      </p>

      {documents.length === 0 ? (
        <EmptyState
          tone="default"
          icon="empty"
          title="No documents uploaded"
          description="When you submit a hardship or QDRO request, your uploaded documents will appear here."
        />
      ) : (
        <>
          <p className="text-[11px] text-text-faint font-mono">
            {documents.length} document{documents.length !== 1 ? 's' : ''}
          </p>
          <div className="space-y-3">
            {documents.map((doc) => (
              <DocCard key={doc.doc_id} doc={doc} />
            ))}
          </div>
        </>
      )}
    </div>
  );
}
