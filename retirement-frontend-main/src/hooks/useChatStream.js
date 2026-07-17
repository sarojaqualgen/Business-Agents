import { useCallback, useState } from 'react';
import { useChatContext } from '../context/ChatContext.jsx';
import { apiClient } from '../lib/apiClient.js';
import { ACCOUNT_UPDATED_EVENT } from '../lib/events.js';
import { useAuth } from '../context/AuthContext.jsx';

const TRACE_EVENT_TYPES = new Set(['agent_start', 'tool_use', 'tool_result', 'step_done']);

// These action types require the participant to upload supporting documents
// before the plan sponsor can approve the queued review entry.
const UPLOAD_REQUIRED_TYPES = new Set(['hardship_distribution', 'qdro']);

let uid = 0;
function nextId(prefix) {
  uid += 1;
  return `${prefix}-${Date.now()}-${uid}`;
}

/**
 * Drives the participant chat: sends a message through apiClient.streamChat,
 * folding each streamed event into the shared ChatContext transcript, and
 * exposes confirm/cancel for any transaction left pending confirmation.
 */
function fireAccountRefresh(participantId) {
  if (typeof window !== 'undefined' && participantId) {
    window.dispatchEvent(new CustomEvent(ACCOUNT_UPDATED_EVENT, { detail: { participantId } }));
  }
}

export function useChatStream() {
  const { state, dispatch } = useChatContext();
  const { principal } = useAuth();
  const [isStreaming, setIsStreaming] = useState(false);
  const [isResolving, setIsResolving] = useState(false);
  // null | { entryId, actionType, expenseType } — shown after human_review responses
  // that require supporting docs (hardship_distribution, qdro).
  const [pendingUpload, setPendingUpload] = useState(null);
  // null | { action } — shown after confirming a supervised loan (awaiting_bank_details)
  const [pendingBankDetails, setPendingBankDetails] = useState(null);

  const clearChat = useCallback(() => dispatch({ type: 'RESET' }), [dispatch]);
  const dismissUpload = useCallback(() => setPendingUpload(null), []);

  // Fast path — Haiku classification + direct PAAP/PLAP calls, no CrewAI.
  // Builds history from the current transcript so Haiku has multi-turn context.
  const sendFastMessage = useCallback(
    async (rawText) => {
      const text = (rawText || '').trim();
      if (!text || isStreaming) return;

      dispatch({ type: 'ADD_USER_MESSAGE', payload: { id: nextId('user'), text } });

      const assistantId = nextId('assistant');
      dispatch({ type: 'ADD_ASSISTANT_PLACEHOLDER', payload: { id: assistantId } });
      setIsStreaming(true);

      // Build history for Haiku context (last 6 messages, user + assistant only)
      const history = state.messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-6)
        .map((m) => ({ role: m.role, content: m.text || '' }));

      try {
        const res = await apiClient.chatFast(text, history);
        dispatch({
          type: 'COMPLETE_ASSISTANT_MESSAGE',
          payload: {
            id:          assistantId,
            text:        res.reply || '',
            autonomy:    res.autonomy || null,
            transaction: null,   // fast path never uses TransactionSummaryCard
            intent:      res.intent || null,
            isError:     false,
          },
        });
        if (res.autonomy === 'supervised' && res.transaction) {
          const tx = res.transaction;
          dispatch({
            type: 'SET_PENDING_TRANSACTION',
            payload: {
              type:     tx.action,
              amount:   tx.amount,
              termYears: tx.repayment_years,
              purpose:  tx.purpose,
              status:   'pending_confirmation',
            },
          });
        }
      } catch (err) {
        dispatch({
          type: 'COMPLETE_ASSISTANT_MESSAGE',
          payload: {
            id:          assistantId,
            text:        err.message || 'Something went wrong. Please try again.',
            autonomy:    null,
            transaction: null,
            isError:     true,
          },
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [dispatch, isStreaming, state.messages],
  );

  const sendMessage = useCallback(
    async (rawText) => {
      const text = (rawText || '').trim();
      if (!text || isStreaming) return;

      dispatch({ type: 'ADD_USER_MESSAGE', payload: { id: nextId('user'), text } });

      const assistantId = nextId('assistant');
      dispatch({ type: 'ADD_ASSISTANT_PLACEHOLDER', payload: { id: assistantId } });
      setIsStreaming(true);

      try {
        await apiClient.streamChat(text, {
          onEvent: (event) => {
            if (event.type === 'agent_start' && event.intent) {
              dispatch({ type: 'SET_MESSAGE_INTENT', payload: { id: assistantId, intent: event.intent } });
            }

            if (event.type === 'heartbeat') return; // keep-alive ping — no state change

            if (TRACE_EVENT_TYPES.has(event.type)) {
              // Normalise to { agent, label } for both the mock engine (which
              // sends a pre-formatted `label` string) and the real backend
              // (which sends structured fields like task/tool/args/preview/summary).
              let agent = event.agent;
              let label = event.label; // mock path — already a formatted string
              if (!label) {
                // Real backend path — build the same display strings the mock produces
                switch (event.type) {
                  case 'agent_start':
                    label = event.task || '';
                    break;
                  case 'tool_use':
                    agent = agent || event.tool || 'Tool';
                    label = `→ ${event.tool || ''}(${(event.args || '').slice(0, 80)})`;
                    break;
                  case 'tool_result':
                    agent = agent || event.tool || 'Tool';
                    label = `← ${(event.preview || '').slice(0, 80)}`;
                    break;
                  case 'step_done':
                    label = (event.summary || '').slice(0, 100);
                    break;
                  default:
                    label = '';
                }
              }
              dispatch({
                type: 'APPEND_TRACE_STEP',
                payload: { id: assistantId, step: { agent: agent || event.type, label: label || '' } },
              });
              return;
            }

            if (event.type === 'response') {
              // Backend sends `content`; mock sends `text` — accept both.
              const responseText = event.content || event.text || '';
              dispatch({
                type: 'COMPLETE_ASSISTANT_MESSAGE',
                payload: {
                  id: assistantId,
                  text: responseText,
                  autonomy: event.autonomy || null,
                  transaction: event.transaction || null,
                  intent: event.intent || null,
                },
              });
              if (event.autonomy === 'supervised' && event.transaction) {
                dispatch({ type: 'SET_PENDING_TRANSACTION', payload: event.transaction });
              }
              // Prompt document upload after hardship/QDRO queued for review.
              if (event.autonomy === 'human_review' && event.transaction) {
                const tx = event.transaction;
                const actionType = tx.action || tx.type || '';
                if (UPLOAD_REQUIRED_TYPES.has(actionType)) {
                  setPendingUpload({
                    entryId: tx.entry_id ?? tx.entryId ?? null,
                    actionType,
                    expenseType: tx.expense_type || tx.reason || null,
                  });
                }
              }
              return;
            }

            if (event.type === 'error') {
              dispatch({
                type: 'COMPLETE_ASSISTANT_MESSAGE',
                payload: {
                  id: assistantId,
                  text: event.message || 'Something went wrong. Please try again.',
                  autonomy: null,
                  transaction: null,
                  isError: true,
                },
              });
            }
          },
        });
      } catch (err) {
        dispatch({
          type: 'COMPLETE_ASSISTANT_MESSAGE',
          payload: {
            id: assistantId,
            text: err.message || 'Something went wrong. Please try again.',
            autonomy: null,
            transaction: null,
            isError: true,
          },
        });
      } finally {
        setIsStreaming(false);
      }
    },
    [dispatch, isStreaming],
  );

  const confirmTransaction = useCallback(async () => {
    if (!state.pendingTransaction || isResolving) return;
    setIsResolving(true);
    try {
      const res = await apiClient.confirmTransaction();
      dispatch({ type: 'RESOLVE_PENDING_TRANSACTION', payload: { status: res.status, message: res.message } });
      if (res.status === 'awaiting_bank_details') {
        setPendingBankDetails({ action: res.action });
      } else {
        // Non-disbursement (e.g. deferral change) executed immediately — refresh dashboard
        fireAccountRefresh(principal?.participantId);
      }
    } finally {
      setIsResolving(false);
    }
  }, [state.pendingTransaction, isResolving, dispatch]);

  const cancelTransaction = useCallback(async () => {
    if (!state.pendingTransaction || isResolving) return;
    setIsResolving(true);
    try {
      const res = await apiClient.cancelTransaction();
      dispatch({ type: 'RESOLVE_PENDING_TRANSACTION', payload: { status: res.status, message: res.message } });
    } finally {
      setIsResolving(false);
    }
  }, [state.pendingTransaction, isResolving, dispatch]);

  const submitBankDetails = useCallback(async ({ routingNumber, accountNumber, accountType }) => {
    setIsResolving(true);
    try {
      const res = await apiClient.disburseFunds({ routingNumber, accountNumber, accountType });
      const msg = res.disbursement
        ? `Loan disbursement initiated — funds arrive in ${res.disbursement.estimated_arrival} to account ending in ${res.disbursement.account_last4}.`
        : res.message || 'Disbursement processed.';
      dispatch({ type: 'RESOLVE_PENDING_TRANSACTION', payload: { status: 'executed', message: msg } });
      setPendingBankDetails(null);
      fireAccountRefresh(principal?.participantId);
    } catch (err) {
      dispatch({
        type: 'RESOLVE_PENDING_TRANSACTION',
        payload: { status: 'error', message: err.message || 'Disbursement failed.' },
      });
      setPendingBankDetails(null);
    } finally {
      setIsResolving(false);
    }
  }, [dispatch]);

  const dismissBankDetails = useCallback(() => setPendingBankDetails(null), []);

  return {
    messages: state.messages,
    pendingTransaction: state.pendingTransaction,
    pendingUpload,
    pendingBankDetails,
    isStreaming,
    isResolving,
    sendMessage,
    sendFastMessage,
    confirmTransaction,
    cancelTransaction,
    clearChat,
    dismissUpload,
    submitBankDetails,
    dismissBankDetails,
  };
}
