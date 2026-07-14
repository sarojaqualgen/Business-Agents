// Thin, namespaced wrapper around window.localStorage.
//
// Every key is prefixed so the app never collides with other data a browser
// tab might hold, and every read/write is wrapped in try/catch so a private
// browsing mode or a full storage quota never crashes the app.

const NAMESPACE = 'aldergate';

function namespacedKey(key) {
  return `${NAMESPACE}:${key}`;
}

export function getItem(key, fallback = null) {
  try {
    const raw = window.localStorage.getItem(namespacedKey(key));
    if (raw === null) return fallback;
    return JSON.parse(raw);
  } catch {
    return fallback;
  }
}

export function setItem(key, value) {
  try {
    window.localStorage.setItem(namespacedKey(key), JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeItem(key) {
  try {
    window.localStorage.removeItem(namespacedKey(key));
    return true;
  } catch {
    return false;
  }
}

export function clearNamespace() {
  try {
    Object.keys(window.localStorage)
      .filter((k) => k.startsWith(`${NAMESPACE}:`))
      .forEach((k) => window.localStorage.removeItem(k));
    return true;
  } catch {
    return false;
  }
}

export const STORAGE_KEYS = {
  SESSION: 'session', // { sessionToken, expiresAt, principal }
  // Per-participant chat transcript + pending transaction, keyed so
  // switching participants (or roles) never mixes conversations.
  chatHistory: (participantId) => `chat:${participantId}`,
  // Mock-database overlay: { [participantId]: { ...fields changed by
  // executed transactions } }. Merged on top of the seed participant list
  // in mocks/data.js so account updates (loan draws, deferral changes,
  // reallocations, address changes) survive a page refresh.
  accountOverrides: 'accounts:overrides',
  // Sponsor-workflow persistence (Milestone 3 scope): plan overrides (e.g.
  // blackout state), queue entry overrides (approve/deny status), and the
  // append-only audit log. Same merge-on-top-of-seed pattern as
  // accountOverrides above.
  planOverrides: 'plans:overrides',
  queueOverrides: 'queue:overrides',
  auditLog: 'audit:log',
};
