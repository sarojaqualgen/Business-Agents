import React, { useRef, useState } from 'react';
import { apiClient } from '../../lib/apiClient.js';

// Maps expense_type → available doc_type values.
// Mirrors the table in POST /documents/upload Swagger description.
const DOC_TYPES = {
  medical: [
    { value: 'medical_bill', label: 'Medical Bill' },
    { value: 'hospital_statement', label: 'Hospital Statement' },
    { value: 'doctor_invoice', label: 'Doctor Invoice' },
    { value: 'explanation_of_benefits', label: 'Explanation of Benefits (EOB)' },
  ],
  prevent_eviction: [
    { value: 'eviction_notice', label: 'Eviction Notice' },
    { value: 'foreclosure_letter', label: 'Foreclosure Letter' },
    { value: 'utility_shutoff_notice', label: 'Utility Shutoff Notice' },
  ],
  tuition: [
    { value: 'tuition_invoice', label: 'Tuition Invoice' },
    { value: 'enrollment_verification', label: 'Enrollment Verification' },
    { value: 'financial_aid_letter', label: 'Financial Aid Letter' },
  ],
  funeral: [
    { value: 'funeral_invoice', label: 'Funeral Invoice' },
    { value: 'death_certificate', label: 'Death Certificate' },
  ],
  primary_home_purchase: [
    { value: 'purchase_agreement', label: 'Purchase Agreement' },
    { value: 'contractor_estimate', label: 'Contractor Estimate' },
    { value: 'builder_contract', label: 'Builder Contract' },
  ],
  casualty_loss: [
    { value: 'insurance_claim', label: 'Insurance Claim' },
    { value: 'damage_assessment', label: 'Damage Assessment' },
  ],
  FEMA_disaster: [
    { value: 'FEMA_declaration', label: 'FEMA Declaration' },
    { value: 'damage_proof', label: 'Damage Proof' },
  ],
  qdro: [
    { value: 'court_order', label: 'Court Order (QDRO)' },
    { value: 'divorce_decree', label: 'Divorce Decree' },
  ],
};

const EXPENSE_TYPES_HARDSHIP = [
  { value: 'medical', label: 'Medical / Hospital Bills' },
  { value: 'prevent_eviction', label: 'Eviction / Foreclosure Prevention' },
  { value: 'tuition', label: 'Educational Tuition' },
  { value: 'funeral', label: 'Funeral / Burial Expenses' },
  { value: 'primary_home_purchase', label: 'Primary Home Purchase or Repair' },
  { value: 'casualty_loss', label: 'Casualty Loss' },
  { value: 'FEMA_disaster', label: 'FEMA Disaster Relief' },
];

const ACCEPTED_FORMATS = '.txt,.pdf,.docx';
const MAX_FILE_MB = 10;

function VerifiedBadge({ verified }) {
  return verified ? (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success bg-success/10 px-2 py-0.5 rounded-full">
      <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 fill-success"><path d="M13.5 3.5 6 11 2.5 7.5l-1 1L6 13l8.5-8.5z"/></svg>
      Verified
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-danger bg-danger/10 px-2 py-0.5 rounded-full">
      <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 fill-danger"><path d="M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1zm.75 4v4.5h-1.5V5h1.5zm0 6v1.5h-1.5V11h1.5z"/></svg>
      Rejected
    </span>
  );
}

export default function DocumentUploadCard({ entryId, actionType, expenseType: initialExpenseType, onDismiss, onUploadComplete }) {
  const isQdro = actionType === 'qdro';
  const [expenseType, setExpenseType] = useState(
    isQdro ? 'qdro' : (initialExpenseType || '')
  );
  const [docType, setDocType] = useState('');
  const [file, setFile] = useState(null);
  const [isDragOver, setIsDragOver] = useState(false);
  const [status, setStatus] = useState('idle'); // idle | uploading | success | error
  const [result, setResult] = useState(null);
  const [errorMsg, setErrorMsg] = useState('');
  const fileInputRef = useRef(null);

  const availableDocTypes = DOC_TYPES[expenseType] || [];

  function handleExpenseChange(val) {
    setExpenseType(val);
    setDocType('');
  }

  function acceptFile(f) {
    if (!f) return;
    const ext = f.name.split('.').pop()?.toLowerCase();
    if (!['txt', 'pdf', 'docx'].includes(ext)) {
      setErrorMsg('Only .txt, .pdf, and .docx files are accepted.');
      return;
    }
    if (f.size > MAX_FILE_MB * 1024 * 1024) {
      setErrorMsg(`File must be under ${MAX_FILE_MB} MB.`);
      return;
    }
    setErrorMsg('');
    setFile(f);
  }

  function handleDrop(e) {
    e.preventDefault();
    setIsDragOver(false);
    acceptFile(e.dataTransfer.files[0]);
  }

  async function handleUpload() {
    if (!file || !docType || !expenseType) return;
    setStatus('uploading');
    setErrorMsg('');
    try {
      const res = await apiClient.uploadDocumentFast({
        queueEntryId: entryId,
        actionType,
        expenseType,
        docType,
        file,
      });
      setResult(res);
      setStatus('success');
      // Doc is now in the system — clear both sessionStorage keys so navigating
      // away and returning doesn't re-show the upload form.
      try {
        sessionStorage.removeItem('pendingUpload');
        sessionStorage.removeItem('activityUploadOpen');
      } catch { /* storage unavailable */ }
      // Notify parent so it can inject a status message into the chat transcript.
      onUploadComplete?.(res);
    } catch (err) {
      setErrorMsg(err.message || 'Upload failed. Please try again.');
      setStatus('idle');
    }
  }

  const canUpload = file && docType && expenseType && status === 'idle';

  // ── Success state ──────────────────────────────────────────────────────────
  if (status === 'success') {
    const verified = result?.verified ?? false;
    return (
      <div className={`mt-2 ml-11 border ${verified ? 'border-success/30 bg-success/5' : 'border-danger/30 bg-danger/5'} rounded-xl p-4 msg-enter`}>
        <div className="flex items-start gap-3">
          <div className={`w-8 h-8 rounded-full ${verified ? 'bg-success/15' : 'bg-danger/15'} flex items-center justify-center flex-shrink-0 mt-0.5`}>
            {verified ? (
              <svg viewBox="0 0 20 20" className="w-4 h-4 fill-success">
                <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7 7a1 1 0 0 1-1.4 0l-3-3a1 1 0 1 1 1.4-1.4L9 11.59l6.3-6.3a1 1 0 0 1 1.4 0z" clipRule="evenodd"/>
              </svg>
            ) : (
              <svg viewBox="0 0 20 20" className="w-4 h-4 fill-danger">
                <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/>
              </svg>
            )}
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-sm font-semibold text-text">
                {verified ? 'Document verified' : 'Document rejected'}
              </span>
              <VerifiedBadge verified={verified} />
            </div>
            {verified ? (
              <>
                {result?.key_details && (
                  <p className="text-xs text-text-muted leading-relaxed">{result.key_details}</p>
                )}
                {result?.name_on_document && (
                  <p className="text-xs text-text-faint mt-1">
                    <span className="font-medium text-text-muted">Name on document:</span> {result.name_on_document}
                  </p>
                )}
                {result?.filename && (
                  <p className="text-xs text-text-faint mt-0.5 font-mono truncate">{result.filename}</p>
                )}
                <p className="text-xs text-success/70 mt-2">
                  Your document is on file and awaiting administrator approval.
                </p>
              </>
            ) : (
              <>
                {result?.verification_note && (
                  <p className="text-xs text-danger/80 leading-relaxed mb-1">{result.verification_note}</p>
                )}
                <p className="text-xs text-danger/70 font-medium">
                  Your request has been cancelled. Please start a new request with a valid document.
                </p>
              </>
            )}
          </div>
          <button
            onClick={onDismiss}
            aria-label="Dismiss"
            className="text-text-faint hover:text-text-muted transition-colors flex-shrink-0"
          >
            <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current">
              <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/>
            </svg>
          </button>
        </div>
      </div>
    );
  }

  // ── Upload form ────────────────────────────────────────────────────────────
  return (
    <div className="mt-2 ml-11 border border-accent/20 bg-accent-light/30 rounded-xl p-4 msg-enter">
      <div className="flex items-start justify-between gap-2 mb-3">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-7 h-7 rounded-lg bg-accent/15 flex items-center justify-center">
              <svg viewBox="0 0 20 20" className="w-4 h-4 fill-accent">
                <path d="M9 2a1 1 0 000 2h2a1 1 0 100-2H9z"/>
                <path fillRule="evenodd" d="M4 5a2 2 0 012-2v1a2 2 0 002 2h4a2 2 0 002-2V3a2 2 0 012 2v11a2 2 0 01-2 2H6a2 2 0 01-2-2V5zm8 3a1 1 0 10-2 0v3.586l-1.293-1.293a1 1 0 10-1.414 1.414l3 3a1 1 0 001.414 0l3-3a1 1 0 10-1.414-1.414L12 11.586V8z" clipRule="evenodd"/>
              </svg>
            </div>
            <div>
              <p className="text-sm font-semibold text-text">Upload Supporting Document</p>
              <p className="text-[11px] text-text-muted">Entry #{entryId}</p>
            </div>
          </div>
          <p className="text-xs text-text-muted mt-2 leading-relaxed">
            Your plan administrator requires proof before approving this request. Upload a document and our system will verify it automatically.
          </p>
        </div>
        <button onClick={onDismiss} aria-label="Skip upload" className="text-text-faint hover:text-text-muted transition-colors flex-shrink-0">
          <svg viewBox="0 0 20 20" className="w-4 h-4 fill-current">
            <path d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"/>
          </svg>
        </button>
      </div>

      <div className="space-y-3">
        {/* Expense type — hidden for QDRO (always qdro) */}
        {!isQdro && (
          <div>
            <label className="label-mono">Expense type</label>
            <select
              className="input-field text-sm"
              value={expenseType}
              onChange={(e) => handleExpenseChange(e.target.value)}
            >
              <option value="">Select expense type…</option>
              {EXPENSE_TYPES_HARDSHIP.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>
        )}

        {/* Document type */}
        <div>
          <label className="label-mono">Document type</label>
          <select
            className="input-field text-sm"
            value={docType}
            onChange={(e) => setDocType(e.target.value)}
            disabled={!expenseType}
          >
            <option value="">Select document type…</option>
            {availableDocTypes.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>

        {/* File drop zone */}
        <div>
          <label className="label-mono">Document file</label>
          <div
            className={[
              'border-2 border-dashed rounded-lg px-4 py-5 text-center cursor-pointer transition-colors',
              isDragOver
                ? 'border-accent bg-accent-light'
                : file
                ? 'border-success/40 bg-success/5'
                : 'border-border-strong hover:border-accent/50 hover:bg-accent-light/50',
            ].join(' ')}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => { e.preventDefault(); setIsDragOver(true); }}
            onDragLeave={() => setIsDragOver(false)}
            onDrop={handleDrop}
          >
            {file ? (
              <div className="flex items-center justify-center gap-2">
                <svg viewBox="0 0 20 20" className="w-4 h-4 fill-success flex-shrink-0">
                  <path fillRule="evenodd" d="M16.7 5.3a1 1 0 0 1 0 1.4l-7 7a1 1 0 0 1-1.4 0l-3-3a1 1 0 1 1 1.4-1.4L9 11.59l6.3-6.3a1 1 0 0 1 1.4 0z" clipRule="evenodd"/>
                </svg>
                <span className="text-xs font-medium text-text truncate max-w-[200px]">{file.name}</span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); setFile(null); }}
                  className="text-text-faint hover:text-danger transition-colors"
                >
                  <svg viewBox="0 0 16 16" className="w-3.5 h-3.5 fill-current">
                    <path d="M4.293 4.293a1 1 0 011.414 0L8 6.586l2.293-2.293a1 1 0 111.414 1.414L9.414 8l2.293 2.293a1 1 0 01-1.414 1.414L8 9.414l-2.293 2.293a1 1 0 01-1.414-1.414L6.586 8 4.293 5.707a1 1 0 010-1.414z"/>
                  </svg>
                </button>
              </div>
            ) : (
              <div>
                <svg viewBox="0 0 24 24" className="w-6 h-6 fill-text-faint mx-auto mb-1.5">
                  <path d="M9 16h6v-6h4l-7-7-7 7h4zm-4 2h14v2H5z"/>
                </svg>
                <p className="text-xs text-text-muted">Drop file here or <span className="text-accent font-medium">browse</span></p>
                <p className="text-[10px] text-text-faint mt-0.5">.txt · .pdf · .docx · max {MAX_FILE_MB} MB</p>
              </div>
            )}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FORMATS}
            className="hidden"
            onChange={(e) => acceptFile(e.target.files?.[0])}
          />
        </div>

        {errorMsg && (
          <p className="text-xs text-danger">{errorMsg}</p>
        )}

        <button
          type="button"
          onClick={handleUpload}
          disabled={!canUpload}
          className="w-full py-2.5 rounded-lg text-sm font-medium transition-colors bg-accent hover:bg-accent-dark text-white disabled:bg-border-strong disabled:text-text-faint disabled:cursor-not-allowed flex items-center justify-center gap-2"
        >
          {status === 'uploading' ? (
            <>
              <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.5}>
                <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/>
              </svg>
              Uploading & verifying…
            </>
          ) : (
            'Upload & Verify Document'
          )}
        </button>
      </div>
    </div>
  );
}
