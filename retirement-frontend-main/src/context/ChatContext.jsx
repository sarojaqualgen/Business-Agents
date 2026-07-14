import React, { createContext, useContext, useEffect, useMemo, useReducer } from 'react';
import { useAuth } from './AuthContext.jsx';
import { getItem, setItem, STORAGE_KEYS } from '../lib/storage.js';

const ChatContext = createContext(null);

function emptyState() {
  return { messages: [], pendingTransaction: null };
}

function reducer(state, action) {
  switch (action.type) {
    case 'HYDRATE':
      return action.payload;

    case 'ADD_USER_MESSAGE':
      return {
        ...state,
        messages: [
          ...state.messages,
          { id: action.payload.id, role: 'user', text: action.payload.text, createdAt: Date.now() },
        ],
      };

    case 'ADD_ASSISTANT_PLACEHOLDER':
      return {
        ...state,
        messages: [
          ...state.messages,
          {
            id: action.payload.id,
            role: 'assistant',
            text: '',
            steps: [],
            isStreaming: true,
            autonomy: null,
            transaction: null,
            intent: null,
            isError: false,
            createdAt: Date.now(),
          },
        ],
      };

    case 'APPEND_TRACE_STEP':
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.payload.id ? { ...m, steps: [...m.steps, action.payload.step] } : m,
        ),
      };

    case 'COMPLETE_ASSISTANT_MESSAGE':
      return {
        ...state,
        messages: state.messages.map((m) =>
          m.id === action.payload.id
            ? {
                ...m,
                text: action.payload.text,
                autonomy: action.payload.autonomy,
                transaction: action.payload.transaction,
                intent: action.payload.intent ?? m.intent,
                isError: Boolean(action.payload.isError),
                isStreaming: false,
              }
            : m,
        ),
      };

    case 'SET_MESSAGE_INTENT':
      return {
        ...state,
        messages: state.messages.map((m) => (m.id === action.payload.id ? { ...m, intent: action.payload.intent } : m)),
      };

    case 'SET_PENDING_TRANSACTION':
      return { ...state, pendingTransaction: action.payload };

    case 'RESOLVE_PENDING_TRANSACTION': {
      const resolvedNote = {
        id: `system-${Date.now()}`,
        role: 'system',
        text: action.payload.message,
        status: action.payload.status,
        createdAt: Date.now(),
      };
      return { ...state, pendingTransaction: null, messages: [...state.messages, resolvedNote] };
    }

    case 'RESET':
      return emptyState();

    default:
      return state;
  }
}

/**
 * Owns the participant's chat transcript and any transaction awaiting
 * confirmation. Scoped per `participantId` and persisted to localStorage so
 * a refresh — or switching back to this participant later — restores the
 * conversation exactly where it left off.
 */
export function ChatProvider({ children }) {
  const { principal } = useAuth();
  const participantId = principal?.participantId || null;
  const storageKey = participantId ? STORAGE_KEYS.chatHistory(participantId) : null;

  const [state, dispatch] = useReducer(reducer, undefined, () =>
    storageKey ? getItem(storageKey, emptyState()) : emptyState(),
  );

  // Re-hydrate whenever the active participant changes (role switch,
  // re-login as someone else) so conversations never bleed into each other.
  useEffect(() => {
    dispatch({ type: 'HYDRATE', payload: storageKey ? getItem(storageKey, emptyState()) : emptyState() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storageKey]);

  useEffect(() => {
    if (!storageKey) return;
    setItem(storageKey, state);
  }, [storageKey, state]);

  const value = useMemo(() => ({ state, dispatch, participantId }), [state, participantId]);

  return <ChatContext.Provider value={value}>{children}</ChatContext.Provider>;
}

export function useChatContext() {
  const ctx = useContext(ChatContext);
  if (!ctx) throw new Error('useChatContext must be used within a ChatProvider');
  return ctx;
}
