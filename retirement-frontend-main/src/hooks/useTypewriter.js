import { useEffect, useRef, useState } from 'react';

/**
 * Deterministic character-reveal animation for a completed response string.
 * No randomness, no network — purely a setInterval walking an index across
 * `text`. Intended for the final assistant response bubble, layered on top
 * of the already-deterministic mock AI pipeline (trace steps -> response).
 *
 * @param {string} text - full text to reveal
 * @param {object} opts
 * @param {boolean} opts.skip - render `text` immediately with no animation
 *   (used for history rehydrated from localStorage)
 * @param {number} opts.speedMs - ms per character batch
 * @param {number} opts.charsPerTick - characters revealed per tick (keeps
 *   long ERISA disclosure paragraphs from feeling sluggish)
 * @param {() => void} opts.onDone - fired once, when the full text has been
 *   revealed
 */
export function useTypewriter(text, { skip = false, speedMs = 14, charsPerTick = 2, onDone } = {}) {
  const [visibleLength, setVisibleLength] = useState(skip ? (text || '').length : 0);
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (skip || !text) {
      setVisibleLength((text || '').length);
      return undefined;
    }

    setVisibleLength(0);
    const interval = setInterval(() => {
      setVisibleLength((current) => {
        const next = Math.min(current + charsPerTick, text.length);
        if (next >= text.length) {
          clearInterval(interval);
          onDoneRef.current?.();
        }
        return next;
      });
    }, speedMs);

    return () => clearInterval(interval);
    // Re-run only when the underlying text or skip flag changes — not on
    // every render — so the animation isn't restarted by unrelated state.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text, skip]);

  const done = visibleLength >= (text || '').length;
  return { visibleText: (text || '').slice(0, visibleLength), done };
}
