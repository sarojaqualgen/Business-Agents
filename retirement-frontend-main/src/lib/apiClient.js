// Central API client — always calls the real FastAPI backend.

import { getItem, STORAGE_KEYS } from './storage.js';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

function authHeader() {
  const session = getItem(STORAGE_KEYS.SESSION);
  if (!session?.sessionToken) return {};
  return { Authorization: `Bearer ${session.sessionToken}` };
}

async function streamChatViaBackend(message, onEvent) {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeader() },
    body: JSON.stringify({ message }),
  });

  if (!response.ok || !response.body) {
    throw new ApiError(`Chat request failed with status ${response.status}`, response.status);
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) {
      const line = chunk.trim();
      if (!line.startsWith('data:')) continue;
      const jsonStr = line.slice(5).trim();
      if (!jsonStr) continue;
      try { onEvent(JSON.parse(jsonStr)); } catch { /* skip malformed */ }
    }
  }
}

async function request(path, { method = 'GET', body, auth = false } = {}) {
  const response = await fetch(`${BASE_URL}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...(auth ? authHeader() : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  let data = null;
  try { data = await response.json(); } catch { data = null; }

  if (!response.ok) {
    throw new ApiError(data?.detail || `Request failed with status ${response.status}`, response.status);
  }
  return data;
}

export const apiClient = {
  async login(payload) {
    return request('/auth/login', { method: 'POST', body: payload });
  },

  async listParticipants() {
    return request('/meta/participants');
  },

  async listPlans() {
    return request('/meta/plans');
  },

  async getQueue() {
    return request('/queue', { auth: true });
  },

  async approveQueueEntry(entryId, note) {
    return request(`/queue/${entryId}/approve`, { method: 'POST', body: { note }, auth: true });
  },

  async denyQueueEntry(entryId, note) {
    return request(`/queue/${entryId}/deny`, { method: 'POST', body: { note }, auth: true });
  },

  async getQueueEntryDocs(entryId) {
    return request(`/queue/${entryId}/docs`, { auth: true });
  },

  async approveQueueEntryDocs(entryId, note) {
    return request(`/queue/${entryId}/approve-docs`, { method: 'POST', body: { note }, auth: true });
  },

  async getAuditLog() {
    return request('/admin/audit', { auth: true });
  },

  async activateBlackout({ planId, startDate, endDate, reason }) {
    return request('/admin/blackout', {
      method: 'POST',
      auth: true,
      body: { plan_id: planId, start_date: startDate, end_date: endDate, reason },
    });
  },

  async deactivateBlackout({ planId }) {
    return request('/admin/blackout', {
      method: 'POST',
      auth: true,
      body: { plan_id: planId, action: 'deactivate' },
    });
  },

  async getParticipantActivity() {
    return request('/meta/participant/activity', { auth: true });
  },

  async getParticipantDocuments() {
    return request('/documents/participant', { auth: true });
  },

  async resetDemo() {
    return request('/admin/reset', { method: 'POST', auth: true });
  },

  async getParticipantInvestments() {
    return request('/meta/participant/investments', { auth: true });
  },

  async reallocateFunds({ scope, elections }) {
    return request('/transactions/reallocate', {
      method: 'POST',
      auth: true,
      body: { scope, elections },
    });
  },

  async health() {
    return request('/health');
  },

  async streamChat(message, { onEvent } = {}) {
    return streamChatViaBackend(message, onEvent);
  },

  async getPendingTransaction() {
    return request('/transactions/pending', { auth: true });
  },

  async confirmTransaction() {
    return request('/transactions/confirm', { method: 'POST', auth: true });
  },

  async cancelTransaction() {
    return request('/transactions/cancel', { method: 'POST', auth: true });
  },

  async disburseFunds({ routingNumber, accountNumber, accountType, entryId }) {
    const body = {
      routing_number: routingNumber,
      account_number: accountNumber,
      account_type: accountType,
    };
    if (entryId) body.entry_id = entryId;
    return request('/transactions/disburse', { method: 'POST', auth: true, body });
  },

  async getTransactionPending() {
    return request('/transactions/pending', { auth: true });
  },

  async uploadDocument({ queueEntryId, actionType, expenseType, docType, file }) {
    const fd = new FormData();
    fd.append('queue_entry_id', String(queueEntryId));
    fd.append('action_type', actionType);
    fd.append('expense_type', expenseType || '');
    fd.append('doc_type', docType);
    fd.append('file', file);

    const response = await fetch(`${BASE_URL}/documents/upload`, {
      method: 'POST',
      headers: { ...authHeader() },
      body: fd,
    });

    if (!response.ok || !response.body) {
      let detail = `Upload failed: ${response.status}`;
      try { detail = (await response.json()).detail || detail; } catch { /* ignore */ }
      throw new ApiError(detail, response.status);
    }

    // The upload endpoint returns SSE — read the stream and pull out the final
    // "response" event which contains the LLM verification summary.
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let finalContent = null;

    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const chunks = buffer.split('\n\n');
      buffer = chunks.pop() ?? '';
      for (const chunk of chunks) {
        const line = chunk.trim();
        if (!line.startsWith('data:')) continue;
        const jsonStr = line.slice(5).trim();
        if (!jsonStr) continue;
        try {
          const event = JSON.parse(jsonStr);
          if (event.type === 'response') finalContent = event.content || null;
          if (event.type === 'error') throw new ApiError(event.message || 'Verification failed', 500);
        } catch (e) {
          if (e instanceof ApiError) throw e;
          /* skip malformed chunks */
        }
      }
    }

    return { content: finalContent };
  },
};

export { ApiError };
