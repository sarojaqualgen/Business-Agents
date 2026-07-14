import React from 'react';
import AgentStep from './AgentStep.jsx';

/**
 * Vertical, connector-style timeline of agent/tool trace steps. Purely a
 * layout wrapper around AgentStep — all step data comes from the mock AI
 * pipeline (mockChatEngine.simulateChatStream) via ChatContext, so this
 * component has no logic of its own beyond ordering and the trailing
 * "live" cursor shown while a response is still streaming in.
 */
export default function TraceTimeline({ steps, isStreaming }) {
  if (steps.length === 0) return null;

  return (
    <div className="flex flex-col">
      {steps.map((step, i) => (
        <AgentStep key={i} step={step} isLast={i === steps.length - 1 && !isStreaming} />
      ))}
      {isStreaming && (
        <div className="flex gap-2 items-center font-mono text-[11px] text-text-faint pt-0.5">
          <span className="w-3 flex justify-center flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
          </span>
          <span>working…</span>
        </div>
      )}
    </div>
  );
}
