import React, { useState } from 'react';
import Avatar from '../ui/Avatar.jsx';
import AgentTracePanel from './AgentTracePanel.jsx';
import TransactionSummaryCard from './TransactionSummaryCard.jsx';
import MarkdownText from './MarkdownText.jsx';
import { formatTime } from '../../lib/format.js';

function SystemNotice({ message }) {
  const isCancelled = message.status === 'cancelled';
  return (
    <div className="max-w-md mx-auto text-center msg-enter">
      <p className={`text-xs ${isCancelled ? 'text-text-faint' : 'text-success'}`}>
        {isCancelled ? '' : '✅ '}
        {message.text}
      </p>
    </div>
  );
}

function CopyButton({ text }) {
  const [copied, setCopied] = useState(false);

  async function handleCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // Clipboard API unavailable (e.g. insecure context) — fail silently,
      // this is a convenience affordance, not a core chat function.
    }
  }

  return (
    <button
      type="button"
      onClick={handleCopy}
      className="text-[10px] font-mono text-text-faint hover:text-text-muted transition-colors self-start"
      aria-label="Copy response"
    >
      {copied ? 'copied ✓' : 'copy'}
    </button>
  );
}

export default function MessageBubble({ message, userInitials }) {
  if (message.role === 'system') {
    return <SystemNotice message={message} />;
  }

  if (message.role === 'user') {
    return (
      <div className="flex gap-3 max-w-2xl ml-auto flex-row-reverse msg-enter">
        <Avatar name={userInitials} principalType="participant" size={32} />
        <div className="flex flex-col items-end gap-1">
          <div className="bg-accent-dark text-white rounded-[12px_4px_12px_12px] px-4 py-3 text-sm leading-relaxed">
            {message.text}
          </div>
          {message.createdAt && (
            <span className="text-[10px] font-mono text-text-faint pr-1">{formatTime(message.createdAt)}</span>
          )}
        </div>
      </div>
    );
  }

  // assistant
  return (
    <div className="flex gap-3 max-w-2xl msg-enter">
      <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-[11px] font-semibold text-white mt-0.5 bg-gradient-to-br from-accent-dark to-accent">
        A
      </div>
      <div className="flex-1 min-w-0 flex flex-col gap-1.5">
        {(message.steps?.length > 0 || message.isStreaming) && (
          <AgentTracePanel steps={message.steps} isStreaming={message.isStreaming} intent={message.intent} />
        )}
        {!message.isStreaming && message.text && (
          <div
            className={[
              'px-4 py-3 rounded-[4px_12px_12px_12px] border msg-enter',
              message.isError ? 'bg-bg-surface border-danger text-danger' : 'bg-bg-surface border-border text-text',
            ].join(' ')}
          >
            <MarkdownText text={message.text} />
          </div>
        )}
        {!message.isStreaming && message.text && !message.isError && (
          <div className="flex items-center gap-2 pl-1">
            {message.createdAt && (
              <span className="text-[10px] font-mono text-text-faint">{formatTime(message.createdAt)}</span>
            )}
            <CopyButton text={message.text} />
          </div>
        )}
        {!message.isStreaming && message.transaction && message.transaction.status !== 'pending_confirmation' && (
          <TransactionSummaryCard transaction={message.transaction} />
        )}
      </div>
    </div>
  );
}
