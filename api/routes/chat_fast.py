"""
Fast chat endpoint — Haiku intent classification + direct PAAP/PLAP calls.
No CrewAI, no SSE. Returns JSON in 3-5 seconds.

POST /chat/fast
Body: { "message": str, "history": [{ "role": "user"|"assistant", "content": str }] }
Returns: { "reply": str, "autonomy": str|null, "transaction": dict|null, "missing": list|null }

Supported intents:
  loan_initiation   — classify params, call PAAP (PAAP calls PLAP → FAP internally), set supervised pending
  data_question     — hit PAAP/PLAP read endpoint, Haiku formats the data
  conceptual_question — Haiku answers directly using FAP rules context
  unknown           — polite redirect
"""

import json
import re
import anthropic
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import SessionToken, get_session
from agents.paap.agent import (
    ParticipantNotFound,
    UnauthorizedByFAP,
    execute as paap_execute,
    get_participant_plan_id,
    get_rmd_info,
)
from api.pending import set_supervised_pending
from agents.fap.context import FAP_RULES_TEXT

router = APIRouter()
_client = anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Haiku helpers
# ---------------------------------------------------------------------------

_CLASSIFY_SYSTEM = """You are a 401k plan assistant intent classifier.
A single user message can contain MULTIPLE things at once — a question AND a transaction request.
Extract ALL of them. Return ONLY valid JSON — no explanation, no markdown.

Supported transaction intents:
  loan_initiation, hardship_distribution, in_service_distribution,
  separation_distribution, rmd, qdro, beneficiary_update

  loan_initiation required params: amount (dollars), repayment_years (integer), purpose ("general" or "primary_residence")
  IMPORTANT: Extract whatever number the user gives for repayment_years — do NOT validate it. Even if
  they say "6 years" or "10 years", extract it. Compliance rules run separately and will reject if invalid.

  hardship_distribution required params: amount (dollars), qualifying_expense_type (string — the user's stated reason), taxable_event_acknowledged (boolean)
  Classify ANY request where someone wants money from their 401k for a personal financial reason as hardship_distribution,
  even if the reason is not a valid IRS category (e.g. "vacation", "car repairs", "credit card debt"). Extract the
  qualifying_expense_type as whatever the user says — do NOT validate it. Compliance rules run separately and will
  reject invalid categories.
  Map common user language to IRS standard terms where applicable:
    "medical bills/expenses/hospital" → "medical"
    "rent/eviction" → "prevent_eviction"
    "school/college/tuition" → "tuition"
    "funeral/burial" → "funeral"
    "buy a home/house/primary residence" → "primary_home_purchase"
    "disaster/FEMA/hurricane/flood" → "FEMA_disaster"
    "property damage/casualty loss" → "casualty_loss"
  If the user's reason doesn't match any of the above, pass it through as-is (e.g. "vacation", "car_repairs").
  taxable_event_acknowledged: set to true if the user says yes/I understand/I acknowledge/proceed/confirmed/ok/sure
  in response to a tax warning. If not yet acknowledged, add "taxable_event_acknowledged" to missing[].

  in_service_distribution required params: amount (dollars), taxable_event_acknowledged (boolean)
  For participants still employed, age 59½ or older. Map: "in-service withdrawal", "take money while still working",
  "withdraw at 59½", "active employee withdrawal", "while I'm still working", "while still employed",
  "I'm still at my job", "I'm still employed" → in_service_distribution.
  taxable_event_acknowledged: set to true if the user says yes/I understand/I acknowledge/proceed/confirmed/ok/sure
  in response to a tax warning. If not yet acknowledged, add "taxable_event_acknowledged" to missing[].

  separation_distribution required params: amount (dollars), taxable_event_acknowledged (boolean)
  For participants who have left employment (terminated, retired). Map: "I quit/left my job and want my money",
  "separation distribution", "termination distribution", "retire and take my money",
  "I was terminated", "I'm no longer employed", "I left my job" → separation_distribution.
  taxable_event_acknowledged: set to true if the user says yes/I understand/I acknowledge/proceed/confirmed/ok/sure
  in response to a tax warning. If not yet acknowledged, add "taxable_event_acknowledged" to missing[].

  CRITICAL RULE — in_service vs separation:
  If the user explicitly says they are CURRENTLY WORKING ("still working", "still employed", "while I'm working",
  "I'm still at my job") → ALWAYS classify as in_service_distribution, never separation_distribution.
  If the user explicitly says they have LEFT ("quit", "left my job", "was terminated", "I'm no longer working",
  "I retired", "I separated") → ALWAYS classify as separation_distribution, never in_service_distribution.
  Do NOT infer employment status from conversation history — classify based only on what the current message says.
  Do NOT carry over taxable_event_acknowledged from a prior intent if the current intent is different.

  rmd required params: taxable_event_acknowledged (boolean)
  Map: "RMD", "required minimum distribution", "take my required distribution", "I have to take money out this year",
  "mandatory withdrawal" → rmd.
  taxable_event_acknowledged: set to true if the user says yes/I understand/I acknowledge/proceed/confirmed/ok/sure
  in response to a tax warning. If not yet acknowledged, add "taxable_event_acknowledged" to missing[].

  qdro required params: alternate_payee_name (string), transfer_pct (integer 1-100)
  Map: "QDRO", "qualified domestic relations order", "divorce settlement transfer", "transfer to ex-spouse",
  "court-ordered transfer", "divorce decree" → qdro.

  beneficiary_update required params: beneficiary_name (string), relationship (one of: "spouse", "child", "parent", "sibling", "estate", "other")
  Optional: allocation_pct (integer, defaults to 100 if single beneficiary)
  Map: "change beneficiary", "update beneficiary", "add beneficiary", "remove beneficiary",
  "who gets my money", "designate beneficiary" → beneficiary_update.

  In multi-turn conversations, carry over params already collected from history into the current params.
  EXCEPTION — taxable_event_acknowledged is NEVER carried over from history.
  Set taxable_event_acknowledged=true ONLY when the CURRENT user message (not history) explicitly contains
  acknowledgment language: "yes", "i acknowledge", "i understand", "proceed", "i know", "ok", "sure", "confirmed".
  If the current message does not contain such language, always add "taxable_event_acknowledged" to missing[]
  regardless of what appears in prior history. Every new transaction request requires a fresh disclosure.

data_question_type options:
  balance           — total and vested balance
  loan_headroom     — how much the participant can borrow (IRC §72(p) cap)
  vesting           — vesting percentage and years of service
  rmd               — required minimum distribution info
  distribution_options — what withdrawals are available
  plan_capabilities — what this plan allows (loans, hardship, etc.)
  fund_lineup       — all funds available in the plan (NOT personal holdings)
  my_investments    — the participant's OWN current investment elections/holdings

IMPORTANT: "what am I invested in", "my current funds", "my holdings", "where is my money" → my_investments
           "what funds are available", "what can I invest in" → fund_lineup

conceptual_question: any question about how 401k rules, ERISA, vesting, RMDs, or plan terms work.
"""

_CLASSIFY_PROMPT = """Conversation history (last few turns):
{history}

User's latest message: "{message}"

Return JSON exactly like this (all fields required, use null if not present):
{{
  "transaction": {{
    "intent": "loan_initiation" | "hardship_distribution" | "in_service_distribution" | "separation_distribution" | "rmd" | "qdro" | "beneficiary_update" | null,
    "params": {{}},
    "missing": []
  }},
  "data_question_type": null,
  "conceptual_topic": null
}}

Examples:
- "What is my balance and take a $5000 loan for 3 years general"
  → transaction.intent=loan_initiation, params={{amount:5000,repayment_years:3,purpose:general}}, data_question_type=balance
- "How much can I borrow?"
  → transaction.intent=null, data_question_type=loan_headroom
- "What is vesting?"
  → transaction.intent=null, data_question_type=null, conceptual_topic="vesting"
- "I want a loan"
  → transaction.intent=loan_initiation, missing=[amount,repayment_years,purpose]
- "I need $3000 for medical bills"
  → transaction.intent=hardship_distribution, params={{amount:3000,qualifying_expense_type:medical}}, missing=[]
- "I need a hardship withdrawal"
  → transaction.intent=hardship_distribution, params={{}}, missing=[amount,qualifying_expense_type]
- "I need $3000 for a vacation"
  → transaction.intent=hardship_distribution, params={{amount:3000,qualifying_expense_type:vacation}}, missing=[]
- "I need $1000 for car repairs"
  → transaction.intent=hardship_distribution, params={{amount:1000,qualifying_expense_type:car_repairs}}, missing=[]
- "I want to take $5000 out, I'm 60 and still working"
  → transaction.intent=in_service_distribution, params={{amount:5000}}, missing=["taxable_event_acknowledged"]
- "I want to take $10,000 out while I'm still working — I'm 62"
  → transaction.intent=in_service_distribution, params={{amount:10000}}, missing=["taxable_event_acknowledged"]
- "I left my job, I want to take $20000 out"
  → transaction.intent=separation_distribution, params={{amount:20000}}, missing=["taxable_event_acknowledged"]
- "I need to take my RMD this year"
  → transaction.intent=rmd, params={{}}, missing=[]
- "I need to set up a QDRO, 50% to my ex-wife Jane Smith"
  → transaction.intent=qdro, params={{alternate_payee_name:"Jane Smith",transfer_pct:50}}, missing=[]
- "Change my beneficiary to my daughter Maria, she's my child"
  → transaction.intent=beneficiary_update, params={{beneficiary_name:"Maria",relationship:"child"}}, missing=[]
- "I need $5000 for medical bills" (no prior acknowledgment in history)
  → transaction.intent=hardship_distribution, params={{amount:5000,qualifying_expense_type:"medical"}}, missing=["taxable_event_acknowledged"]
- "yes I understand" or "yes proceed" (history shows pending hardship with amount+expense_type already collected)
  → transaction.intent=hardship_distribution, params={{amount:<from history>,qualifying_expense_type:<from history>,taxable_event_acknowledged:true}}, missing=[]
- "I want to take $10,000 out, I'm still working and I'm 62" (no prior acknowledgment)
  → transaction.intent=in_service_distribution, params={{amount:10000}}, missing=["taxable_event_acknowledged"]
"""


def _classify(message: str, history: list[dict]) -> dict:
    history_text = "\n".join(
        f"{m.get('role', 'user')}: {m.get('content', '')}"
        for m in history[-6:]
    ) or "(no prior context)"

    resp = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=_CLASSIFY_SYSTEM,
        messages=[{
            "role": "user",
            "content": _CLASSIFY_PROMPT.format(history=history_text, message=message),
        }],
    )
    raw = resp.content[0].text.strip()

    # Strip markdown code fences Haiku sometimes wraps around JSON
    raw = re.sub(r"^```(?:json)?\s*", "", raw)
    raw = re.sub(r"\s*```$", "", raw)
    raw = raw.strip()

    # Extract the first {...} block in case there is surrounding text
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        raw = m.group(0)

    try:
        return json.loads(raw)
    except Exception:
        return {"intent": "unknown", "params": {}, "missing": [], "data_question_type": None, "conceptual_topic": None}


def _haiku_reply(
    system_extra: str,
    instruction: str,
    max_tokens: int = 600,
    history: list[dict] | None = None,
) -> str:
    system = (
        f"You are Aldergate, a friendly 401k plan assistant. "
        f"Be concise. Use plain English. No bullet lists unless asked.\n\n"
        f"The 12 compliance rules this plan enforces:\n{FAP_RULES_TEXT}\n\n"
        f"{system_extra}"
    )
    if history:
        messages = [*history[-6:], {"role": "user", "content": instruction}]
    else:
        messages = [{"role": "user", "content": instruction}]

    resp = _client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=system,
        messages=messages,
    )
    return resp.content[0].text.strip()


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class ChatFastRequest(BaseModel):
    message: str
    history: list[dict] = []


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

@router.post("/chat/fast")
def chat_fast(req: ChatFastRequest, session: SessionToken = Depends(get_session)):
    participant_id = session.participant_id
    if not participant_id:
        raise HTTPException(400, "No participant in session.")

    try:
        plan_id = get_participant_plan_id(participant_id)
    except ParticipantNotFound:
        raise HTTPException(404, "Participant not found.")

    # Load participant for context-aware proactive checks (employment status, age, RMD flag)
    _pctx = None
    try:
        from data import db as _db_mod
        _pctx = _db_mod.get_participant(participant_id)
    except Exception:
        pass

    _p_emp_status = getattr(_pctx, "employment_status", None)
    _p_rmd_required = getattr(_pctx, "rmd_required", None)
    _p_age: float | None = None
    if _pctx and _pctx.date_of_birth:
        from datetime import date as _dt_date
        try:
            _dob = _dt_date.fromisoformat(_pctx.date_of_birth[:10])
            _today = _dt_date.today()
            _p_age = (_today - _dob).days / 365.25
        except Exception:
            pass

    classified = _classify(req.message, req.history)       # ← Haiku runs here, returns JSON
    tx_block    = classified.get("transaction") or {}
    tx_intent   = tx_block.get("intent")
    tx_params   = tx_block.get("params") or {}
    tx_missing  = tx_block.get("missing") or []
    dtype       = classified.get("data_question_type")
    ctopic      = classified.get("conceptual_topic")

    # Backend safety net for taxable_event_acknowledged: Haiku may carry over a prior
    # session's ack from conversation history. We require the CURRENT message to contain
    # explicit acknowledgment language — if it doesn't, force ack back into missing[].
    _TAXABLE_ACK_INTENTS = {"hardship_distribution", "in_service_distribution", "separation_distribution", "rmd"}
    _ACK_PHRASES = {"yes", "acknowledge", "understand", "proceed", "confirmed", "i know", "sure", "ok"}
    _current_msg_lower = req.message.lower()
    _has_explicit_ack = any(phrase in _current_msg_lower for phrase in _ACK_PHRASES)

    if (
        tx_intent in _TAXABLE_ACK_INTENTS
        and tx_params.get("taxable_event_acknowledged") is True
        and not _has_explicit_ack
        and "taxable_event_acknowledged" not in tx_missing
    ):
        # Haiku carried ack from history — strip it and require fresh disclosure
        tx_params = {k: v for k, v in tx_params.items() if k != "taxable_event_acknowledged"}
        tx_missing = list(tx_missing) + ["taxable_event_acknowledged"]

    reply_parts = []   # collect answer fragments, join at the end
    autonomy    = None
    transaction = None

    # Signal the frontend to show a confirm/cancel card when taxable ack is needed.
    pending_tax_ack = (
        {"intent": tx_intent, "params": tx_params}
        if tx_intent in _TAXABLE_ACK_INTENTS and "taxable_event_acknowledged" in tx_missing
        else None
    )

    # If the proactive RMD check will fire, suppress the rmd data question — otherwise
    # both handlers run and produce two contradictory paragraphs in the same reply.
    _proactive_rmd = tx_intent == "rmd" and _p_rmd_required is False
    if _proactive_rmd and dtype == "rmd":
        dtype = None

    # ── Data question — fetch real data first so it leads the reply ───────
    if dtype:
        data = {}
        try:
            if dtype in ("balance", "my_investments"):
                from agents.paap.agent import get_participant_summary
                data = get_participant_summary(participant_id)
            elif dtype == "loan_headroom":
                from agents.paap.agent import get_loan_headroom
                data = get_loan_headroom(participant_id)
            elif dtype == "vesting":
                from agents.paap.agent import get_vesting_info
                data = get_vesting_info(participant_id)
            elif dtype == "rmd":
                from agents.paap.agent import get_rmd_info
                data = get_rmd_info(participant_id)
            elif dtype == "distribution_options":
                from agents.paap.agent import get_distribution_options
                data = get_distribution_options(participant_id)
            elif dtype == "plan_capabilities":
                from agents.plap.agent import query_capabilities
                data = query_capabilities(plan_id)
            elif dtype == "fund_lineup":
                from agents.plap.agent import query_fund_lineup
                data = query_fund_lineup(plan_id)
        except Exception:
            data = {}

        focus = (
            "Focus on the investment_elections field — list each fund_id and its allocation_pct as a percentage."
            if dtype == "my_investments"
            else "Answer only the data question part using the data above."
        )
        answer = _haiku_reply(
            system_extra=f"Participant account data:\n{json.dumps(data, indent=2)}",
            instruction=f'{focus} User message: "{req.message}"',
        )
        reply_parts.append(answer)

    # ── Conceptual question ───────────────────────────────────────────────
    if ctopic:
        answer = _haiku_reply(
            system_extra="",
            instruction=f'Answer this 401k / ERISA question in plain English: "{ctopic}"',
            history=req.history,
        )
        reply_parts.append(answer)

    # ── Loan initiation ───────────────────────────────────────────────────
    if tx_intent == "loan_initiation":
        if tx_missing:
            # Ask for one missing param at a time in priority order
            first = tx_missing[0]
            if first == "amount":
                reply_parts.append("How much would you like to borrow?")
            elif first == "repayment_years":
                reply_parts.append("How many years would you like to repay over?")
            elif first == "purpose":
                reply_parts.append("Is this for a general purpose or a primary residence purchase?")
        else:
            try:
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="loan_initiation",
                    payload=tx_params,
                )
            except UnauthorizedByFAP as e:
                denial_reply = _haiku_reply(
                    system_extra=(
                        f"FAP denied a loan request.\n"
                        f"Denial reason: {e.denial_reason}\n"
                        f"Denial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the loan was denied and what the participant can do.",
                )
                reply_parts.append(denial_reply)
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your loan request right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if fap_token:
                    set_supervised_pending(
                        participant_id=participant_id,
                        action="loan_initiation",
                        payload=tx_params,
                        payload_json=json.dumps(tx_params),
                        fap_token=fap_token,
                    )
                amount  = tx_params.get("amount", 0)
                years   = tx_params.get("repayment_years", 5)
                purpose = tx_params.get("purpose", "general")
                loan_reply = _haiku_reply(
                    system_extra="",
                    instruction=(
                        f"A loan of ${float(amount):,.0f} over {years} year(s) ({purpose}) "
                        f"passed all compliance checks. Tell the participant it's ready to confirm "
                        f"in 1 sentence. No technical terms."
                    ),
                )
                reply_parts.append(loan_reply)
                transaction = {
                    "action":          "loan_initiation",
                    "amount":          float(amount),
                    "repayment_years": int(years),
                    "purpose":         purpose,
                }

    # ── Hardship distribution ─────────────────────────────────────────────
    if tx_intent == "hardship_distribution":
        if tx_missing:
            if "amount" in tx_missing:
                reply_parts.append("How much do you need for the hardship distribution?")
            elif "qualifying_expense_type" in tx_missing:
                reply_parts.append(
                    "What is the reason for your hardship? Options: medical expenses, "
                    "tuition, home purchase, eviction prevention, funeral costs, "
                    "casualty loss, or FEMA disaster."
                )
            elif "taxable_event_acknowledged" in tx_missing:
                reply_parts.append(
                    "Before I submit this, please confirm: hardship distributions are subject to "
                    "ordinary income tax. If you are under age 59½, a 10% early withdrawal penalty "
                    "under IRC § 72(t) may also apply. Do you acknowledge this and wish to proceed?"
                )
        else:
            try:
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="hardship_distribution",
                    payload=tx_params,
                )
            except UnauthorizedByFAP as e:
                denial_reply = _haiku_reply(
                    system_extra=(
                        f"FAP denied a hardship distribution request.\n"
                        f"Denial reason: {e.denial_reason}\n"
                        f"Denial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the hardship was denied and what the participant can do.",
                )
                reply_parts.append(denial_reply)
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your hardship request right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]  # always human_review for hardship
                fap_token = result.get("fap_token")

                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="hardship_distribution",
                        payload=tx_params,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    amount      = tx_params.get("amount", 0)
                    expense     = tx_params.get("qualifying_expense_type", "")
                    hardship_reply = _haiku_reply(
                        system_extra="",
                        instruction=(
                            f"A hardship distribution of ${float(amount):,.0f} for '{expense}' "
                            f"passed compliance checks and is now queued for plan sponsor review. "
                            f"Tell the participant: (1) it needs sponsor approval, (2) they must "
                            f"upload supporting documents (e.g. medical bill, eviction notice), "
                            f"(3) they'll be notified when approved. 3 sentences, plain English."
                        ),
                    )
                    reply_parts.append(hardship_reply)
                    transaction = {
                        "action":                  "hardship_distribution",
                        "amount":                  float(amount),
                        "qualifying_expense_type": expense,
                        "entry_id":                entry_id,
                    }

    # ── In-service distribution ───────────────────────────────────────────
    if tx_intent == "in_service_distribution":
        if _p_emp_status == "terminated":
            # Proactive: terminated participants must use separation_distribution instead
            pending_tax_ack = None
            reply_parts.append(_haiku_reply(
                system_extra="",
                instruction=(
                    "Tell the participant directly (use 'you'): in-service distributions are only available to "
                    "active employees age 59½ or older. Since you have already separated from your employer, "
                    "you are not eligible for an in-service distribution. You should request a separation "
                    "distribution instead, which is the correct withdrawal type for former employees. "
                    "2-3 sentences, plain English."
                ),
            ))
        elif _p_age is not None and _p_age < 59.5:
            # Proactive: age requirement not met
            pending_tax_ack = None
            reply_parts.append(_haiku_reply(
                system_extra="",
                instruction=(
                    f"Tell the participant directly (use 'you'): in-service distributions require age 59½ under "
                    f"IRC § 401(a)(36). At {_p_age:.1f} years old, you don't yet meet this requirement. "
                    "A 401k loan may be a good alternative while you're still employed. "
                    "2-3 sentences, plain English."
                ),
            ))
        elif tx_missing:
            if "amount" in tx_missing:
                reply_parts.append("How much would you like to withdraw from your account?")
            elif "taxable_event_acknowledged" in tx_missing:
                reply_parts.append(
                    "Before I submit this, please confirm: in-service distributions are subject to "
                    "ordinary income tax. Since you are age 59½ or older, the 10% early withdrawal "
                    "penalty under IRC § 72(t) does not apply. Do you acknowledge this and wish to proceed?"
                )
        else:
            try:
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="in_service_distribution",
                    payload=tx_params,
                )
            except UnauthorizedByFAP as e:
                reply_parts.append(_haiku_reply(
                    system_extra=(
                        f"FAP denied an in-service distribution request.\n"
                        f"Denial reason: {e.denial_reason}\nDenial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the in-service withdrawal was denied and what the participant can do.",
                ))
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your request right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="in_service_distribution",
                        payload=tx_params,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    amount = tx_params.get("amount", 0)
                    reply_parts.append(_haiku_reply(
                        system_extra="",
                        instruction=(
                            f"An in-service distribution of ${float(amount):,.0f} passed compliance checks "
                            f"and is queued for plan sponsor review. Tell the participant: (1) it needs sponsor "
                            f"approval, (2) they'll be notified when approved. 2 sentences, plain English."
                        ),
                    ))
                    transaction = {"action": "in_service_distribution", "amount": float(amount), "entry_id": entry_id}

    # ── Separation distribution ───────────────────────────────────────────
    if tx_intent == "separation_distribution":
        if _p_emp_status == "active":
            # Proactive: active employees cannot take a separation distribution
            pending_tax_ack = None
            reply_parts.append(_haiku_reply(
                system_extra="",
                instruction=(
                    "Tell the participant directly (use 'you'): separation distributions are only available to "
                    "participants who have permanently left their employer. Based on plan records, you are still "
                    "an active employee and are not yet eligible for this distribution type. While you're still "
                    "employed, alternatives include a 401k loan or, if you are age 59½ or older, an in-service "
                    "distribution. 2-3 sentences, plain English."
                ),
            ))
        elif tx_missing:
            if "amount" in tx_missing:
                reply_parts.append("How much would you like to withdraw from your account?")
            elif "taxable_event_acknowledged" in tx_missing:
                reply_parts.append(
                    "Before I submit this, please confirm: separation distributions are subject to "
                    "ordinary income tax. If you are under age 59½ and no exception applies, "
                    "a 10% early withdrawal penalty under IRC § 72(t) may also apply. "
                    "Do you acknowledge this and wish to proceed?"
                )
        else:
            try:
                # The portal confirms the IRC §402(f) rollover notice was provided —
                # this is a plan-admin obligation, not a participant-entered field.
                sep_payload = {**tx_params, "rollover_402f_notice_confirmed": True}
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="separation_distribution",
                    payload=sep_payload,
                )
            except UnauthorizedByFAP as e:
                reply_parts.append(_haiku_reply(
                    system_extra=(
                        f"FAP denied a separation distribution request.\n"
                        f"Denial reason: {e.denial_reason}\nDenial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the separation distribution was denied and what the participant can do.",
                ))
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your request right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="separation_distribution",
                        payload=sep_payload,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    amount = sep_payload.get("amount", 0)
                    reply_parts.append(_haiku_reply(
                        system_extra="",
                        instruction=(
                            f"A separation distribution of ${float(amount):,.0f} passed compliance checks "
                            f"and is queued for plan sponsor review. Tell the participant it needs sponsor "
                            f"approval and they'll be notified when approved. 2 sentences."
                        ),
                    ))
                    transaction = {"action": "separation_distribution", "amount": float(amount), "entry_id": entry_id}

    # ── RMD ───────────────────────────────────────────────────────────────
    if tx_intent == "rmd":
        if _p_rmd_required is False:
            # Proactive: participant not yet subject to RMDs
            pending_tax_ack = None
            reply_parts.append(_haiku_reply(
                system_extra="",
                instruction=(
                    "Tell the participant directly (use 'you'): based on your account record, you are not yet required "
                    "to take a Required Minimum Distribution. RMDs begin at age 73 under SECURE 2.0 (IRC § 401(a)(9)). "
                    "You'll receive a notice when your first RMD becomes due. Do not ask for their date of birth — "
                    "the account record is authoritative. 2-3 sentences, plain English."
                ),
            ))
        elif tx_missing and "taxable_event_acknowledged" in tx_missing:
            reply_parts.append(
                "Before I submit this, please confirm: Required Minimum Distributions are subject to "
                "ordinary income tax. The IRS mandates this distribution — failing to take it on time "
                "results in a 25% excise tax on the shortfall under IRC § 4974. "
                "Do you acknowledge this and wish to proceed?"
            )
        else:
            result = None
            try:
                # The plan issues the IRC §401(a)(9) RMD notice by Jan 31 — auto-confirm.
                # If participant said "process my RMD" without specifying amount, use the
                # plan-calculated rmd_amount_current_year from their record.
                rmd_payload = {**tx_params, "rmd_notice_issued": True}
                if "amount" not in rmd_payload:
                    rmd_info = get_rmd_info(participant_id)
                    if rmd_info.get("rmd_amount"):
                        rmd_payload["amount"] = rmd_info["rmd_amount"]
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="rmd",
                    payload=rmd_payload,
                )
            except UnauthorizedByFAP as e:
                reply_parts.append(_haiku_reply(
                    system_extra=(
                        f"FAP denied an RMD request.\n"
                        f"Denial reason: {e.denial_reason}\nDenial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the RMD request was denied and what the participant can do.",
                ))
            except Exception as e:
                reply_parts.append(f"Unable to process your RMD request right now: {e}")

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    rmd_amount = rmd_payload.get("amount", 0)
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="rmd",
                        payload=rmd_payload,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    reply_parts.append(_haiku_reply(
                        system_extra="",
                        instruction=(
                            f"An RMD (Required Minimum Distribution) of ${float(rmd_amount):,.0f} passed compliance "
                            f"checks and is queued for plan sponsor review. Tell the participant it needs sponsor "
                            f"approval and they'll be notified when processed. 2 sentences."
                        ),
                    ))
                    transaction = {"action": "rmd", "entry_id": entry_id}

    # ── QDRO ──────────────────────────────────────────────────────────────
    if tx_intent == "qdro":
        if tx_missing:
            first = tx_missing[0]
            if first == "alternate_payee_name":
                reply_parts.append("What is the full name of the alternate payee (the person receiving the transfer)?")
            elif first == "transfer_pct":
                reply_parts.append("What percentage of your vested balance should be transferred (e.g. 50 for 50%)?")
        else:
            try:
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="qdro",
                    payload=tx_params,
                )
            except UnauthorizedByFAP as e:
                reply_parts.append(_haiku_reply(
                    system_extra=(
                        f"FAP denied a QDRO request.\n"
                        f"Denial reason: {e.denial_reason}\nDenial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2-3 sentences why the QDRO was denied and what the participant can do.",
                ))
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your QDRO request right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="qdro",
                        payload=tx_params,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    payee = tx_params.get("alternate_payee_name", "")
                    pct   = tx_params.get("transfer_pct", 0)
                    reply_parts.append(_haiku_reply(
                        system_extra="",
                        instruction=(
                            f"A QDRO (Qualified Domestic Relations Order) of {pct}% to '{payee}' passed "
                            f"compliance checks and is queued for plan sponsor review. Tell the participant: "
                            f"(1) it needs sponsor approval, (2) they must upload the court order, "
                            f"(3) they'll be notified when approved. 3 sentences."
                        ),
                    ))
                    transaction = {
                        "action":               "qdro",
                        "alternate_payee_name": payee,
                        "transfer_pct":         pct,
                        "entry_id":             entry_id,
                    }

    # ── Beneficiary update ────────────────────────────────────────────────
    if tx_intent == "beneficiary_update":
        if tx_missing:
            first = tx_missing[0]
            if first == "beneficiary_name":
                reply_parts.append("What is the full name of your beneficiary?")
            elif first == "relationship":
                reply_parts.append("What is their relationship to you? (spouse, child, parent, sibling, estate, or other)")
        else:
            try:
                result = paap_execute(
                    participant_id=participant_id,
                    agent_id=session.agent_id or "portal",
                    action="beneficiary_update",
                    payload=tx_params,
                )
            except UnauthorizedByFAP as e:
                reply_parts.append(_haiku_reply(
                    system_extra=(
                        f"FAP denied a beneficiary update.\n"
                        f"Denial reason: {e.denial_reason}\nDenial code: {e.denial_code}"
                    ),
                    instruction="Explain in 2 sentences why the beneficiary update was denied.",
                ))
                result = None
            except Exception as e:
                reply_parts.append(f"Unable to process your beneficiary update right now: {e}")
                result = None

            if result is not None:
                autonomy = result["autonomy_level"]
                fap_token = result.get("fap_token")
                if autonomy == "human_review" and fap_token:
                    import datetime
                    from data.review_queue import enqueue
                    entry_id = enqueue(
                        participant_id=participant_id,
                        plan_id=result["plan_id"],
                        agent_id=session.agent_id or "portal",
                        principal_type="participant",
                        action="beneficiary_update",
                        payload=tx_params,
                        fap_audit_id=result.get("fap_audit_id") or "",
                        fap_token=fap_token,
                        created_at=datetime.datetime.utcnow().isoformat() + "Z",
                    )
                    name = tx_params.get("beneficiary_name", "")
                    rel  = tx_params.get("relationship", "")
                    reply_parts.append(_haiku_reply(
                        system_extra="",
                        instruction=(
                            f"A beneficiary update designating '{name}' ({rel}) passed compliance checks "
                            f"and is queued for plan sponsor review. Tell the participant it needs sponsor "
                            f"approval and they'll be notified when confirmed. 2 sentences."
                        ),
                    ))
                    transaction = {
                        "action":           "beneficiary_update",
                        "beneficiary_name": name,
                        "relationship":     rel,
                        "entry_id":         entry_id,
                    }

    # ── Nothing matched — use history to answer follow-ups or give a soft redirect ──
    if not reply_parts:
        reply_parts.append(_haiku_reply(
            system_extra="",
            instruction=(
                f'The participant said: "{req.message}". '
                "If this is a follow-up to the conversation above, answer it directly using that context. "
                "If it is a new question about 401k rules, ERISA, or their account, answer it. "
                "If it is completely unrelated, politely explain that you can help with loan requests, "
                "account balance questions, investment questions, or plan rules like vesting and RMDs."
            ),
            history=req.history,
        ))

    return {
        "reply":           "\n\n".join(reply_parts),
        "autonomy":        autonomy,
        "transaction":     transaction,
        "intent":          tx_intent or ("data_question" if dtype else ("conceptual_question" if ctopic else "unknown")),
        "pending_tax_ack": pending_tax_ack,
    }
