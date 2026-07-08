"""
Plan Sponsor Crew — handles all administrative duties for the plan sponsor / HR admin.

Plan sponsor duties covered here:
  1. Review and approve/deny the human_review queue (hardship, QDRO, RMD, beneficiary, separation)
  2. Manage blackout periods (with mandatory 30-day participant notice per ERISA § 101(i))
  3. View FAP audit log (ERISA § 107 — 6-year retention requirement)
  4. Query plan configuration

What the sponsor CANNOT do here:
  - Initiate or modify participant transactions directly (only approve/deny queued ones)
  - See participant PII beyond what's in the review queue (no DOB, SSN, marital status)

Entry point: build_sponsor_crew(context) → Crew
"""

from crewai import Agent, Task, Crew, Process

from crew.agents.base import fap_llm
from crew.tools.plap_tools import GetPlanRulesTool
from crew.tools.fap_tools import GetAuditLogTool
from crew.tools.admin_tools import (
    GetPendingReviewsTool,
    ApproveRequestTool,
    DenyRequestTool,
    ManageBlackoutTool,
)


def build_sponsor_crew(
    plan_id: str,
    sponsor_agent_id: str,
    query: str,
) -> Crew:
    """
    Build and return a configured plan sponsor crew for a given admin session.
    """

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------

    admin_intent_agent = Agent(
        role="Plan Administrator",
        goal=(
            "Understand what the plan sponsor needs to do — whether that's reviewing pending requests, "
            "managing blackouts, checking the audit log, or querying plan configuration. "
            "Summarize the outcome clearly for the sponsor."
        ),
        backstory=(
            "You assist plan sponsors (HR administrators, plan trustees) with their ERISA fiduciary duties. "
            "You understand that the plan sponsor has the authority to approve or deny participant requests "
            "that require human review — but cannot unilaterally change participant balances or override FAP. "
            "You ensure every admin action is properly documented in the audit trail. "
            "ERISA § 404 fiduciary duties: act solely in participants' interest, with prudence."
        ),
        tools=[],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    admin_data_agent = Agent(
        role="Plan Administration Data Specialist",
        goal=(
            "Fetch the pending review queue, plan configuration, or audit log data needed "
            "to help the plan sponsor make informed decisions."
        ),
        backstory=(
            "You have access to the review queue, plan rules, and FAP audit log. "
            "You do not have access to participant transaction tools — those are for participant sessions only. "
            "You surface the data the sponsor needs to exercise their fiduciary duties."
        ),
        tools=[
            GetPendingReviewsTool(),
            GetPlanRulesTool(),
            GetAuditLogTool(),
        ],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    admin_action_agent = Agent(
        role="Plan Sponsor Action Executor",
        goal=(
            "Execute administrative decisions: approve or deny queued participant requests, "
            "manage blackout periods, and update plan configuration within ERISA constraints."
        ),
        backstory=(
            "You execute plan sponsor decisions. Every approval or denial is recorded in the audit log. "
            "For blackouts: ERISA § 101(i) requires 30-day advance notice — you enforce this requirement. "
            "For queue decisions: you approve or deny with a note that becomes part of the permanent record."
        ),
        tools=[
            ApproveRequestTool(),
            DenyRequestTool(),
            ManageBlackoutTool(),
        ],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    # -------------------------------------------------------------------------
    # Tasks
    # -------------------------------------------------------------------------

    task_interpret_admin = Task(
        description=(
            f"Plan sponsor query: \"{query}\"\n\n"
            f"Plan ID: {plan_id}\n"
            f"Sponsor Agent ID: {sponsor_agent_id}\n\n"
            "Classify what the sponsor wants to do:\n"
            "1. VIEW_QUEUE — review pending participant requests\n"
            "2. APPROVE — approve a specific queue entry (needs entry_id)\n"
            "3. DENY — deny a specific queue entry (needs entry_id and reason)\n"
            "4. BLACKOUT — activate, deactivate, or check blackout status\n"
            "5. AUDIT_LOG — view recent FAP decisions\n"
            "6. PLAN_CONFIG — view plan rules and configuration\n"
            "7. QUERY_ONLY — general question about the plan\n\n"
            "Identify all parameters: entry_id (if approval/denial), blackout dates, reason, etc."
        ),
        expected_output=(
            "A structured admin intent: intent_type (one of the 7 above), "
            "extracted parameters, and any missing fields that prevent proceeding."
        ),
        agent=admin_intent_agent,
    )

    task_fetch_admin_data = Task(
        description=(
            "You MUST call the appropriate tool — do NOT answer from memory or make up queue contents.\n\n"
            "Based on the intent type from the previous task:\n"
            f"- VIEW_QUEUE or APPROVE/DENY: call GetPendingReviews with plan_id='{plan_id}'\n"
            "- AUDIT_LOG: call GetAuditLog\n"
            f"- PLAN_CONFIG: call GetPlanRules with plan_id='{plan_id}'\n"
            f"- BLACKOUT status: call ManageBlackout with plan_id='{plan_id}', operation='status'\n"
            "- QUERY_ONLY: call the most relevant tool (GetPendingReviews or GetPlanRules)\n\n"
            "If the sponsor asked about the queue, you MUST call GetPendingReviews — the queue is live data "
            "and only the tool returns the actual current state. Never say '0 items' without calling the tool."
        ),
        expected_output=(
            "The raw tool output — actual data from GetPendingReviews, GetAuditLog, or GetPlanRules. "
            "Do not summarize or invent — return exactly what the tool returned."
        ),
        agent=admin_data_agent,
        context=[task_interpret_admin],
    )

    task_execute_admin = Task(
        description=(
            "If the intent requires an action (APPROVE, DENY, or BLACKOUT activate/deactivate), execute it now:\n"
            "- APPROVE: call ApproveRequest with entry_id and sponsor_note\n"
            "- DENY: call DenyRequest with entry_id and sponsor_note (denial reason required)\n"
            "- BLACKOUT activate: call ManageBlackout with operation='activate', start_date, end_date, reason\n"
            "- BLACKOUT deactivate: call ManageBlackout with operation='deactivate'\n"
            "- VIEW_QUEUE, AUDIT_LOG, PLAN_CONFIG, QUERY_ONLY: no action needed — output 'no_action_taken'\n\n"
            "Include a meaningful sponsor_note for every approval or denial — it is the ERISA audit trail."
        ),
        expected_output=(
            "Action execution result: what was done, the outcome, and any ERISA compliance notes "
            "(e.g. blackout notice requirement). Or 'no_action_taken' if intent was read-only."
        ),
        agent=admin_action_agent,
        context=[task_interpret_admin, task_fetch_admin_data],
    )

    task_respond_admin = Task(
        description=(
            "Write a SHORT, DIRECT response — 3 to 5 lines maximum.\n\n"
            "Rules:\n"
            "- NO markdown tables, NO headers, NO ERISA paragraph explanations\n"
            "- NO explaining why you did or did not do something\n"
            "- Just report what happened and what is next\n\n"
            "Format by intent type:\n"
            "  APPROVE/DENY: one line confirming the decision + entry ID, "
            "one line with participant + action + amount, one line: audit trail recorded.\n"
            "  BLACKOUT activate: confirm dates + cite ERISA §101(i) 30-day notice in one line.\n"
            "  BLACKOUT deactivate: confirm lifted, one line.\n"
            "  VIEW_QUEUE: list entries as: [ID]  participant  action  amount. "
            "If queue is empty say so in one line.\n"
            "  AUDIT_LOG: list entries as: ✓/✗  date  participant  action  outcome.\n"
            "  PLAN_CONFIG / QUERY_ONLY: answer in 1–3 sentences, plain text only.\n\n"
            "Example for approval:\n"
            "  Approved [AB064BBC] — hardship distribution $5,000 for PART-001.\n"
            "  Sponsor note recorded in audit log (ERISA §107). PAAP will execute."
        ),
        expected_output=(
            "A short, direct 3–5 line plain-text response. No markdown, no tables, no headers."
        ),
        agent=admin_intent_agent,
        context=[task_interpret_admin, task_fetch_admin_data, task_execute_admin],
    )

    # -------------------------------------------------------------------------
    # Crew assembly
    # -------------------------------------------------------------------------

    return Crew(
        agents=[admin_intent_agent, admin_data_agent, admin_action_agent],
        tasks=[
            task_interpret_admin,
            task_fetch_admin_data,
            task_execute_admin,
            task_respond_admin,
        ],
        process=Process.sequential,
        verbose=False,
    )
