import React from 'react';

/**
 * Lightweight "assistant is composing" cue. Shown the instant a message is
 * sent — before the first agent_start/tool_use trace event has arrived —
 * so the UI never feels idle while useChatStream waits on the network.
 * Once trace events start flowing, AgentTracePanel takes over.
 */
export default function TypingIndicator() {
  return (
    <div className="flex gap-3 max-w-2xl">
      <div className="w-8 h-8 rounded-full flex-shrink-0 flex items-center justify-center text-[11px] font-semibold text-white mt-0.5 bg-gradient-to-br from-accent-dark to-accent">
        A
      </div>
      <div className="bg-bg-surface border border-border rounded-[4px_12px_12px_12px] px-4 py-3 flex items-center gap-1">
        <span className="w-1.5 h-1.5 rounded-full bg-text-faint animate-bounce [animation-delay:-0.3s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-text-faint animate-bounce [animation-delay:-0.15s]" />
        <span className="w-1.5 h-1.5 rounded-full bg-text-faint animate-bounce" />
      </div>
    </div>
  );
}
