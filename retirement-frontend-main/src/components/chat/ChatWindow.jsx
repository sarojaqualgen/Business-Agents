import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import QualGenLogo from '../../assets/QualGenLogo.jsx';
import { useChatStream } from '../../hooks/useChatStream.js';
import { useAuth } from '../../context/AuthContext.jsx';
import { initials } from '../../lib/format.js';
import MessageBubble from './MessageBubble.jsx';
import TypingIndicator from './TypingIndicator.jsx';
import SuggestedPrompts from './SuggestedPrompts.jsx';
import ConfirmationDialog from './ConfirmationDialog.jsx';
import TaxAcknowledgmentCard from './TaxAcknowledgmentCard.jsx';
import ChatInput from './ChatInput.jsx';
import DocumentUploadCard from './DocumentUploadCard.jsx';
import BankDetailsCard from './BankDetailsCard.jsx';
import { apiClient } from '../../lib/apiClient.js';
import { ACCOUNT_UPDATED_EVENT } from '../../lib/events.js';

export default function ChatWindow() {
  const { principal } = useAuth();
  const {
    messages,
    pendingTransaction,
    pendingUpload,
    pendingBankDetails,
    pendingTaxAck,
    isStreaming,
    isResolving,
    sendFastMessage,
    confirmTransaction,
    cancelTransaction,
    clearChat,
    dismissUpload,
    notifyUpload,
    submitBankDetails,
    dismissBankDetails,
    acknowledgeTax,
    cancelTaxAck,
  } = useChatStream();

  const location = useLocation();

  // Draft is owned here so SuggestedPrompts can fill it without auto-sending.
  // Also picks up any pre-filled text passed via navigate('/participant/chat', { state: { chatDraft } }).
  const [draft, setDraft] = useState(() => location.state?.chatDraft || '');

  // Clear the navigation state so the pre-fill doesn't resurface on re-renders.
  useEffect(() => {
    if (location.state?.chatDraft) {
      window.history.replaceState({ ...location.state, chatDraft: undefined }, '');
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const scrollRef = useRef(null);
  const userInitials = initials(principal?.participantId || 'P');

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages, isStreaming, pendingTransaction, pendingUpload, pendingBankDetails]);

  const lastMessage = messages[messages.length - 1];
  const showTypingIndicator =
    isStreaming && lastMessage?.role === 'assistant' && lastMessage.isStreaming && lastMessage.steps.length === 0;

  const blocked = isStreaming || Boolean(pendingTransaction) || Boolean(pendingBankDetails) || Boolean(pendingTaxAck);

  // Pin the upload card to the most recent human_review message so it stays
  // mounted there even as new messages are added after it. Avoids the card
  // unmounting/remounting in idle state when notifyUpload injects a new message.
  const uploadCardIdx = pendingUpload
    ? messages.reduce((acc, m, i) => (m.autonomy === 'human_review' ? i : acc), -1)
    : -1;

  return (
    <div className="flex flex-col h-[calc(100vh-140px)] card overflow-hidden">
      {/* ── Chat header ─────────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-5 py-3 border-b border-border flex-shrink-0">
        <div className="flex items-center gap-2.5">
          <QualGenLogo height={24} textDark={true} />
          <div>
            <p className="text-sm font-semibold text-text leading-none">Assistant</p>
            {messages.length > 0 && (
              <p className="text-[10px] text-text-faint mt-0.5">{messages.length} message{messages.length !== 1 ? 's' : ''}</p>
            )}
          </div>
        </div>
        <div className="flex items-center gap-3">
          {messages.length > 0 && (
            <button
              type="button"
              onClick={clearChat}
              title="Clear conversation"
              className="flex items-center gap-1.5 text-xs text-text-faint hover:text-danger transition-colors px-2 py-1 rounded-md hover:bg-danger/8"
            >
              <svg viewBox="0 0 20 20" className="w-3.5 h-3.5 fill-current">
                <path fillRule="evenodd" d="M9 2a1 1 0 00-.894.553L7.382 4H4a1 1 0 000 2v10a2 2 0 002 2h8a2 2 0 002-2V6a1 1 0 100-2h-3.382l-.724-1.447A1 1 0 0011 2H9zm-1 7a1 1 0 112 0v3a1 1 0 11-2 0V9zm4 0a1 1 0 112 0v3a1 1 0 11-2 0V9z" clipRule="evenodd"/>
              </svg>
              Clear chat
            </button>
          )}
        </div>
      </div>

      {/* ── Transcript ──────────────────────────────────────────────────────── */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-5 flex flex-col gap-4">
        {messages.length === 0 ? (
          <div className="flex-1 flex flex-col items-center justify-center gap-4 text-center px-6">
            <QualGenLogo height={36} textDark={true} iconOnly={true} />
            <div>
              <h2 className="text-sm font-semibold text-text mb-1">Ask QualGen anything</h2>
              <p className="text-xs text-text-muted max-w-sm">
                Loans, deferral changes, investment reallocation, hardship withdrawals, beneficiary and address
                updates — all in plain English.
              </p>
            </div>
            <div className="w-full max-w-sm">
              <p className="text-[10px] uppercase tracking-widest text-text-faint mb-3 font-medium">Suggested</p>
              <SuggestedPrompts onSelect={setDraft} disabled={blocked} />
            </div>
          </div>
        ) : (
          <>
            {messages.map((message, idx) => (
              <React.Fragment key={message.id}>
                <MessageBubble message={message} userInitials={userInitials} />
                {/* Confirm/cancel — pinned right below the supervised response */}
                {!message.isStreaming && message.autonomy === 'supervised' && pendingTransaction && (
                  <div className="max-w-2xl ml-11 msg-enter">
                    <ConfirmationDialog
                      transaction={pendingTransaction}
                      onConfirm={confirmTransaction}
                      onCancel={cancelTransaction}
                      isResolving={isResolving}
                    />
                  </div>
                )}
                {/* Tax acknowledgment — shown when a distribution needs explicit tax disclosure */}
                {!message.isStreaming && pendingTaxAck && idx === messages.length - 1 && (
                  <div className="max-w-2xl ml-11 msg-enter">
                    <TaxAcknowledgmentCard
                      onConfirm={acknowledgeTax}
                      onCancel={cancelTaxAck}
                      isResolving={isResolving}
                    />
                  </div>
                )}
                {/* Bank details — shows after confirming a disbursement loan */}
                {pendingBankDetails && idx === messages.length - 1 && (
                  <div className="max-w-2xl ml-11 msg-enter">
                    <BankDetailsCard
                      action={pendingBankDetails.action}
                      onSubmit={submitBankDetails}
                      onCancel={dismissBankDetails}
                      isSubmitting={isResolving}
                    />
                  </div>
                )}
                {/* Document upload — pinned to the human_review message so the card
                    stays mounted (and keeps its success state) even when new messages
                    are added after it (e.g. the notifyUpload status message). */}
                {uploadCardIdx !== -1 && idx === uploadCardIdx && (
                  <div className="max-w-2xl ml-11 msg-enter">
                    <DocumentUploadCard
                      entryId={pendingUpload.entryId}
                      actionType={pendingUpload.actionType}
                      expenseType={pendingUpload.expenseType}
                      onDismiss={dismissUpload}
                      onUploadComplete={async (result) => {
                        // If rejected, cancel the queue entry so it leaves the sponsor queue.
                        let cancelled = false;
                        if (!result?.verified && pendingUpload?.entryId) {
                          try {
                            await apiClient.cancelQueueEntry(pendingUpload.entryId);
                            cancelled = true;
                          } catch {
                            // Cancel failed — queue entry stays pending; message will reflect this.
                          }
                        }
                        // Inject a short persistent message into the chat transcript.
                        notifyUpload(result, cancelled);
                        // Tell the Activity page to refresh so the updated status (cancelled
                        // or pending_review with verified doc) shows immediately.
                        if (principal?.participantId) {
                          window.dispatchEvent(new CustomEvent(ACCOUNT_UPDATED_EVENT, {
                            detail: { participantId: principal.participantId },
                          }));
                        }
                      }}
                    />
                  </div>
                )}
              </React.Fragment>
            ))}
            {showTypingIndicator && <TypingIndicator />}
          </>
        )}
      </div>

      {/* ── Inline prompt suggestions (below transcript when chat has started) */}
      {messages.length > 0 && !blocked && !pendingUpload && (
        <div className="px-5 pt-2 pb-1">
          <SuggestedPrompts onSelect={setDraft} disabled={blocked} />
        </div>
      )}

      {/* ── Composer ────────────────────────────────────────────────────────── */}
      <ChatInput
        value={draft}
        onChange={setDraft}
        onSend={sendFastMessage}
        disabled={blocked}
      />
    </div>
  );
}
