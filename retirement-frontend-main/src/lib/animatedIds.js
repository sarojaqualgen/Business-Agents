// Tracks which streamed assistant message ids have already played their
// character-reveal animation in this browser session. Backed by a plain
// in-memory Set (not persisted), so:
//   - a message streamed in *this* session animates once, then stays static
//   - messages rehydrated from localStorage on page load render instantly,
//     since their ids were never marked animated in the fresh module state
//
// Kept as a tiny standalone module (rather than component state) so both
// StreamingText and any future consumer share one source of truth without
// prop drilling.

const animated = new Set();

export function hasAnimated(id) {
  return animated.has(id);
}

export function markAnimated(id) {
  animated.add(id);
}
