import React, { useEffect, useRef } from 'react';

/**
 * Fully controlled chat composer. Parent owns the draft string via
 * `value` + `onChange`. Sending clears the draft by calling `onChange('')`
 * after invoking `onSend`. Auto-resizes up to 110px tall.
 */
export default function ChatInput({ value, onChange, onSend, disabled }) {
  const textareaRef = useRef(null);

  // Resize whenever the draft changes (including external fills from
  // SuggestedPrompts — which now populate the field without submitting).
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 110)}px`;
  }, [value]);

  function submit() {
    const trimmed = (value || '').trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    onChange('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <div className="border-t border-border px-5 py-3.5 flex gap-2.5 items-end flex-shrink-0 bg-bg-surface">
      <div className="flex-1 bg-bg border border-border-strong rounded-xl flex items-end px-3.5 py-2.5 gap-2 focus-within:border-accent focus-within:ring-2 focus-within:ring-accent/10 transition-all duration-150">
        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder="Ask about loans, deferrals, investments, hardship withdrawals…"
          className="flex-1 bg-transparent border-none outline-none text-text text-sm leading-relaxed resize-none max-h-[110px] overflow-y-auto placeholder:text-text-faint disabled:opacity-60"
        />
      </div>
      <button
        type="button"
        onClick={submit}
        disabled={disabled || !(value || '').trim()}
        aria-label="Send message"
        className="w-9 h-9 bg-accent hover:bg-accent-dark disabled:bg-border-strong disabled:cursor-not-allowed rounded-lg flex items-center justify-center flex-shrink-0 transition-colors shadow-sm"
      >
        <svg viewBox="0 0 24 24" className="w-4 h-4 fill-white">
          <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z" />
        </svg>
      </button>
    </div>
  );
}
