# Saga Pattern in Aldergate — Why, What, and Where

---

## What Is the Saga Pattern, Actually?

Saga is a **design pattern**. Not a rollback feature, not an algorithm,
not something specific to microservices. A design pattern is a reusable
solution to a recurring problem in software design.

**It was invented in 1987** by Hector Garcia-Molina and Kenneth Salem for
long-lived database transactions — way before microservices existed. The
name "saga" comes from the idea of a long story made up of multiple
chapters, where each chapter can be undone.

It became popular again in the 2010s because microservices made the problem
much more common — but the pattern itself is not tied to microservices.

---

### The Core Problem Saga Solves

In a normal database, if three operations fail halfway:

```
BEGIN
  UPDATE accounts SET balance = balance - 5000
  INSERT INTO transactions ...
  UPDATE queue SET status = 'done'
ROLLBACK   ← database undoes all three atomically. Clean.
```

But what if your three operations live in different places?

```
Operation 1 → Python set in memory      (token store)
Operation 2 → Python dict in memory     (participant state)
Operation 3 → JSON file on disk         (queue entry)
```

There is no single ROLLBACK that covers all three. They are three separate
storage mechanisms. If Operation 2 fails, Operation 1 already happened and
there is no automatic undo.

**Saga's answer:** For every forward step that has a side effect, you write
a compensating action — a specific piece of code that logically reverses
that side effect. If a later step fails, you run the compensating actions
for all earlier steps in reverse order.

```
Step 1 forward:      consume token → _consumed_tokens.add(jti)
Step 1 compensate:   unconsume token → _consumed_tokens.discard(jti)

Step 2 forward:      apply override → participant state updated
Step 2 compensate:   not needed if Step 2 itself is the one that fails
                     (we handle its failure with try/except before any
                     irreversible side effect happens)

Step 3 forward:      finalize entry → status = "approved"
Step 3 compensate:   not needed — we only run Step 3 after Steps 1 and 2
                     have fully succeeded
```

---

### Is It Rollback?

Rollback is a database primitive — one instruction that atomically undoes
a set of changes that were part of the same database transaction.

Saga is a pattern built on top of application code. It achieves the same
goal (getting the system back to a consistent state) but through explicit
compensating actions written by the developer, not through a database
engine.

Rollback = one instruction, handled by the database.
Saga = you write the undo logic yourself, step by step.

---

### Is It a Microservices Thing?

No. Saga is used heavily in microservices because each service has its own
database and you literally cannot do a cross-service ROLLBACK. But the
pattern applies anywhere you have multiple sequential operations that
cannot share one atomic transaction — including a single Python process
with multiple storage mechanisms, which is exactly our situation.

---

### Two Types of Saga

**Choreography** — each step emits an event, the next step listens for it
and reacts. No central controller. Used in event-driven systems.

**Orchestration** — one central piece of code calls each step in order and
decides what compensating actions to run on failure. Used when one function
coordinates the whole flow.

We use **orchestration**. The `disburse_transaction()` function in
`api/routes/transactions.py` is the orchestrator — it calls each step,
checks the result, and runs compensating actions if needed.

---

## The Problem We Had (Before This Fix)

A participant submitted a hardship withdrawal request. Here is what happened step by step:

```
1. Participant typed "I need $5,000 for medical expenses" in chat
2. FAP ran 12 ERISA rules — all passed
3. FAP issued a JWT token (valid for 5 minutes at the time)
4. The token was stored in the review queue entry
   → entry status: "pending"
5. Sponsor logged in — but it took 30 minutes to review
6. Sponsor approved the request
   → entry status: "approved_awaiting_bank_details"
   (this means: sponsor said yes, now waiting for participant's bank account details)
7. Participant called POST /transactions/disburse with routing number + account number
8. The system tried to use the stored FAP token to execute the transaction
9. Token was EXPIRED (issued 30+ minutes ago, had 5-min TTL at the time)
   → ExecuteTransactionTool._run() returned {"error": "Token has expired."}
10. BUT — finalize_disbursed() had already run before we checked that error
```

What does `finalize_disbursed()` do?

```python
# data/review_queue.py
def finalize_disbursed(entry_id):
    entry.status = "approved"   ← marks the queue entry as fully done
    _save()                     ← writes this to review_queue_state.json on disk
```

It marks the queue entry as completely finished — as if the money had moved.
The status goes from `approved_awaiting_bank_details` to `approved` and that
is written to disk immediately.

The old code in `api/routes/transactions.py` looked like this:

```python
# OLD CODE — BROKEN ORDER

raw = tool._run(...)           # ← Step A: execute transaction (FAILED — token expired)
finalize_disbursed(entry_id)   # ← Step B: mark entry as done   (RAN ANYWAY — BUG)

try:
    result = json.loads(raw)
except:
    result = {"status": "unknown"}

if "error" in result:          # ← Step C: error check (TOO LATE — entry already finalized)
    raise HTTPException(400, result["error"])
```

`finalize_disbursed` was on line 238. The error check was on line 265.
The function that marks the entry as done ran BEFORE the check that
asks whether it actually succeeded.

```
11. Entry status → "approved" written to disk
    (disk says: done. reality: nothing happened.)
12. Error check fires → raises 400 "Token has expired"
    (but finalize_disbursed already ran — that cannot be undone)
13. Participant tried again with same bank details
    → "Entry is not awaiting bank details (status: approved)"
    → STUCK. No retry possible.
```

The participant was locked out. The money never moved. The queue entry said
`approved` on disk. No way to recover without manually editing the JSON file.
**We had no rollback.**

---

## A Second Problem

Even if we fixed the `finalize_disbursed` ordering, there was still this:

```
1. validate_token() runs — marks token as consumed (single-use, now dead)
2. apply_investment_override() runs — throws an exception
3. Token is dead. Override was not applied. No way to retry.
   Participant has to go back to /chat and start over.
```

Step 1 and Step 2 are two separate operations. If Step 2 fails, Step 1
cannot be "undone" by a simple database ROLLBACK — because the token store
is a Python set in memory, not a database row. We needed a different mechanism.

---

## What Is the Saga Pattern?

In a normal database, if something fails mid-way you call ROLLBACK and
everything goes back to how it was — the database handles it for you.

But in real applications, not everything is inside one database transaction.
You have:
- A JWT token issued and stored
- A Python dict updated
- A JSON file written
- (Phase 6) A PostgreSQL row written

These cannot all be wrapped in a single ROLLBACK. They happen in different
places in different systems.

**The Saga pattern solves this.**

Instead of one ROLLBACK, each step that causes a side effect also has a
**compensating action** — a specific piece of code that undoes exactly
that side effect if something goes wrong later.

Simple analogy:

```
You book a flight (Step 1 — side effect: seat reserved)
You book a hotel (Step 2 — side effect: room reserved)
Hotel booking fails.

Without saga:  flight seat is still reserved. You are stuck paying for a
               flight to nowhere.

With saga:     the compensating action for Step 1 is "cancel the flight."
               When Step 2 fails, the system automatically cancels the flight.
               You are back to where you started. No stuck state.
```

In our system:

```
FAP issues token (Step 1 — side effect: token exists and is valid)
Token is consumed (Step 2 — side effect: token is now single-use-dead)
Override is applied (Step 3 — side effect: in-memory state updated)

If Step 3 fails:
  Compensating action for Step 2: un-consume the token (make it valid again)
  Now the participant can retry. No stuck state.
```

---

## What We Built (The Fix)

### Fix 1 — Re-issue token at approval time (`data/review_queue.py`)

**Problem:** Token issued during chat has a TTL. Sponsor review takes hours.
Token is expired by the time participant tries to disburse.

**Fix:** When the sponsor approves, `approve_awaiting_bank()` discards the
old token and re-issues a brand new one. The participant now has a fresh
window from the moment of approval — not from when they originally asked.

```
Before fix:
  Participant submits hardship → token issued (5-min TTL starts)
  Sponsor reviews 30 minutes later → approves
  Participant tries to disburse → token expired → stuck

After fix:
  Participant submits hardship → token issued (doesn't matter)
  Sponsor approves → OLD token discarded, NEW token issued (24-hr TTL starts NOW)
  Participant tries to disburse → token valid → success
```

Code: `data/review_queue.py` → `approve_awaiting_bank()` — re-issues token
before setting status to `approved_awaiting_bank_details`.

---

### Fix 2 — Move finalize/clear to AFTER the error check (`api/routes/transactions.py`)

**Problem:** `finalize_disbursed()` and `_clear_disbursement_pending()` were
called before checking if execution actually succeeded. A failed execution
still marked the entry as done.

**Before:**
```
tool._run(...)          ← execution (may fail)
finalize_disbursed()    ← called regardless — BUG
check for error         ← too late
```

**After:**
```
tool._run(...)          ← execution (may fail)
check for error         ← if error: raise 400 immediately, stop here
finalize_disbursed()    ← only reached if execution succeeded — FIXED
```

Code: `api/routes/transactions.py` lines 258-270.

---

### Fix 3 — Un-consume token on override failure (`crew/tools/paap_tools.py` + `agents/fap/tokens.py`)

**Problem:** Token is consumed (made single-use-dead) before the in-memory
override runs. If the override throws, token is dead, state unchanged, no retry.

**Fix (the saga compensating action):**

```python
# tokens.py — new function
def unconsume_token(token_str):
    # decode the JWT to get its unique ID (jti)
    # remove that ID from the consumed set
    # token is valid again
    _consumed_tokens.discard(jti)
```

```python
# paap_tools.py — wrap the override
try:
    apply_investment_override(...)   # or apply_deferral_override(...)
except Exception as exc:
    unconsume_token(fap_token)       # COMPENSATING ACTION — undo token consumption
    return {"error": "rolled back, retry is safe"}
```

If the override fails, the compensating action fires: the token is
un-consumed, the queue entry is NOT finalized (because the error check in
transactions.py stops execution before finalize_disbursed), and the
participant can call `/transactions/disburse` again. The system is back
to exactly where it was before the failed attempt.

---

## The Full Picture — Before and After

```
BEFORE (no rollback):

  /transactions/disburse called
    │
    ├─ token consumed ──────────────────────────────── (no going back)
    ├─ finalize_disbursed() ────────────────────────── (entry marked done)
    ├─ override ran / failed ── doesn't matter, too late
    └─ if failure: participant is STUCK
                  entry says "approved", nothing executed, token dead

AFTER (saga rollback):

  /transactions/disburse called
    │
    ├─ validate routing/account numbers
    │   └─ fail → 400, nothing touched, retry freely
    │
    ├─ validate token (check signature, expiry, action, payload hash)
    │   └─ fail → 400, token NOT consumed, retry freely
    │
    ├─ token consumed
    │   └─ if override fails immediately after:
    │       unconsume_token()  ← COMPENSATING ACTION
    │       return error
    │       finalize_disbursed() never called  ← entry stays awaiting
    │       participant retries — token valid, entry valid
    │
    ├─ override applied (success)
    ├─ error check — no error
    └─ finalize_disbursed() ← entry marked done (only here, on success)
```

---

## Summary — Three Fixes, One Goal

| Fix | Where | What it does |
|---|---|---|
| Re-issue token on sponsor approval | `data/review_queue.py` | Participant's clock starts from approval, not from chat |
| Move finalize/clear after error check | `api/routes/transactions.py` | Entry only marked done when execution actually succeeded |
| `unconsume_token` on override failure | `agents/fap/tokens.py` + `crew/tools/paap_tools.py` | Token made valid again if override throws after consumption |

All three fixes together mean: **if any step in the transaction fails, the
system goes back to the last stable state and the participant can retry without
losing their place in the flow.**

---

## Phase 6 — PostgreSQL

When real database writes land in Phase 6, the saga gets one more step:

```
Token consumed → PostgreSQL UPDATE runs → COMMIT

If UPDATE or COMMIT fails:
  Compensating action 1: ROLLBACK the database transaction
  Compensating action 2: unconsume_token() — token valid again
  Participant retries — same token, same entry — picks up where they left off
```

We will also add an **idempotency key** to every INSERT/UPDATE — a unique ID
built from (participant_id + action + payload hash). If a retry comes in with
the same key, the database returns success without double-applying the write.
This protects against the case where the write succeeded but the response was
lost (network timeout between DB COMMIT and HTTP response).
