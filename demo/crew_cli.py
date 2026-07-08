"""
Aldergate CrewAI CLI — interactive multi-agent ERISA compliance interface.

Powered by Claude + CrewAI. Three domain crews:
  · Participant       — self-service loan, deferral, investment, distribution requests
  · Plan Sponsor      — approve/deny queue, manage blackouts, view audit log
  · Investment Advisor — submit investment recommendations for client accounts

Run:
  source .venv/bin/activate
  python demo/crew_cli.py
"""

import os
import sys
import textwrap

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

# Clear the review queue and document store on every startup (demo only).
# Queue and documents persist to disk — survive CLI restarts.
# Run "reset" as plan sponsor to clear both for a fresh demo.
import pathlib as _pathlib

# ANSI colors
RST  = "\033[0m"
BOLD = "\033[1m"
DIM  = "\033[2m"
C    = "\033[36m"      # cyan
G    = "\033[32m"      # green
Y    = "\033[33m"      # yellow
R    = "\033[31m"      # red
M    = "\033[35m"      # magenta
W    = "\033[37m"      # white


def hr(char="─", width=70):
    print(f"{DIM}{char * width}{RST}")


def header(title: str):
    print()
    hr("═")
    print(f"{BOLD}  {title}{RST}")
    hr("═")
    print()


def section(title: str):
    print()
    hr()
    print(f"{C}{BOLD}  {title}{RST}")
    hr()


def pick(prompt: str, options: list[tuple[str, str]]) -> str:
    """Show numbered options and return the selected key."""
    print(f"\n{BOLD}{prompt}{RST}")
    for i, (key, label) in enumerate(options, 1):
        print(f"  {Y}{i}{RST}  {label}  {DIM}({key}){RST}")
    while True:
        raw = input(f"\n{G}Enter number:{RST} ").strip()
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return options[idx][0]
        except ValueError:
            pass
        print(f"{R}  Invalid choice. Enter 1–{len(options)}.{RST}")


def wrap_output(text: str, width: int = 68):
    """Wrap long output lines for readability."""
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.upper().startswith("STATUS:"):
            print(f"\n  {BOLD}{G}{stripped}{RST}")
        elif stripped.upper().startswith("DETAILS:") or stripped.upper().startswith("NEXT STEPS:"):
            print(f"\n  {BOLD}{C}{stripped}{RST}")
        elif stripped.startswith("-") or stripped.startswith("•"):
            print(f"  {DIM}{stripped}{RST}")
        elif len(line) > width:
            for wrapped in textwrap.wrap(line, width=width):
                print(f"  {wrapped}")
        else:
            print(f"  {line}")


# ---------------------------------------------------------------------------
# Compliance rule trace — shown live after RunComplianceCheck fires
# ---------------------------------------------------------------------------

_RULE_NAMES = [
    ( 1, "Delegation Validity",         "ERISA §404"),
    ( 2, "Blackout Period",              "ERISA §101(i)"),
    ( 3, "Participation & Eligibility",  "ERISA §202"),
    ( 4, "Vesting Enforcement",          "ERISA §203"),
    ( 5, "Contribution Limits",          "IRC §402(g)"),
    ( 6, "Plan Rules",                   "plan-specific"),
    ( 7, "Early Withdrawal Penalty",     "IRC §72(t)"),
    ( 8, "Anti-Alienation",              "ERISA §206(d)"),
    ( 9, "Prohibited Transaction",       "ERISA §406"),
    (10, "Prudent Expert",               "ERISA §404"),
    (11, "RMD Failure Prevention",       "IRC §401(a)(9)"),
    (12, "Autonomy Level Assignment",    "—"),
]

_DENIAL_TO_RULE = {
    "AGENT_NOT_REGISTERED": 1,      "DELEGATION_SCOPE_EXCEEDED": 1,
    "BLACKOUT_ACTIVE": 2,
    "ELIGIBILITY_NOT_MET": 3,       "ENTRY_DATE_NOT_REACHED": 3,
    "INSUFFICIENT_VESTING": 4,
    "DEFERRAL_LIMIT_EXCEEDED": 5,   "ANNUAL_ADDITIONS_LIMIT_EXCEEDED": 5,
    "ROTH_CATCHUP_REQUIRED": 5,
    "LOAN_CAP_EXCEEDED": 6,         "LOAN_NOT_PERMITTED": 6,
    "LOANS_OUTSTANDING_LIMIT": 6,   "HARDSHIP_NOT_PERMITTED": 6,
    "HARDSHIP_CRITERIA_NOT_MET": 6, "IN_SERVICE_AGE_NOT_MET": 6,
    "SEPARATION_STATUS_INVALID": 6, "ROLLOVER_NOTICE_NOT_ISSUED": 6,
    "RMD_NOT_YET_REQUIRED": 6,      "RMD_NOTICE_NOT_ISSUED": 6,
    "RMD_AMOUNT_INSUFFICIENT": 6,   "QJSA_CONSENT_REQUIRED": 6,
    "QDRO_FIELDS_MISSING": 6,
    "EARLY_WITHDRAWAL_PENALTY_APPLIES": 7,
    "ANTI_ALIENATION_VIOLATION": 8,
    "PROHIBITED_TRANSACTION": 9,
    "RMD_SHORTFALL_RISK": 11,
}


def _show_compliance_trace(result_summary: str) -> None:
    """Print the 12-rule pass/fail trace based on the RunComplianceCheck result summary."""
    approved = result_summary.startswith("APPROVED")

    if approved:
        # e.g. "APPROVED  autonomy=human_review"
        autonomy = ""
        if "autonomy=" in result_summary:
            autonomy = result_summary.split("autonomy=")[-1].strip()
        fail_at = 13  # all rules pass
    else:
        # e.g. "DENIED  RMD_SHORTFALL_RISK"
        parts = result_summary.split()
        denial_code = parts[-1] if len(parts) >= 2 else "UNKNOWN"
        fail_at = _DENIAL_TO_RULE.get(denial_code, 12)

    print()
    for num, name, citation in _RULE_NAMES:
        if num < fail_at:
            # Rule passed
            if num == 12 and approved:
                tag = f"{G}{autonomy.upper()}{RST}  {DIM}token issued{RST}"
                print(f"  {G}✓{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {tag}")
            else:
                print(f"  {G}✓{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {DIM}{citation}{RST}")
        elif num == fail_at:
            code_str = denial_code if not approved else autonomy.upper()
            print(f"  {R}✗{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {R}FAIL  ← {code_str}{RST}")
            print(f"  {DIM}     Rules {num+1}–12 not evaluated (fail-fast){RST}")
            break
    print()


# ---------------------------------------------------------------------------
# Session context helpers — built dynamically from mock data
# ---------------------------------------------------------------------------

def _build_participant_menu() -> dict[str, str]:
    from data.participants import ALL_PARTICIPANTS
    labels = {
        "PART-008": ("Amara Osei",    "PLAN-003", "age 36 · $85k vested · no loans · 5yr service · primary demo"),
        "PART-006": ("Gabriel Stone", "PLAN-003", "age 61 · HCE · $210k vested · catch-up eligible · near retirement"),
        "PART-009": ("Daniela Reyes", "PLAN-003", "age 41 · $100k vested · existing $25k loan · §72(p) cap demo"),
        "PART-007": ("Yuki Tanaka",   "PLAN-004", "age 31 · Prudential · 1.5yr service · cliff vesting not met"),
    }
    out = {}
    for pid, (name, plan, notes) in labels.items():
        p = ALL_PARTICIPANTS.get(pid)
        vested = f"${p.vested_balance:,.0f}" if p else "—"
        loan_headroom = f"${float(p.max_additional_loan_amount):,.0f}" if p else "—"
        out[pid] = (
            f"{name:<14}  {plan}  vested {vested}  "
            f"headroom {loan_headroom}  {notes}"
        )
    return out

PARTICIPANTS = _build_participant_menu()

PLANS = {
    "PLAN-003": "Capital One Associate Savings Plan  [safe harbor · immediate eligibility · Fidelity]",
    "PLAN-004": "Prudential Employee Savings Plan (PESP)  [1yr wait · 3yr cliff · Empower]",
}


def choose_participant() -> tuple[str, str]:
    """Returns (participant_id, plan_id)."""
    options = [(pid, desc) for pid, desc in PARTICIPANTS.items()]
    pid = pick("Select participant:", options)
    from data.participants import ALL_PARTICIPANTS
    p = ALL_PARTICIPANTS.get(pid)
    return pid, p.plan_id if p else "PLAN-003"


def choose_plan() -> str:
    options = [(pid, desc) for pid, desc in PLANS.items()]
    return pick("Select plan to administer:", options)


# ---------------------------------------------------------------------------
# Crew runner — structured output only
# ---------------------------------------------------------------------------

def _show_run_error(exc: Exception) -> None:
    name = type(exc).__name__
    msg = str(exc)
    print()
    if "APIConnectionError" in name or "ConnectionError" in name or "Connection error" in msg:
        print(f"  {R}Connection error{RST} — could not reach the Anthropic API.")
        print(f"  {DIM}Check your internet connection and try again.{RST}")
    elif "AuthenticationError" in name or "invalid_api_key" in msg or "401" in msg:
        print(f"  {R}Authentication error{RST} — check ANTHROPIC_API_KEY in your .env file.")
    elif "RateLimitError" in name or "429" in msg:
        print(f"  {R}Rate limit reached{RST} — too many requests. Wait a moment and try again.")
    elif "APIStatusError" in name:
        print(f"  {R}API error ({name}){RST}: {msg[:120]}")
    else:
        print(f"  {R}Error ({name}){RST}: {msg[:120]}")
    print()


# Tool → (step_number, step_label)
_TOOL_STEPS = {
    "GetPlanRules":          (2, "Data Agent — plan rules"),
    "GetFundLineup":         (2, "Data Agent — fund lineup"),
    "GetParticipantSummary": (3, "Data Agent — participant data"),
    "GetLoanHeadroom":       (3, "Data Agent — loan headroom"),
    "RunComplianceCheck":    (4, "Compliance Agent — FAP · 12 ERISA rules"),
    "ExecuteTransaction":    (5, "Data Agent — execute / queue transaction"),
    "GetPendingReviews":     (2, "Data Agent — review queue"),
    "GetAuditLog":           (2, "Data Agent — FAP audit log"),
    "ApproveRequest":        (3, "Action Agent — approving request"),
    "DenyRequest":           (3, "Action Agent — denying request"),
    "ManageBlackout":        (2, "Data/Action Agent — blackout management"),
}


def _make_live_fn() -> tuple:
    """
    Returns (live_fn, get_last_step) for real-time tool call display.
    Writes directly to sys.__stdout__ so output appears even inside redirect_stdout.
    """
    import sys
    out = sys.__stdout__
    state = {"step": 1}

    def live_fn(tool: str, args: str, result: str) -> None:
        step_num, step_label = _TOOL_STEPS.get(tool, (state["step"], tool))

        # Print step header when we enter a new step
        if step_num > state["step"]:
            state["step"] = step_num
            print(f"\n  {Y}[{step_num}]{RST}  {BOLD}{step_label}{RST}", file=out, flush=True)

        # Tool call line
        approved = "APPROVED" in result
        denied = "DENIED" in result or "ERROR" in result
        sym = f"{G}✓{RST}" if not denied else f"{R}✗{RST}"
        result_color = G if approved else (R if denied else DIM)
        print(
            f"       {sym}  {C}{tool:<22}{RST}  {DIM}{args[:28]:<28}{RST}"
            f"  {result_color}{result}{RST}",
            file=out, flush=True,
        )

        # Compliance trace: expand all 12 rules inline
        if tool == "RunComplianceCheck":
            _show_compliance_trace_to(result, out)

    def get_step():
        return state["step"]

    return live_fn, get_step


def _show_compliance_trace_to(result_summary: str, out) -> None:
    """Print the 12-rule trace to `out` (sys.__stdout__ during live mode)."""
    approved = result_summary.startswith("APPROVED")

    if approved:
        autonomy = result_summary.split("autonomy=")[-1].strip() if "autonomy=" in result_summary else "full"
        fail_at = 13
    else:
        parts = result_summary.split()
        denial_code = parts[-1] if len(parts) >= 2 else "UNKNOWN"
        fail_at = _DENIAL_TO_RULE.get(denial_code, 12)

    print(file=out)
    for num, name, citation in _RULE_NAMES:
        if num < fail_at:
            if num == 12 and approved:
                tag = f"{G}{autonomy.upper()}{RST}  {DIM}→ JWT token issued{RST}"
                print(f"       {G}✓{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {tag}", file=out, flush=True)
            else:
                print(f"       {G}✓{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {DIM}{citation}{RST}", file=out, flush=True)
        elif num == fail_at:
            code_disp = denial_code if not approved else autonomy.upper()
            print(f"       {R}✗{RST}  {DIM}Rule {num:2d}{RST}  {name:<30}  {R}FAIL  ← {code_disp}{RST}", file=out, flush=True)
            if num < 12:
                print(f"       {DIM}     Rules {num+1}–12 not evaluated (fail-fast){RST}", file=out, flush=True)
            break
    print(file=out, flush=True)


def run_crew(crew, session_label: str) -> bool:
    from crew.tool_logger import reset as tl_reset, set_live, clear_live
    import io, contextlib

    tl_reset()
    live_fn, get_step = _make_live_fn()
    set_live(live_fn)

    out = sys.__stdout__

    # Step 1 header — Intent Agent always runs first (no tools)
    print(f"\n  {Y}[1]{RST}  {BOLD}Intent Agent — parsing query...{RST}", file=out, flush=True)

    try:
        buf_err = io.StringIO()
        with contextlib.redirect_stderr(buf_err):
            result = crew.kickoff()
    except KeyboardInterrupt:
        clear_live()
        raise
    except Exception as exc:
        clear_live()
        _show_run_error(exc)
        return False
    finally:
        clear_live()

    # Final step — composing response (always last)
    last_step = get_step()
    final_step = last_step + 1
    print(f"\n  {Y}[{final_step}]{RST}  {BOLD}Intent Agent — composing response...{RST}", file=out, flush=True)

    # Response
    section(f"Response  ·  {session_label}")
    final = result.raw if hasattr(result, "raw") else str(result)
    wrap_output(final)
    print()
    return True


# ---------------------------------------------------------------------------
# Supervised transaction confirmation helpers
# ---------------------------------------------------------------------------

def show_supervised_panel(participant_id: str, pending: dict) -> None:
    """Display a structured confirmation box for a supervised transaction."""
    action = pending["action"]
    payload = pending["payload"]

    print()
    hr("═")
    print(f"{BOLD}{Y}  CONFIRMATION REQUIRED{RST}")
    hr("═")
    print(f"  {DIM}FAP approved this transaction, but it carries financial impact.{RST}")
    print(f"  {DIM}All 12 ERISA rules passed. Your explicit confirmation is required.{RST}")
    print()
    print(f"  {BOLD}Participant {RST}  {participant_id}")
    print(f"  {BOLD}Action      {RST}  {action.replace('_', ' ').title()}")

    if action == "loan_initiation":
        amt = payload.get("amount") or payload.get("loan_amount")
        yrs = payload.get("repayment_years") or payload.get("term_years")
        purp = payload.get("purpose", "general purpose")
        if amt is not None:
            try:
                print(f"  {BOLD}Amount      {RST}  ${float(amt):,.2f}")
            except (TypeError, ValueError):
                print(f"  {BOLD}Amount      {RST}  {amt}")
        if yrs is not None:
            print(f"  {BOLD}Term        {RST}  {yrs} years")
        print(f"  {BOLD}Purpose     {RST}  {purp}")
        print(f"  {DIM}  This loan reduces your retirement savings and accrues interest.{RST}")
    elif action == "deferral_change":
        pct = payload.get("new_deferral_pct")
        dtype = payload.get("deferral_type", "pre_tax")
        if pct is not None:
            pct_val = float(pct)
            print(f"  {BOLD}New rate    {RST}  {pct_val * 100:.1f}%  ({dtype})")
            if pct_val == 0.0:
                print(f"  {DIM}  Setting to 0% stops all retirement contributions.{RST}")

    print()
    hr()
    print(f"  Type  {G}confirm{RST}  to execute   ·   Type  {R}cancel{RST}  to abort")
    hr("═")
    print()


def _execute_supervised_confirmed(participant_id: str) -> None:
    """Execute a supervised transaction after the participant typed 'confirm'."""
    import json as _json
    from crew.tools.paap_tools import get_supervised_pending, clear_supervised_pending, ExecuteTransactionTool

    pending = get_supervised_pending(participant_id)
    if not pending:
        print(f"\n  {R}No pending transaction found.{RST}")
        return

    clear_supervised_pending(participant_id)
    print(f"\n  {DIM}Executing confirmed transaction...{RST}\n")

    tool = ExecuteTransactionTool()
    # Pass autonomy_level="full" so the tool executes rather than looping back to supervised.
    result_raw = tool._run(
        participant_id=participant_id,
        action=pending["action"],
        payload_json=pending["payload_json"],
        fap_token=pending["fap_token"],
        autonomy_level="full",
    )

    try:
        result = _json.loads(result_raw)
    except Exception:
        result = {"status": "unknown", "message": result_raw}

    section("Transaction Executed")
    status = result.get("status", "unknown")
    if status == "executed":
        print(f"  {G}EXECUTED{RST}")
        action_str = result.get("action", "").replace("_", " ").title()
        print(f"  {BOLD}Action      {RST}  {action_str}")
        print(f"  {BOLD}Participant {RST}  {result.get('participant_id')}")
        p = result.get("payload", {})
        if "amount" in p:
            try:
                print(f"  {BOLD}Amount      {RST}  ${float(p['amount']):,.2f}")
            except (TypeError, ValueError):
                print(f"  {BOLD}Amount      {RST}  {p['amount']}")
        if "repayment_years" in p:
            print(f"  {BOLD}Term        {RST}  {p['repayment_years']} years")
        if "new_deferral_pct" in p:
            try:
                print(f"  {BOLD}New rate    {RST}  {float(p['new_deferral_pct'])*100:.1f}%")
            except (TypeError, ValueError):
                pass
        print()
        print(f"  {DIM}{result.get('message', '')}{RST}")
    elif "error" in result:
        print(f"  {R}Execution failed{RST}: {result['error']}")
    else:
        print(f"  Status: {status}")
        print(f"  {DIM}{result.get('message', '')}{RST}")
    print()


# ---------------------------------------------------------------------------
# Participant session
# ---------------------------------------------------------------------------

PARTICIPANT_EXAMPLES = [
    "balance              ← instant: vested balance, loans, fund elections",
    "my investments       ← instant: fund allocation breakdown",
    "my deferral          ← instant: contribution rate + YTD breakdown",
    "my employment        ← instant: status, hire date, vesting, service",
    "my plan              ← instant: plan name, type, loan/hardship rules",
    "ytd                  ← instant: employee + employer contributions year-to-date",
    "how much can I borrow← instant: max loan under IRC §72(p)",
    "status               ← instant: pending/approved requests in the queue",
    "my beneficiary       ← instant: beneficiary info (Phase 5 when available)",
    "my address           ← instant: contact info (Phase 5 when available)",
    "I want to take out a $10,000 loan over 5 years",
    "Change my deferral to 8% pre-tax",
    "I need a $5,000 hardship withdrawal for a medical emergency",
    "Reallocate to 70% COF-LIFEPATH-2040 and 30% COF-SP500    ← Capital One funds",
    "Reallocate to 80% PESP-GOALMAKER-MOD and 20% PESP-STABLE ← Prudential funds",
    "Update my address to 456 Oak Street, Chicago, IL 60601",
]


def _participant_fast_read(query: str, participant_id: str, plan_id: str) -> bool:
    """
    Handle read-only participant queries without CrewAI.
    Returns True if handled, False if it should go through the crew.
    """
    import json as _json
    q = query.lower().strip()

    # Status check — "is my hardship approved", "status of my request", "my pending requests" etc.
    status_keywords = [
        "status", "approved", "pending", "my request", "my hardship",
        "my withdrawal", "my distribution", "my loan status", "did my",
        "was my", "check my", "what happened to my",
    ]
    if any(w in q for w in status_keywords) and not any(
        w in q for w in ["new", "take out", "apply", "submit", "request a", "want a", "need a",
                         "employment", "vesting", "hire", "service"]
    ):
        from data.review_queue import get_all, reload
        reload()
        entries = [e for e in get_all() if e.participant_id == participant_id]
        section(f"Your Requests — {participant_id}")
        if not entries:
            print(f"  {DIM}No requests on file for {participant_id}.{RST}")
            print(f"  {DIM}(Only hardship, separation, RMD, beneficiary, and QDRO requests appear here.){RST}")
        else:
            for e in entries:
                action_str = e.action.replace("_", " ").title()
                payload = e.payload or {}
                amt = payload.get("amount", "")
                amt_str = f"  ${float(amt):,.0f}" if amt else ""
                if e.status == "approved":
                    status_line = f"{G}✓  APPROVED{RST}"
                elif e.status == "denied":
                    status_line = f"{R}✗  DENIED{RST}"
                else:
                    status_line = f"{Y}⏳  PENDING — awaiting sponsor review{RST}"
                print(f"  {status_line}")
                print(f"  [{DIM}{e.entry_id}{RST}]  {C}{action_str}{RST}{amt_str}")
                print(f"  Submitted:  {DIM}{e.created_at[:10]}{RST}")
                if e.sponsor_note:
                    print(f"  Sponsor:    {DIM}\"{e.sponsor_note}\"{RST}")
                if e.status == "approved":
                    print(f"  {DIM}  Production: funds disbursed within 3–5 business days.{RST}")
                elif e.status == "denied":
                    print(f"  {DIM}  You may reapply with additional documentation.{RST}")
                print()
        print()
        return True

    # Balance / account summary — instant read
    # Calls get_participant() directly (not the LLM-facing tool) so the participant
    # sees their own full balance. PII minimization applies only to LLM tool outputs.
    _balance_write = ["withdraw", "withdrawal", "distribution", "take out",
                      "in-service", "in service", "rollover", "make a", "want to take"]
    if any(w in q for w in ["balance", "vested", "my account", "account summary", "how much do i have"]) and not any(
        w in q for w in _balance_write
    ):
        from data.participants import get_participant
        from data.plans import get_plan
        p = get_participant(participant_id)
        section(f"Account Summary — {participant_id}")
        if not p:
            print(f"  {R}Participant {participant_id} not found.{RST}")
        else:
            print(f"  {BOLD}Vested balance  {RST}  ${float(p.vested_balance):,.2f}")
            print(f"  {BOLD}Deferral rate   {RST}  {float(p.current_deferral_pct)*100:.1f}%")
            print(f"  {BOLD}Employment      {RST}  {p.employment_status.value}")
            print(f"  {BOLD}Vesting %       {RST}  {float(p.vesting_percentage)*100:.0f}%")
            if p.outstanding_loans:
                print(f"  {BOLD}Active loans    {RST}  {len(p.outstanding_loans)}")
                for loan in p.outstanding_loans:
                    print(f"    {DIM}· ${float(loan.outstanding_balance):,.0f} outstanding  (matures {loan.maturity_date}){RST}")
            else:
                print(f"  {BOLD}Active loans    {RST}  none")
            if p.investment_elections:
                fund_names = {}
                plan = get_plan(p.plan_id)
                if plan:
                    fund_names = {f.fund_id: f.fund_name for f in plan.fund_lineup}
                print(f"  {BOLD}Fund elections  {RST}")
                for e in p.investment_elections:
                    name = fund_names.get(e.fund_id, e.fund_id)
                    bar = "█" * int(e.allocation_pct * 20)
                    print(f"    {DIM}· {bar:<20}  {e.allocation_pct*100:>5.0f}%  {e.fund_id}  {name}{RST}")
        print(f"  {DIM}  Note: balances are seeded demo data — live balances sync from recordkeeper (Phase 5).{RST}")
        print()
        return True

    # Investment elections — instant read (only for read queries, not reallocation commands)
    if any(w in q for w in ["investment", "fund", "my funds", "elections", "allocated", "what am i in", "where is my money"]) and not any(w in q for w in ["reallocate", "move", "change", "rebalance", "switch", "put", "allocate", "%"]):
        from data.participants import get_participant
        from data.plans import get_plan
        p = get_participant(participant_id)
        section(f"Investment Elections — {participant_id}")
        if not p:
            print(f"  {R}Participant {participant_id} not found.{RST}")
        elif not p.investment_elections:
            print(f"  {DIM}No investment elections on file.{RST}")
        else:
            fund_names = {}
            plan = get_plan(p.plan_id)
            if plan:
                fund_names = {f.fund_id: f.fund_name for f in plan.fund_lineup}
            total = sum(e.allocation_pct for e in p.investment_elections)
            for e in p.investment_elections:
                name = fund_names.get(e.fund_id, e.fund_id)
                bar = "█" * int(e.allocation_pct * 20)
                print(f"  {C}{e.allocation_pct*100:>5.0f}%{RST}  {G}{bar:<20}{RST}  {BOLD}{e.fund_id}{RST}  {DIM}{name}{RST}")
            print()
            print(f"  {DIM}Total: {total*100:.0f}%  ·  Plan: {p.plan_id}  ·  Type: {p.deferral_type.value}{RST}")
            print(f"  {DIM}To change: type  reallocate my investments  or  move everything to [fund]{RST}")
        print()
        return True

    # Loan headroom — instant read
    if any(w in q for w in ["how much can i borrow", "loan headroom", "borrow limit", "max loan", "maximum loan"]):
        from crew.tools.paap_tools import GetLoanHeadroomTool
        raw = GetLoanHeadroomTool()._run(participant_id=participant_id)
        data = _json.loads(raw)
        section(f"Loan Headroom — {participant_id}")
        print(f"  {BOLD}Max you can borrow  {RST}  ${data.get('loan_headroom_usd', 0):,.2f}")
        print(f"  {BOLD}Active loans        {RST}  {data.get('outstanding_loans', 0)}")
        print(f"  {DIM}  IRC §72(p): lesser of $50k minus prior loans, or 50% of vested balance.{RST}")
        print()
        return True

    # Deferral / contribution rate — instant read (not write commands)
    _deferral_write = ["change", "set", "update", "increase", "decrease", "reduce",
                       "raise", "lower", "modify", "switch", "want to", "i want",
                       "i'd like", "new", "%"]
    if any(w in q for w in ["deferral", "contribution rate", "how much am i contributing",
                             "what's my deferral", "my contribution", "savings rate",
                             "how much do i save", "my rate"]) and not any(
        w in q for w in _deferral_write
    ):
        from data.participants import get_participant
        p = get_participant(participant_id)
        section(f"Deferral Election — {participant_id}")
        if not p:
            print(f"  {R}Participant {participant_id} not found.{RST}")
        else:
            pct = float(p.current_deferral_pct) * 100
            dtype = p.deferral_type.value.replace("_", "-")
            print(f"  {BOLD}Deferral rate       {RST}  {pct:.1f}%  ({dtype})")
            print(f"  {BOLD}Employee YTD        {RST}  ${float(p.employee_contributions_ytd):,.2f}")
            print(f"  {BOLD}Employer YTD        {RST}  ${float(p.employer_contributions_ytd):,.2f}")
            total_ytd = float(p.employee_contributions_ytd) + float(p.employer_contributions_ytd)
            print(f"  {BOLD}Total YTD           {RST}  ${total_ytd:,.2f}")
            if p.is_hce:
                print(f"  {DIM}  HCE — subject to ADP/ACP nondiscrimination testing.{RST}")
            if p.age_50_or_older and not p.age_60_to_63:
                print(f"  {DIM}  Catch-up eligible (age 50+): additional $7,500/yr.{RST}")
            if p.age_60_to_63:
                print(f"  {DIM}  SECURE 2.0 enhanced catch-up (age 60–63): additional $10,000/yr.{RST}")
            print(f"  {DIM}  To change: tell me your new deferral rate.{RST}")
        print()
        return True

    # Employment / service / vesting — instant read
    if any(w in q for w in ["employment", "am i active", "my status", "service years",
                             "years of service", "when did i start", "hire date",
                             "vesting", "eligibility", "my service"]):
        from data.participants import get_participant
        from data.plans import get_plan
        p = get_participant(participant_id)
        section(f"Employment & Service — {participant_id}")
        if not p:
            print(f"  {R}Participant {participant_id} not found.{RST}")
        else:
            plan = get_plan(p.plan_id)
            plan_name = plan.plan_name if plan else p.plan_id
            print(f"  {BOLD}Plan                {RST}  {p.plan_id}  {DIM}({plan_name}){RST}")
            print(f"  {BOLD}Employment status   {RST}  {p.employment_status.value}")
            print(f"  {BOLD}Hire date           {RST}  {p.hire_date}")
            print(f"  {BOLD}Eligibility date    {RST}  {p.eligibility_date}")
            print(f"  {BOLD}Vesting service     {RST}  {p.years_of_vesting_service:.1f} years")
            vest_pct = float(p.vesting_percentage) * 100
            if vest_pct == 0:
                print(f"  {BOLD}Employer match      {RST}  {Y}0% vested{RST}  {DIM}(cliff not yet reached — employee contributions always 100% yours){RST}")
            elif vest_pct < 100:
                print(f"  {BOLD}Employer match      {RST}  {Y}{vest_pct:.0f}% vested{RST}  {DIM}(graduated schedule — employee contributions always 100% yours){RST}")
            else:
                print(f"  {BOLD}Employer match      {RST}  {G}100% vested{RST}")
            if p.termination_date:
                print(f"  {BOLD}Termination date    {RST}  {p.termination_date}")
            if p.break_in_service:
                print(f"  {Y}  Break in service on record.{RST}")
            if p.userra_military_leave:
                print(f"  {DIM}  USERRA military leave — service credit preserved.{RST}")
            if p.is_hce:
                print(f"  {Y}  Highly Compensated Employee (HCE) — ADP/ACP limits apply.{RST}")
        print()
        return True

    # Plan info — instant read
    if any(w in q for w in ["my plan", "what plan", "plan details", "plan name",
                             "which plan", "plan info", "plan rules summary"]):
        from data.plans import get_plan
        from data.participants import get_participant
        p = get_participant(participant_id)
        plan = get_plan(plan_id) if not p else get_plan(p.plan_id)
        section(f"Plan Information — {plan_id}")
        if not plan:
            print(f"  {R}Plan {plan_id} not found.{RST}")
        else:
            print(f"  {BOLD}Plan name           {RST}  {plan.plan_name}")
            print(f"  {BOLD}Plan type           {RST}  {plan.plan_type.value}")
            print(f"  {BOLD}Safe harbor         {RST}  {'Yes' if plan.safe_harbor else 'No'}")
            print(f"  {BOLD}ERISA plan #        {RST}  {plan.erisa_plan_number}")
            print(f"  {BOLD}Plan year end       {RST}  {plan.plan_year_end}")
            print(f"  {BOLD}Loans permitted     {RST}  {'Yes' if plan.loan_policy.loans_permitted else 'No'}")
            print(f"  {BOLD}Hardship permitted  {RST}  {'Yes' if plan.hardship_policy.hardship_permitted else 'No'}")
            print(f"  {BOLD}In-service (59½+)   {RST}  {'Yes' if plan.distribution_options.in_service_age_59_5 else 'No'}")
            if plan.blackout_status.is_active:
                print(f"  {R}  BLACKOUT ACTIVE — all writes blocked.{RST}")
        print()
        return True

    # YTD contributions breakdown — instant read
    if any(w in q for w in ["ytd", "year to date", "this year contributions",
                             "my contributions this year", "how much have i contributed"]):
        from data.participants import get_participant
        p = get_participant(participant_id)
        section(f"Contributions YTD — {participant_id}")
        if not p:
            print(f"  {R}Participant {participant_id} not found.{RST}")
        else:
            emp_ytd = float(p.employee_contributions_ytd)
            er_ytd = float(p.employer_contributions_ytd)
            total = emp_ytd + er_ytd
            # IRS 402(g) limit context
            limit_402g = 23_000
            pct_used = (emp_ytd / limit_402g * 100) if limit_402g else 0
            bar_len = int(pct_used / 5)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"  {BOLD}Employee (pre-tax)  {RST}  ${emp_ytd:,.2f}")
            print(f"  {BOLD}Employer (match)    {RST}  ${er_ytd:,.2f}")
            print(f"  {BOLD}Total YTD           {RST}  ${total:,.2f}")
            print()
            print(f"  {DIM}  402(g) limit progress:  {bar}  {pct_used:.0f}% of ${limit_402g:,}{RST}")
            if p.age_50_or_older:
                catchup = 10_000 if p.age_60_to_63 else 7_500
                print(f"  {DIM}  +${catchup:,} catch-up allowance available.{RST}")
        print()
        return True

    # Beneficiary — read-only info (write commands go through CrewAI)
    _beneficiary_write = ["update", "change", "set", "add", "designate", "want to",
                          "i want", "i'd like", "remove", "make", "to my", "as my"]
    if "beneficiary" in q and not any(w in q for w in _beneficiary_write):
        from data.participants import get_participant
        from data.plans import get_plan
        p = get_participant(participant_id)
        plan = get_plan(p.plan_id) if p else None
        section(f"Beneficiary — {participant_id}")
        print(f"  {Y}Beneficiary records are not available in this demo.{RST}")
        print()
        print(f"  {DIM}In production, your beneficiary designation is stored by the recordkeeper")
        if plan:
            print(f"  {DIM}({plan.plan_name}) and synced to Aldergate (Phase 5).{RST}")
        print()
        print(f"  To update your beneficiary, type:")
        print(f"  {C}  Update my beneficiary to [Name], relationship [spouse/child/other]{RST}")
        print(f"  {DIM}  This goes to the plan sponsor queue for QJSA review (ERISA §205).{RST}")
        print()
        return True

    # Address / contact info — read-only info (write commands go through CrewAI)
    _address_write = ["update", "change", "set", "new address", "move to", "move my"]
    if any(w in q for w in ["address", "my contact", "contact info", "mailing address",
                             "where do i live", "my home address"]) and not any(
        w in q for w in _address_write
    ):
        section(f"Address — {participant_id}")
        print(f"  {Y}Address records are not stored in this demo.{RST}")
        print()
        print(f"  {DIM}In production, your address is maintained by your employer's HR system")
        print(f"  {DIM}and synced from the recordkeeper nightly (Phase 5).{RST}")
        print()
        print(f"  To update your address, type:")
        print(f"  {C}  Update my address to [new address]{RST}")
        print(f"  {DIM}  Address updates are processed immediately (full autonomy — no FAP review needed).{RST}")
        print()
        return True

    # QDRO — fast path: Python extracts the 5 fields directly, bypasses LLM field parsing
    if "qdro" in q or "qualified domestic relations" in q:
        import json as _json
        import re as _re
        from crew.tools.fap_tools import RunComplianceCheckTool
        from crew.tools.paap_tools import ExecuteTransactionTool

        out = sys.__stdout__
        print(f"\n  {Y}[1]{RST}  {BOLD}QDRO — collecting required fields...{RST}", file=out)

        # Extract whatever fields are present in the initial query
        _patterns = {
            "participant_name":      r"[Pp]articipant(?:\s+name)?[:\s]+([^\n.]+)",
            "alternate_payee_name":  r"[Aa]lternate\s+payee(?:\s+name)?[:\s]+([^\n.]+)",
            "plan_name":             r"[Pp]lan[:\s]+([^\n.]+)",
            "benefit_amount_or_pct": r"[Aa]mount[:\s]+([^\n.]+)",
            "payment_period":        r"[Pp]ayment\s+period[:\s]+([^\n.]+)",
        }
        _prompts = {
            "participant_name":      "  Participant name",
            "alternate_payee_name":  "  Alternate payee name",
            "plan_name":             "  Plan name (from court order)",
            "benefit_amount_or_pct": "  Benefit amount or %",
            "payment_period":        "  Payment period",
        }

        # Drain any buffered stdin lines (multi-line paste) before extracting fields.
        # This prevents subsequent paste lines from feeding the wrong interactive prompt.
        import select as _select
        full_query = query
        while True:
            ready, _, _ = _select.select([sys.stdin], [], [], 0.05)
            if not ready:
                break
            line = sys.stdin.readline()
            if not line:
                break
            full_query += "\n" + line.rstrip("\n")

        fields: dict[str, str] = {}
        for key, pattern in _patterns.items():
            m = _re.search(pattern, full_query)
            if m:
                fields[key] = m.group(1).strip().rstrip(".,;")

        # Prompt interactively only for fields genuinely not in the message
        missing = [k for k in _patterns if k not in fields]
        if missing:
            print(f"\n  {DIM}Please provide the {len(missing)} missing field(s):{RST}")
            for key in missing:
                try:
                    val = input(f"{G}{_prompts[key]}:{RST} ").strip().rstrip(".,;")
                except EOFError:
                    val = ""
                if not val:
                    print(f"\n  {Y}QDRO cancelled.{RST}\n")
                    return True
                fields[key] = val

        payload_json = _json.dumps(fields)

        # Run FAP directly with the complete payload
        print(f"\n  {Y}[2]{RST}  {BOLD}Compliance Agent — FAP · 12 ERISA rules{RST}", file=out)
        fap_raw = RunComplianceCheckTool()._run(
            agent_id="AGENT-PARTICIPANT-001",
            participant_id=participant_id,
            plan_id=plan_id,
            action="qdro",
            payload_json=payload_json,
        )

        fap_result = _json.loads(fap_raw)
        authorized = fap_result.get("authorized", False)
        sym = f"{G}✓{RST}" if authorized else f"{R}✗{RST}"
        result_summary = (
            f"APPROVED  autonomy={fap_result.get('autonomy_level', '')}"
            if authorized else
            f"DENIED  {fap_result.get('denial_code', 'UNKNOWN')}"
        )
        print(
            f"       {sym}  {C}{'RunComplianceCheck':<22}{RST}  "
            f"{DIM}{'qdro  ' + participant_id:<28}{RST}  "
            f"{(G if authorized else R)}{result_summary}{RST}",
            file=out,
        )
        _show_compliance_trace_to(result_summary, out)

        if not authorized:
            section("QDRO — Denied")
            print(f"  {R}Denied:{RST}  {fap_result.get('denial_reason', '')}")
            print(f"  {DIM}ERISA citation: {fap_result.get('erisa_citation', '')}{RST}")
            print()
            return True

        # Approved — queue for human review
        print(f"\n  {Y}[3]{RST}  {BOLD}Data Agent — queuing for sponsor review{RST}", file=out)
        exec_raw = ExecuteTransactionTool()._run(
            participant_id=participant_id,
            action="qdro",
            payload_json=fap_result["payload_json"],
            fap_token=fap_result["fap_token"],
            autonomy_level="human_review",
        )
        exec_result = _json.loads(exec_raw)

        section("QDRO — Queued for Plan Sponsor Review")
        print(f"  {G}✓  Submitted successfully{RST}")
        print(f"  {BOLD}Participant         {RST}  {fields.get('participant_name')}")
        print(f"  {BOLD}Alternate payee     {RST}  {fields.get('alternate_payee_name')}")
        print(f"  {BOLD}Plan                {RST}  {fields.get('plan_name')}")
        print(f"  {BOLD}Benefit amount      {RST}  {fields.get('benefit_amount_or_pct')}")
        print(f"  {BOLD}Payment period      {RST}  {fields.get('payment_period')}")
        print(f"  {BOLD}Queue entry ID      {RST}  {exec_result.get('queue_entry_id', '—')}")
        print(f"  {BOLD}Audit ID            {RST}  {fap_result.get('audit_id', '—')}")
        print()
        print(f"  {DIM}ERISA § 206(d): Plan sponsor has 18 months to qualify or reject.{RST}")
        print(f"  {DIM}Both you and the alternate payee will be notified of the outcome.{RST}")
        print()
        # Prompt for QDRO court order upload
        entry_id = exec_result.get("queue_entry_id", "")
        if entry_id:
            _prompt_document_upload(participant_id, plan_id, entry_id, "qdro", "qdro")
        return True

    return False


# ---------------------------------------------------------------------------
# Document upload flow — called after a human_review action is queued
# ---------------------------------------------------------------------------

_SAMPLE_DOCS_DIR = _pathlib.Path(__file__).parent.parent / "data" / "sample_docs"

_EXPENSE_DOC_PROMPTS: dict[str, tuple[str, str, str]] = {
    # expense_type → (doc_type, label, sample_filename)
    "medical":               ("medical_bill",    "Medical bill / hospital statement", "medical_bill.txt"),
    "tuition":               ("tuition_invoice", "Tuition invoice",                  "tuition_invoice.txt"),
    "prevent_eviction":      ("eviction_notice", "Eviction or foreclosure notice",   "eviction_notice.txt"),
    "funeral":               ("funeral_invoice", "Funeral home invoice",             "funeral_invoice.txt"),
    "primary_home_purchase": ("purchase_agreement", "Purchase agreement / contractor estimate", None),
    "casualty_loss":         ("insurance_claim", "Insurance claim / damage assessment", None),
    "FEMA_disaster":         ("FEMA_declaration","FEMA declaration document",        None),
    "qdro":                  ("court_order",     "Signed court order (QDRO)",        "qdro_court_order.txt"),
}


def _prompt_document_upload(
    participant_id: str,
    plan_id: str,
    queue_entry_id: str,
    action_type: str,
    expense_type: str,
) -> None:
    """
    Prompt the participant to choose a file, then hand off to the Document Verification
    Agent (inside ParticipantCrew) which uploads and verifies via UploadDocumentTool.
    """
    info = _EXPENSE_DOC_PROMPTS.get(expense_type)
    if not info:
        return   # no document requirement for this expense type

    doc_type, doc_label, sample_filename = info

    print()
    hr("─")
    print(f"\n  {Y}DOCUMENT UPLOAD REQUIRED{RST}")
    print(f"  {DIM}Plan sponsors require supporting documentation before approving this request.{RST}")
    print(f"\n  Required document:  {BOLD}{doc_label}{RST}")
    print()

    sample_path = (_SAMPLE_DOCS_DIR / sample_filename) if sample_filename else None
    if sample_path and sample_path.exists():
        print(f"  {DIM}1{RST}  Use sample document  {DIM}(demo — pre-filled {doc_label}){RST}")
        print(f"  {DIM}2{RST}  Provide file path     {DIM}(enter path to your .txt file){RST}")
        print(f"  {DIM}3{RST}  Skip for now          {DIM}(request stays pending without docs){RST}")
        print()
        try:
            choice = input(f"{G}Enter 1, 2, or 3:{RST} ").strip()
        except EOFError:
            choice = "3"
    else:
        print(f"  {DIM}1{RST}  Provide file path     {DIM}(enter path to your .txt file){RST}")
        print(f"  {DIM}2{RST}  Skip for now          {DIM}(request stays pending without docs){RST}")
        print()
        try:
            choice = input(f"{G}Enter 1 or 2:{RST} ").strip()
        except EOFError:
            choice = "2"
        # remap so "2" → skip regardless of whether sample exists
        if choice == "1":
            choice = "2_filepath"
        else:
            choice = "3"

    if choice == "1" and sample_path:
        file_path = str(sample_path)
    elif choice in ("2", "2_filepath"):
        try:
            file_path = input(f"{G}File path:{RST} ").strip().strip('"\'')
        except EOFError:
            file_path = ""
        if not file_path:
            print(f"\n  {Y}No file provided. Skipping document upload.{RST}\n")
            return
    else:
        print(f"\n  {DIM}Document upload skipped. Your request is in the queue.{RST}")
        print(f"  {DIM}You can upload documents later — sponsors may request them before approving.{RST}\n")
        return

    # Hand off to the Document Verification Agent inside ParticipantCrew
    print(f"\n  {DIM}Document Verification Agent uploading and verifying...{RST}\n")
    from crew.crews.participant_crew import build_document_verification_crew
    doc_crew = build_document_verification_crew(
        participant_id=participant_id,
        plan_id=plan_id,
        queue_entry_id=queue_entry_id,
        action_type=action_type,
        expense_type=expense_type,
        doc_type=doc_type,
        file_path=file_path,
    )
    run_crew(doc_crew, "Document Verification Agent")
    print(f"\n  {DIM}Document is now visible to the plan sponsor in the review queue.{RST}\n")


def run_participant_session():
    from crew.router import route
    from crew.tools.paap_tools import get_supervised_pending, clear_supervised_pending

    header("Participant Self-Service")
    print(f"  {DIM}Your queries go through Intent → Data → Compliance (FAP) → Execute{RST}")
    print(f"  {DIM}All 12 ERISA rules enforced before any write occurs.{RST}")
    print(f"  {DIM}Type {RST}{Y}back{DIM} at any time to return to the main menu.{RST}\n")

    participant_id, plan_id = choose_participant()
    agent_id = "AGENT-PARTICIPANT-001"

    print(f"\n  {G}Logged in as:{RST} {participant_id}  ·  Plan: {plan_id}  ·  Agent: {agent_id}")

    print(f"\n{BOLD}Example queries:{RST}")
    for ex in PARTICIPANT_EXAMPLES:
        print(f"  {DIM}· {ex}{RST}")

    while True:
        print()
        # Show a different prompt when waiting for supervised confirmation
        if get_supervised_pending(participant_id):
            query = input(f"{Y}confirm / cancel >{RST} ").strip()
        else:
            query = input(f"{G}Participant >{RST} ").strip()

        if not query:
            continue
        if query.lower() in ("exit", "quit", "q", "back"):
            clear_supervised_pending(participant_id)
            break

        # Handle supervised confirmation before routing to crew
        if get_supervised_pending(participant_id):
            if query.lower() == "confirm":
                _execute_supervised_confirmed(participant_id)
                continue
            elif query.lower() == "cancel":
                clear_supervised_pending(participant_id)
                print(f"\n  {Y}Transaction cancelled.{RST}")
                continue
            else:
                # User typed something new — clear the pending transaction first
                clear_supervised_pending(participant_id)
                print(f"\n  {DIM}Pending transaction cleared. Processing new query...{RST}")

        # Fast-path: instant reads without LLM round-trip
        if _participant_fast_read(query, participant_id, plan_id):
            continue

        crew = route(
            principal_type="participant",
            query=query,
            participant_id=participant_id,
            plan_id=plan_id,
            agent_id=agent_id,
        )
        run_crew(crew, f"Participant · {participant_id}")

        # If the crew left a supervised transaction pending, show the confirmation panel
        if get_supervised_pending(participant_id):
            show_supervised_panel(participant_id, get_supervised_pending(participant_id))

        # After the crew queues a human_review action, check if a new queue entry
        # was created that needs documents (hardship only — QDRO has its own fast path).
        _doc_actions = {"hardship_distribution"}
        q_lower = query.lower()
        if any(w in q_lower for w in ["hardship", "medical", "eviction", "tuition", "funeral",
                                       "casualty", "fema", "home repair", "prevent eviction"]):
            from data.review_queue import get_all as _get_all, reload as _rq_reload
            _rq_reload()
            recent = [
                e for e in _get_all()
                if e.participant_id == participant_id
                and e.action in _doc_actions
                and e.status == "pending"
            ]
            if recent:
                latest = recent[-1]
                # Only prompt if no docs yet uploaded for this entry
                from data import document_store as _ds
                _ds.reload()
                if not _ds.get_by_entry(latest.entry_id):
                    payload = latest.payload or {}
                    expense = payload.get("qualifying_expense_type") or payload.get("expense_type", "medical")
                    _prompt_document_upload(participant_id, plan_id, latest.entry_id,
                                            latest.action, expense)


# ---------------------------------------------------------------------------
# Plan Sponsor session
# ---------------------------------------------------------------------------

SPONSOR_EXAMPLES = [
    "queue                                   ← instant: pending review items + doc status",
    "audit                                   ← instant: FAP audit log",
    "blackout status                         ← instant: blackout state",
    "docs A1B2C3D4                          ← instant: document summary + LLM verification",
    "open doc A1B2C3D4 1                   ← instant: read full document text",
    "approve doc A1B2C3D4                   ← instant: approve documents (required before approving request)",
    "Approve A1B2C3D4 — valid medical docs  ← instant: approve request (only after approve doc)",
    "Deny A1B2C3D4 — insufficient docs      ← instant (no LLM)",
    "reset                                   ← instant: clear queue + documents for a fresh demo",
    "Activate a blackout from 2026-08-15 to 2026-09-01 for recordkeeper transition",
    "What does our plan allow for hardship distributions?",
]


# ---------------------------------------------------------------------------
# Sponsor fast-path — direct tool calls for read-only queries (no LLM round-trip)
# ---------------------------------------------------------------------------

def _sponsor_fast_read(query: str, plan_id: str) -> bool:
    """
    Detect and handle common read-only sponsor queries directly without CrewAI.
    Returns True if handled, False if it should go through the crew.
    """
    import json as _json
    q = query.lower().strip()

    # Queue view
    if q in ("queue", "q", "pending", "show queue", "show pending") or (
        any(w in q for w in ["queue", "pending", "review"]) and
        not any(w in q for w in ["approve", "deny", "reject"])
    ):
        from crew.tools.admin_tools import GetPendingReviewsTool
        tool = GetPendingReviewsTool()
        raw = tool._run(plan_id=plan_id)
        data = _json.loads(raw)
        section(f"Pending Queue — {plan_id}")
        count = data.get("pending_count", 0)
        if count == 0:
            print(f"  {G}Queue is empty{RST} — no items awaiting sponsor review.")
        else:
            from data import document_store as _ds
            _ds.reload()
            print(f"  {Y}{count} item{'s' if count != 1 else ''} awaiting review:{RST}\n")
            for e in data.get("entries", []):
                action_str = e["action"].replace("_", " ").title()
                payload = e.get("payload", {})
                amt = payload.get("amount", "")
                amt_str = f"  ${float(amt):,.0f}" if amt else ""
                docs = _ds.get_by_entry(e["entry_id"])
                needs_docs = e["action"] in ("hardship_distribution", "qdro")
                if docs:
                    sponsor_approved = sum(1 for d in docs if d.sponsor_doc_approved)
                    llm_verified = sum(1 for d in docs if d.verified)
                    n = len(docs)
                    doc_str = f"  📎 {n} doc{'s' if n>1 else ''}"
                    if sponsor_approved == n:
                        doc_str = f"  {G}📎 {n} doc{'s' if n>1 else ''}  (sponsor approved ✓){RST}"
                    elif llm_verified > 0:
                        doc_str = f"  {Y}📎 {n} doc{'s' if n>1 else ''}  (LLM verified · awaiting your review){RST}"
                    else:
                        doc_str = f"  {Y}📎 {n} doc{'s' if n>1 else ''}  (verification failed){RST}"
                elif needs_docs:
                    doc_str = f"  {Y}⚠ no documents uploaded{RST}"
                else:
                    doc_str = ""
                print(f"  [{G}{e['entry_id']}{RST}]  {e['participant_id']}  {C}{action_str}{RST}{amt_str}{doc_str}")
                print(f"         queued: {DIM}{e['created_at']}{RST}")
                if needs_docs:
                    print(f"         {DIM}→ docs {e['entry_id']}  |  approve doc {e['entry_id']}  |  Approve {e['entry_id']} — note  |  Deny {e['entry_id']} — reason{RST}")
                else:
                    print(f"         {DIM}→ Approve {e['entry_id']} — note  |  Deny {e['entry_id']} — reason{RST}")
                print()
        print()
        return True

    # Audit log
    if q in ("audit", "audit log", "log") or "audit" in q:
        from crew.tools.fap_tools import GetAuditLogTool
        tool = GetAuditLogTool()
        raw = tool._run(limit=10)
        data = _json.loads(raw)
        section("FAP Audit Log (last 10)")
        entries = data.get("entries", [])
        if not entries:
            print(f"  {DIM}No audit entries yet.{RST}")
        for e in entries:
            approved = e.get("authorized")
            symbol = f"{G}✓{RST}" if approved else f"{R}✗{RST}"
            action_str = (e.get("action") or "").replace("_", " ")
            level = e.get("autonomy_level") or ""
            denial = e.get("denial_code") or ""
            detail = level if approved else denial
            print(f"  {symbol}  {DIM}{e['timestamp'][:19]}{RST}  {e['participant_id']}  {C}{action_str}{RST}  {DIM}{detail}{RST}")
        print()
        return True

    # Blackout status
    if q in ("blackout", "blackout status", "blackout?") or (
        "blackout" in q and any(w in q for w in ["status", "current", "active", "check", "is"])
    ):
        from crew.tools.admin_tools import ManageBlackoutTool
        tool = ManageBlackoutTool()
        raw = tool._run(plan_id=plan_id, operation="status")
        data = _json.loads(raw)
        section(f"Blackout Status — {plan_id}")
        active = data.get("blackout_active", False)
        if active:
            print(f"  {R}BLACKOUT ACTIVE{RST}")
            print(f"  Start:  {data.get('start_date', '—')}")
            print(f"  End:    {data.get('end_date', '—')}")
            print(f"  Reason: {data.get('reason', '—')}")
        else:
            print(f"  {G}No active blackout{RST} — all participant writes permitted.")
        print()
        return True

    # Open doc — show full document text for a specific document number
    # Usage: open doc AB064BBC 1   (doc number from the docs listing)
    if q.startswith("open doc") or q.startswith("view doc"):
        prefix = "open doc" if q.startswith("open doc") else "view doc"
        rest = query[len(prefix):].strip().upper().split()
        if not rest:
            print(f"\n  {Y}Usage:{RST}  open doc <entry_id> <doc_number>")
            print(f"  {DIM}Example:  open doc AB064BBC 1{RST}\n")
            return True
        entry_id = rest[0]
        doc_num = int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else 1
        from data import document_store as _ds
        _ds.reload()
        docs = _ds.get_by_entry(entry_id)
        if not docs:
            print(f"\n  {Y}No documents for entry {entry_id}.{RST}\n")
            return True
        if doc_num < 1 or doc_num > len(docs):
            print(f"\n  {Y}Document {doc_num} not found — entry has {len(docs)} document(s).{RST}\n")
            return True
        d = docs[doc_num - 1]
        doc_label = _ds.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type)
        llm_sym = f"{G}✓ LLM verified{RST}" if d.verified else f"{Y}⚠ LLM check failed{RST}"
        sponsor_sym = f"{G}✓ You approved{RST}" if d.sponsor_doc_approved else f"{Y}Awaiting your approval{RST}"
        section(f"Document [{doc_num}] — {entry_id}")
        print(f"  {BOLD}Type        {RST}  {doc_label}")
        print(f"  {BOLD}File        {RST}  {d.filename}  ·  uploaded {d.uploaded_at[:10]}")
        print(f"  {BOLD}LLM check   {RST}  {llm_sym}")
        if d.verification_note:
            print(f"  {BOLD}LLM note    {RST}  {DIM}{d.verification_note}{RST}")
        print(f"  {BOLD}Sponsor     {RST}  {sponsor_sym}")
        print()
        print(f"  {DIM}{'─' * 54}{RST}")
        for line in d.content_text.splitlines():
            print(f"  {line}")
        print(f"  {DIM}{'─' * 54}{RST}")
        print()
        if not d.sponsor_doc_approved:
            print(f"  {DIM}approve doc {entry_id}   ← approve after reading{RST}")
        print()
        return True

    # Docs view — summary of uploaded documents for a queue entry
    if q.startswith("docs"):
        rest = query[4:].strip().upper()
        if not rest:
            print(f"\n  {Y}Specify the entry ID:{RST}  docs <entry_id>")
            print(f"  {DIM}Example:  docs AB064BBC{RST}\n")
            return True
        from data import document_store as _ds
        _ds.reload()
        docs = _ds.get_by_entry(rest)
        section(f"Documents — {rest}")
        if not docs:
            print(f"  {Y}No documents uploaded for entry {rest}.{RST}")
            print(f"  {DIM}Participant has not yet uploaded supporting documents.{RST}")
        else:
            for i, d in enumerate(docs, 1):
                doc_label = _ds.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type)
                llm_sym = f"{G}✓ LLM verified{RST}" if d.verified else f"{Y}⚠ LLM check failed{RST}"
                if d.sponsor_doc_approved:
                    sponsor_sym = f"{G}✓ You approved{RST}"
                    if d.sponsor_doc_note:
                        sponsor_sym += f"  {DIM}(\"{d.sponsor_doc_note}\"){RST}"
                else:
                    sponsor_sym = f"{Y}Awaiting your approval{RST}"
                print(f"  {BOLD}[{i}] {doc_label}{RST}")
                print(f"      {BOLD}LLM check   {RST}  {llm_sym}")
                if d.verification_note:
                    print(f"      {BOLD}LLM note    {RST}  {DIM}{d.verification_note}{RST}")
                print(f"      {BOLD}Sponsor     {RST}  {sponsor_sym}")
                print(f"      {BOLD}File        {RST}  {d.filename}  ·  uploaded {d.uploaded_at[:10]}")
                print(f"      {BOLD}Preview     {RST}  {DIM}{d.content_text[:150].strip()}...{RST}")
                print(f"      {DIM}open doc {rest} {i}   ← read full document{RST}")
                print()
            if not any(d.sponsor_doc_approved for d in docs):
                print(f"  {DIM}──────────────────────────────────────────────────────{RST}")
                print(f"  {Y}Documents awaiting your review.{RST}")
                print(f"  {DIM}Run:  approve doc {rest}          ← approve the documents{RST}")
                print(f"  {DIM}Then: Approve {rest} — note  ← approve the request{RST}")
                print()
        print()
        return True

    # Approve document — sponsor explicitly reviews and approves the uploaded documents
    # Must come BEFORE the general approve handler so "approve doc" is caught first
    if q.startswith("approve doc") or q.startswith("approve document"):
        prefix = "approve doc" if q.startswith("approve doc") else "approve document"
        rest = query[len(prefix):].strip()
        if not rest:
            print(f"\n  {Y}Specify the entry ID:{RST}  approve doc <entry_id>")
            print(f"  {DIM}Example:  approve doc AB064BBC{RST}\n")
            return True
        if "—" in rest:
            parts = rest.split("—", 1)
        elif " - " in rest:
            parts = rest.split(" - ", 1)
        else:
            parts = [rest, ""]
        entry_id = parts[0].strip().upper()
        note = parts[1].strip() if len(parts) > 1 and parts[1].strip() else ""
        from data import document_store as _ds
        from datetime import datetime, timezone
        _ds.reload()
        docs = _ds.get_by_entry(entry_id)
        section(f"Document Approval — {plan_id}")
        if not docs:
            print(f"  {Y}No documents found for entry {entry_id}.{RST}")
            print(f"  {DIM}Participant has not uploaded supporting documents yet.{RST}")
        else:
            now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            updated = _ds.approve_by_sponsor(entry_id=entry_id, note=note, approved_at=now)
            for d in updated:
                doc_label = _ds.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type)
                print(f"  {G}✓  Document approved{RST}  {BOLD}{doc_label}{RST}  ({d.filename})")
                if note:
                    print(f"     {BOLD}Note      {RST}  \"{note}\"")
            print(f"\n  {DIM}Documents approved. You may now approve the request:{RST}")
            print(f"  {DIM}  Approve {entry_id} — <your note>{RST}")
        print()
        return True

    # Approve request — fast path (no LLM needed)
    if q.startswith("approve"):
        rest = query[len("approve"):].strip()
        if not rest:
            print(f"\n  {Y}Specify the entry ID:{RST}  Approve <entry_id> — <note>")
            print(f"  {DIM}Example:  Approve AB064BBC — valid medical documentation{RST}\n")
            return True
        # parse "AB064BBC — sponsor note" or "AB064BBC sponsor note"
        if "—" in rest:
            parts = rest.split("—", 1)
        elif " - " in rest:
            parts = rest.split(" - ", 1)
        else:
            parts = rest.split(None, 1)
        entry_id = parts[0].strip().upper()
        note = parts[1].strip() if len(parts) > 1 else ""

        # For hardship and QDRO: block approval until sponsor has explicitly approved the documents
        _ACTIONS_REQUIRING_DOCS = {"hardship_distribution", "qdro"}
        from data import review_queue as _rq_check
        from data import document_store as _ds_check
        _rq_check.reload()
        _ds_check.reload()
        _entry_check = _rq_check.get_entry(entry_id)
        if _entry_check and _entry_check.action in _ACTIONS_REQUIRING_DOCS:
            _docs_on_file = _ds_check.get_by_entry(entry_id)
            _sponsor_approved_docs = [d for d in _docs_on_file if d.sponsor_doc_approved]
            if not _sponsor_approved_docs:
                section(f"Approval Blocked — {plan_id}")
                action_label = _entry_check.action.replace("_", " ").title()
                print(f"  {Y}⚠  Cannot approve — documents not yet reviewed.{RST}")
                print(f"  {DIM}{action_label} requires you to review and approve the documents first.{RST}")
                print()
                if _docs_on_file:
                    _llm_verified = [d for d in _docs_on_file if d.verified]
                    if _llm_verified:
                        print(f"  {DIM}Step 1:  docs {entry_id}              ← read the documents{RST}")
                        print(f"  {DIM}Step 2:  approve doc {entry_id}       ← approve the documents{RST}")
                        print(f"  {DIM}Step 3:  Approve {entry_id} — note    ← approve the request{RST}")
                    else:
                        print(f"  {Y}  {len(_docs_on_file)} document(s) uploaded but LLM verification failed.{RST}")
                        print(f"  {DIM}  Review the docs manually: docs {entry_id}{RST}")
                        print(f"  {DIM}  Then: approve doc {entry_id}  →  Approve {entry_id} — note{RST}")
                else:
                    print(f"  {DIM}  No documents uploaded yet.{RST}")
                    print(f"  {DIM}  Switch to Participant → submit the request again → upload docs when prompted.{RST}")
                print()
                return True

        from crew.tools.admin_tools import ApproveRequestTool
        raw = ApproveRequestTool()._run(entry_id=entry_id, sponsor_note=note)
        result = _json.loads(raw)
        section(f"Approval — {plan_id}")
        if "error" in result:
            print(f"  {R}✗  {result['error']}{RST}\n")
        else:
            payload = result.get("payload", {})
            amt = payload.get("amount", "")
            amt_str = f"  ${float(amt):,.0f}" if amt else ""
            action_str = result.get("action", "").replace("_", " ").title()
            print(f"  {G}✓  APPROVED{RST}  [{G}{entry_id}{RST}]")
            print(f"  {BOLD}Participant {RST}  {result.get('participant_id')}")
            print(f"  {BOLD}Action      {RST}  {action_str}{amt_str}")
            if note:
                print(f"  {BOLD}Note        {RST}  \"{note}\"")
            print(f"  {BOLD}Audit trail {RST}  recorded — ERISA §107")
            print(f"  {DIM}  Production: PAAP re-issues FAP token and executes immediately.{RST}")
        print()
        return True

    # Deny request — fast path (no LLM needed)
    if q.startswith("deny") or q.startswith("reject"):
        prefix = "deny" if q.startswith("deny") else "reject"
        rest = query[len(prefix):].strip()
        if not rest:
            print(f"\n  {Y}Specify the entry ID and reason:{RST}  Deny <entry_id> — <reason>")
            print(f"  {DIM}Example:  Deny AB064BBC — insufficient documentation provided{RST}\n")
            return True
        if "—" in rest:
            parts = rest.split("—", 1)
        elif " - " in rest:
            parts = rest.split(" - ", 1)
        else:
            parts = rest.split(None, 1)
        entry_id = parts[0].strip().upper()
        note = parts[1].strip() if len(parts) > 1 else ""
        from crew.tools.admin_tools import DenyRequestTool
        raw = DenyRequestTool()._run(entry_id=entry_id, sponsor_note=note)
        result = _json.loads(raw)
        section(f"Denial — {plan_id}")
        if "error" in result:
            print(f"  {R}✗  {result['error']}{RST}\n")
        else:
            payload = result.get("payload", {})
            amt = payload.get("amount", "")
            amt_str = f"  ${float(amt):,.0f}" if amt else ""
            action_str = result.get("action", "").replace("_", " ").title()
            print(f"  {R}✗  DENIED{RST}  [{DIM}{entry_id}{RST}]")
            print(f"  {BOLD}Participant {RST}  {result.get('participant_id')}")
            print(f"  {BOLD}Action      {RST}  {action_str}{amt_str}")
            if note:
                print(f"  {BOLD}Reason      {RST}  \"{note}\"")
            print(f"  {BOLD}Audit trail {RST}  recorded — ERISA §107")
            print(f"  {DIM}  Participant will be notified of denial.{RST}")
        print()
        return True

    # Reset — clear queue and documents for a fresh demo
    if q in ("reset", "clear", "reset demo", "clear demo"):
        from data import review_queue as _rq
        from data import document_store as _ds
        _rq.reload()
        _ds.reload()
        pending = len(_rq.get_pending())
        total_docs = len(_ds._store)
        _rq._queue.clear()
        _rq._save()
        _ds.clear_all()
        section("Demo Reset")
        print(f"  {G}✓  Queue cleared{RST}  ({pending} pending entr{'ies' if pending != 1 else 'y'} removed)")
        print(f"  {G}✓  Documents cleared{RST}")
        print(f"  {DIM}Fresh demo state — ready for a new run.{RST}")
        print()
        return True

    return False


def run_sponsor_session():
    from crew.router import route

    header("Plan Sponsor Administration")
    print(f"  {DIM}Manage the human review queue, blackouts, and audit log.{RST}")
    print(f"  {DIM}ERISA § 404 fiduciary duties apply to every decision.{RST}")
    print(f"  {DIM}Type {RST}{Y}back{DIM} at any time to return to the main menu.{RST}\n")

    plan_id = choose_plan()
    agent_id = "AGENT-SPONSOR-001"

    print(f"\n  {G}Logged in as:{RST} Plan Sponsor  ·  Plan: {plan_id}  ·  Agent: {agent_id}")

    print(f"\n{BOLD}Example commands:{RST}")
    for ex in SPONSOR_EXAMPLES:
        print(f"  {DIM}· {ex}{RST}")

    while True:
        print()
        query = input(f"{M}Sponsor >{RST} ").strip()
        if not query:
            continue
        if query.lower() in ("exit", "quit", "q", "back"):
            break

        # Fast-path: instant read without LLM round-trip
        if _sponsor_fast_read(query, plan_id):
            continue

        crew = route(
            principal_type="plan_sponsor",
            query=query,
            plan_id=plan_id,
            agent_id=agent_id,
        )
        run_crew(crew, f"Plan Sponsor · {plan_id}")


# ---------------------------------------------------------------------------
# Investment Advisor session
# ---------------------------------------------------------------------------

ADVISOR_EXAMPLES = [
    "Show me the fund lineup for this plan",
    "What are my client's current investment elections?",
    "Reallocate my client to 70% FIDELITY-500 and 30% VANGUARD-TDF-2040",
    "Change my client's deferral to 10% pre-tax",
    "Recommend a rebalance to the target-date fund",
]


def run_advisor_session():
    from crew.router import route

    header("Investment Advisor Portal")
    print(f"  {DIM}Submit investment recommendations for client accounts.{RST}")
    print(f"  {DIM}Scope: investment_reallocation and deferral_change only.{RST}")
    print(f"  {DIM}All recommendations require participant confirmation (supervised autonomy).{RST}\n")

    print(f"{BOLD}Select client:{RST}")
    participant_id, plan_id = choose_participant()
    agent_id = "AGENT-ADVISOR-001"

    # Advisor is registered for PLAN-003 (Capital One) only
    if plan_id not in ("PLAN-003",):
        print(f"\n{R}  AGENT-ADVISOR-001 is not registered for {plan_id}.{RST}")
        print(f"  {DIM}Advisor scope covers PLAN-003 (Capital One). Select a Capital One participant.{RST}")
        return

    print(f"\n  {G}Logged in as:{RST} Advisor  ·  Client: {participant_id}  ·  Plan: {plan_id}")

    print(f"\n{BOLD}Example queries:{RST}")
    for ex in ADVISOR_EXAMPLES:
        print(f"  {DIM}· {ex}{RST}")

    while True:
        print()
        query = input(f"{C}Advisor >{RST} ").strip()
        if not query:
            continue
        if query.lower() in ("exit", "quit", "q", "back"):
            break

        crew = route(
            principal_type="investment_advisor",
            query=query,
            participant_id=participant_id,
            plan_id=plan_id,
            agent_id=agent_id,
        )
        run_crew(crew, f"Advisor · Client {participant_id}")


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main():
    header("Aldergate  ·  ERISA 401(k)  ·  CrewAI Agent Interface")

    print(f"  {DIM}PLAP → FAP (12 rules) → PAAP  ·  LLM interprets, Python decides compliance.{RST}")
    print(f"  {DIM}ParticipantCrew · SponsorCrew  ·  Intent Agent · Data Agent · Compliance Agent{RST}\n")

    hr()

    ROLES = [
        ("participant", "Participant  — loans · deferrals · investments · distributions"),
        ("plan_sponsor", "Plan Sponsor — approve queue · blackouts · audit log"),
        ("quit", "Exit"),
    ]

    while True:
        role = pick("Select your role:", ROLES)

        if role == "quit":
            print(f"\n{DIM}  Session ended.{RST}\n")
            break
        elif role == "participant":
            run_participant_session()
        elif role == "plan_sponsor":
            run_sponsor_session()


if __name__ == "__main__":
    try:
        main()
    except EnvironmentError as e:
        print(f"\n{R}{e}{RST}")
        sys.exit(1)
    except KeyboardInterrupt:
        print(f"\n\n{DIM}  Interrupted.{RST}\n")
        sys.exit(0)
