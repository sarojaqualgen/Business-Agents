// DOM event names used to signal state changes across components.
// Components fire these with window.dispatchEvent() and listen with
// window.addEventListener() so unrelated pages can refresh without polling.

export const ACCOUNT_UPDATED_EVENT = 'aldergate:account-updated';
export const PLAN_UPDATED_EVENT    = 'aldergate:plan-updated';
export const QUEUE_UPDATED_EVENT   = 'aldergate:queue-updated';
export const AUDIT_UPDATED_EVENT   = 'aldergate:audit-updated';
