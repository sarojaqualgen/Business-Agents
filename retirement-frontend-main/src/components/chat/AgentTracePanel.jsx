import React, { useEffect, useRef, useState } from 'react';
import TraceTimeline from './trace/TraceTimeline.jsx';
import IntentBadge from './trace/IntentBadge.jsx';

/**
 * Streams incremental agent/tool trace lines while a chat response is in
 * flight, then auto-collapses once the response arrives — matching the
 * "thinking block" pattern from the original chatbot_ui_1.html demo, but
 * driven entirely by real hook state instead of scripted timeouts.
 *
 * Step rendering itself is delegated to TraceTimeline/AgentStep (reusable
 * trace primitives) so this component only owns the expand/collapse chrome.
 */
export default function AgentTracePanel({ steps, isStreaming, intent }) {
  const [expanded, setExpanded] = useState(true);
  const [elapsed, setElapsed] = useState(0);
  const startRef = useRef(null);

  useEffect(() => {
    if (!isStreaming && steps.length > 0) {
      setExpanded(false);
    }
  }, [isStreaming, steps.length]);

  // Tick elapsed seconds while streaming so the user can see progress even
  // during the silent LLM-processing gaps between tool calls.
  useEffect(() => {
    if (!isStreaming) {
      setElapsed(0);
      startRef.current = null;
      return;
    }
    startRef.current = Date.now();
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startRef.current) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [isStreaming]);

  if (steps.length === 0 && !isStreaming) return null;

  return (
    <div className="bg-bg-surface border border-border rounded-lg overflow-hidden">
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3.5 py-2 text-xs text-text-faint hover:text-text-muted transition-colors"
      >
        <span
          className={[
            'w-3 h-3 rounded-full border-2 flex-shrink-0',
            isStreaming ? 'border-border-strong border-t-accent animate-spin' : 'border-success',
          ].join(' ')}
        />
        <span className="font-mono text-[11px]">
          {isStreaming
            ? elapsed > 0
              ? `Thinking… ${elapsed}s${elapsed >= 20 ? ' — complex requests take 30–90s' : ''}`
              : 'Thinking…'
            : `${steps.length} step(s) traced`}
        </span>
        {intent && <IntentBadge intent={intent} />}
        <span className="ml-auto text-[10px]">{expanded ? '▾ collapse' : '▸ expand'}</span>
      </button>
      {expanded && (
        <div className="border-t border-border px-3.5 py-2.5 max-h-52 overflow-y-auto">
          <TraceTimeline steps={steps} isStreaming={isStreaming} />
        </div>
      )}
    </div>
  );
}
