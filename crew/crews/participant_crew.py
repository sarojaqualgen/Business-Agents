"""
Participant Crew — handles all self-service actions for a plan participant.

Agents:
  - Intent Agent       : parses the participant's natural-language query into a structured intent;
                         formats the final participant-facing response
  - Data Agent         : fetches plan rules + participant summary (read-only PLAP/PAAP tools)
  - Compliance Agent   : runs all 12 ERISA rules via FAP and issues/denies a token
  - Transaction Agent  : executes the approved transaction via ExecuteTransaction (write-only PAAP)

Separating Data Agent (reads) from Transaction Agent (writes) enforces the ERISA principle
that data retrieval and execution are distinct fiduciary acts.

Entry point: build_participant_crew(context) → Crew
"""

import json
import re

from crewai import Agent, Task, Crew, Process

from crew.agents.base import fap_llm


def _extract_qdro_payload(query: str) -> str | None:
    """
    Parse QDRO fields from the participant's message in Python so the LLM
    never has to extract them. Returns a ready-to-use payload_json string
    if all 5 required fields are found, otherwise None.
    """
    fields: dict[str, str] = {}

    patterns = [
        ("participant_name",     r"[Pp]articipant(?:\s+name)?[:\s]+([^\n.]+)"),
        ("alternate_payee_name", r"[Aa]lternate\s+payee(?:\s+name)?[:\s]+([^\n.]+)"),
        ("plan_name",            r"[Pp]lan[:\s]+([^\n.]+)"),
        ("benefit_amount_or_pct",r"[Aa]mount[:\s]+([^\n.]+)"),
        ("payment_period",       r"[Pp]ayment\s+period[:\s]+([^\n.]+)"),
    ]

    for key, pattern in patterns:
        m = re.search(pattern, query)
        if m:
            fields[key] = m.group(1).strip().rstrip(".,;")

    if len(fields) == 5:
        return json.dumps(fields)
    return None
from crew.tools.plap_tools import GetPlanRulesTool, GetFundLineupTool
from crew.tools.paap_tools import GetParticipantSummaryTool, GetLoanHeadroomTool, ExecuteTransactionTool
from crew.tools.fap_tools import RunComplianceCheckTool, GetAuditLogTool
from crew.tools.document_tools import UploadDocumentTool


def build_participant_crew(
    participant_id: str,
    plan_id: str,
    agent_id: str,
    query: str,
) -> Crew:
    """
    Build and return a configured participant crew for a given session context.
    Call crew.kickoff() on the returned Crew — no extra inputs needed.
    """

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------

    intent_agent = Agent(
        role="ERISA Participant Service Specialist",
        goal=(
            "Understand exactly what the participant wants to do with their retirement account, "
            "then translate that into a structured action request (action type + parameters). "
            "At the end, summarize the outcome in plain English."
        ),
        backstory=(
            "You are a knowledgeable ERISA specialist who helps retirement plan participants "
            "navigate their 401(k) options. You understand participant rights, available actions, "
            "and how to communicate compliance decisions clearly and compassionately. "
            "You NEVER make compliance decisions yourself — that is FAP's job. "
            "Valid actions: loan_initiation, deferral_change, investment_reallocation, "
            "hardship_distribution, in_service_distribution, separation_distribution, "
            "rmd, beneficiary_update, qdro."
        ),
        tools=[],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    data_agent = Agent(
        role="Retirement Account Data Specialist",
        goal=(
            "Fetch the plan rules and participant data needed to evaluate the requested action. "
            "Return exactly what the compliance check needs — nothing more."
        ),
        backstory=(
            "You have read-only access to the Plan Rules Module (PLAP) and the "
            "Participant Data Module (PAAP). You retrieve plan configuration and participant account "
            "summaries for the compliance check. You never expose SSNs, dates of birth, marital status, "
            "or full account balances in your output. You do NOT execute transactions — that is the "
            "Transaction Agent's sole responsibility."
        ),
        tools=[
            GetPlanRulesTool(),
            GetFundLineupTool(),
            GetParticipantSummaryTool(),
            GetLoanHeadroomTool(),
        ],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    transaction_agent = Agent(
        role="ERISA Transaction Executor",
        goal=(
            "Execute PAAP-level participant transactions once FAP has issued a valid authorization token. "
            "Route human_review actions to the plan sponsor queue."
        ),
        backstory=(
            "You are the execution arm of the participant workflow. You receive a valid FAP token from "
            "the compliance step and call ExecuteTransaction with the correct action and payload. "
            "You have no read tools — you cannot fetch plan rules or participant data. "
            "Your only job is to execute or queue what FAP has already authorized. "
            "If FAP denied the request, you do nothing and pass the denial through."
        ),
        tools=[ExecuteTransactionTool()],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    compliance_agent = Agent(
        role="ERISA Fiduciary Compliance Officer",
        goal=(
            "Run the full 12-rule FAP compliance check for every proposed participant transaction. "
            "Issue an authorization token if all rules pass, or return a clear denial with the specific rule violated."
        ),
        backstory=(
            "You are the compliance gate for all participant transactions. "
            "You have access ONLY to RunComplianceCheck — you cannot fetch participant data directly "
            "or execute transactions. This separation ensures no compliance shortcuts. "
            "You run FAP, report the result, and hand the token (or denial) back to the crew. "
            "All 12 ERISA rules must be evaluated; FAP stops at the first failure."
        ),
        tools=[RunComplianceCheckTool()],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    # -------------------------------------------------------------------------
    # Tasks (sequential — each feeds context to the next)
    # -------------------------------------------------------------------------

    task_interpret = Task(
        description=(
            f"Participant query: \"{query}\"\n\n"
            f"Participant ID: {participant_id}\n"
            f"Plan ID: {plan_id}\n"
            f"Agent ID: {agent_id}\n\n"
            "Parse the participant's query and identify:\n"
            "1. The intended action (one of the valid ActionType values)\n"
            "2. All required parameters for that action\n"
            "3. Any ambiguities that need resolving (e.g. missing loan amount, missing fund IDs)\n\n"
            "Output a structured summary: action name, parameters extracted, and any clarifying questions "
            "if the query is incomplete. If the query is a question (not a transaction request), "
            "note that no compliance check is needed — just answer using the data agents fetch."
        ),
        expected_output=(
            "A structured intent summary containing:\n"
            "- action: the ActionType string (or 'query_only' if no transaction)\n"
            "- parameters: dict of extracted values (amount, deferral_pct, expense_type, etc.)\n"
            "- is_transaction: true/false\n"
            "- notes: any ambiguities or missing fields"
        ),
        agent=intent_agent,
    )

    task_fetch_plan = Task(
        description=(
            f"Fetch the plan rules for plan {plan_id} using GetPlanRules. "
            "Identify which capabilities are relevant to the action identified in the intent step. "
            "Note whether a blackout is active, whether the requested action type is permitted, "
            "and any plan-specific limits that apply."
        ),
        expected_output=(
            "A concise plan rules summary relevant to the proposed action: "
            "blackout status, whether the action is permitted, key limits (loan cap, hardship standard, etc.)."
        ),
        agent=data_agent,
        context=[task_interpret],
    )

    task_fetch_participant = Task(
        description=(
            f"Fetch the participant summary for {participant_id} using GetParticipantSummary. "
            "If the action involves a loan, also call GetLoanHeadroom. "
            "Report employment status, service years, deferral info, loan count, and eligibility flags. "
            "Do NOT include date of birth, SSN, or marital status in your output."
        ),
        expected_output=(
            "A concise participant account summary relevant to the proposed action: "
            "employment status, vesting %, active loan count, catch-up eligibility, and loan headroom if applicable."
        ),
        agent=data_agent,
        context=[task_interpret],
    )

    _qdro_payload = _extract_qdro_payload(query)
    _qdro_hint = (
        f"\nQDRO PAYLOAD — use this exact payload_json string verbatim, do not modify it:\n"
        f"  {_qdro_payload}\n"
        if _qdro_payload else ""
    )

    task_compliance = Task(
        description=(
            f"Run the FAP compliance check using RunComplianceCheck with:\n"
            f"  agent_id: {agent_id}\n"
            f"  participant_id: {participant_id}\n"
            f"  plan_id: {plan_id}\n"
            "  action: (from the intent task)\n"
            "  payload_json: (JSON string built from intent task parameters)\n"
            f"{_qdro_hint}\n"
            "CRITICAL payload key names — use these exactly:\n"
            "  hardship_distribution: {\"amount\": 5000, \"qualifying_expense_type\": \"medical\"}\n"
            "    (NOT expense_type — the key is qualifying_expense_type)\n"
            "    valid values: medical, tuition, primary_home_purchase, prevent_eviction, funeral, casualty_loss, FEMA_disaster\n"
            "    map: 'medical emergency' → medical, 'housing purchase' → primary_home_purchase\n"
            "    if participant rmd_required=True (check participant summary) also include rmd_satisfied_for_year=true\n"
            "  loan_initiation: {\"amount\": 10000, \"repayment_years\": 5, \"purpose\": \"general\"}\n"
            "  deferral_change: {\"new_deferral_pct\": 0.06, \"deferral_type\": \"pre_tax\"}\n"
            "    (both new_deferral_pct and deferral_pct are accepted)\n"
            "  separation_distribution: {\"rollover_notice_issued\": true}\n"
            "    (participant must be terminated or retired; rollover_notice_issued confirms IRC §402(f) notice given)\n"
            "    if participant rmd_required=True also include rmd_satisfied_for_year=true\n"
            "  in_service_distribution: {}\n"
            "    (participant must be age 59.5+ — fetch participant summary first to confirm)\n"
            "    if participant rmd_required=True also include rmd_satisfied_for_year=true\n"
            "  rmd: {\"rmd_notice_issued\": true, \"amount\": 16800}\n"
            "    (amount must meet or exceed participant's rmd_amount_current_year)\n"
            "  beneficiary_update: {} or {\"spousal_consent_obtained\": true}\n"
            "  investment_reallocation: {\"scope\": \"both\", \"elections\": [{\"fund_id\": \"FIDELITY-500\", \"allocation_pct\": 0.6}, {\"fund_id\": \"VANGUARD-TDF-2040\", \"allocation_pct\": 0.4}]}\n"
            "    valid fund IDs: FIDELITY-500, VANGUARD-TDF-2040, PIMCO-BOND, STABLE-VALUE\n"
            "  qdro: {\"participant_name\": \"...\", \"alternate_payee_name\": \"...\", \"plan_name\": \"...\", \"benefit_amount_or_pct\": \"...\", \"payment_period\": \"...\"}\n"
            "    ALL FIVE keys are REQUIRED. Extract each value directly from the original participant message above:\n"
            "      'Participant:' → participant_name\n"
            "      'Alternate payee:' → alternate_payee_name\n"
            "      'Plan:' → plan_name\n"
            "      'Amount:' → benefit_amount_or_pct\n"
            "      'Payment period:' → payment_period\n"
            "    Include a field only if the participant stated it. Do NOT infer from tool results or your knowledge.\n\n"
            "If the intent was a query_only (no transaction), skip this step and output 'no_compliance_needed'.\n\n"
            "Report the full result: authorized (true/false), fap_token, autonomy_level, "
            "or denial_code + denial_reason + erisa_citation."
        ),
        expected_output=(
            "FAP compliance result: either authorized=true with fap_token and autonomy_level, "
            "or authorized=false with denial_code, denial_reason, and erisa_citation."
        ),
        agent=compliance_agent,
        context=[task_interpret, task_fetch_plan, task_fetch_participant],
    )

    task_execute = Task(
        description=(
            "Based on the FAP compliance result:\n\n"
            "- If authorized=false: do nothing, just report the denial.\n"
            "- If authorized=true AND autonomy_level='full': call ExecuteTransaction immediately.\n"
            "- If authorized=true AND autonomy_level='supervised': call ExecuteTransaction "
            "  (the CLI will have already shown the participant a summary and gotten confirmation).\n"
            "- If authorized=true AND autonomy_level='human_review': call ExecuteTransaction — "
            "  it will automatically route to the plan sponsor queue.\n"
            "- If no compliance check was needed (query_only): report 'no transaction executed'.\n\n"
            f"For ExecuteTransaction: participant_id={participant_id}, "
            "action and payload_json from intent task, fap_token and autonomy_level from compliance task."
        ),
        expected_output=(
            "Transaction execution result: status (executed/queued_for_human_review/not_applicable), "
            "queue_entry_id if applicable, or denial pass-through."
        ),
        agent=transaction_agent,
        context=[task_interpret, task_compliance],
    )

    task_respond = Task(
        description=(
            "Compose the final response for the participant using this exact structure:\n\n"
            "STATUS: [one-line summary, e.g. 'Loan approved — pending your confirmation']\n\n"
            "Details:\n"
            "- [key fact 1, e.g. Amount: $10,000]\n"
            "- [key fact 2, e.g. Term: 5 years]\n"
            "- [key fact 3, e.g. ERISA rule: IRC §72(p) loan cap]\n\n"
            "Next Steps: [what the participant needs to do or expect next]\n\n"
            "Rules:\n"
            "- supervised: tell the participant to type 'confirm' to execute or 'cancel' to abort.\n"
            "- full (executed immediately): confirm execution happened, state what changed.\n"
            "- human_review: explain it is in the plan sponsor queue (typically 1-3 business days).\n"
            "- denied: plain-English reason (no internal codes), cite the ERISA rule, suggest alternative.\n"
            "- query_only: answer using the data fetched — use bullet points for multiple facts.\n\n"
            "Tone: professional, clear, empathetic. No internal system IDs except queue entry ID."
        ),
        expected_output=(
            "A structured participant-facing response with STATUS, Details, and Next Steps sections."
        ),
        agent=intent_agent,
        context=[task_interpret, task_fetch_plan, task_fetch_participant, task_compliance, task_execute],
    )

    # -------------------------------------------------------------------------
    # Crew assembly
    # -------------------------------------------------------------------------

    return Crew(
        agents=[intent_agent, data_agent, compliance_agent, transaction_agent],
        tasks=[
            task_interpret,
            task_fetch_plan,
            task_fetch_participant,
            task_compliance,
            task_execute,
            task_respond,
        ],
        process=Process.sequential,
        verbose=False,
    )


def build_document_verification_crew(
    participant_id: str,
    plan_id: str,
    queue_entry_id: str,
    action_type: str,
    expense_type: str,
    doc_type: str,
    file_path: str,
    object_key: str = "",
) -> Crew:
    """
    Mini-crew for document upload and verification after a human_review action is queued.

    One agent (Document Agent) with UploadDocumentTool. Called from the CLI after
    the participant has already chosen which file to submit — the agent handles
    the actual upload, LLM verification, and store write.
    """

    document_agent = Agent(
        role="ERISA Document Verification Specialist",
        goal=(
            "Upload the participant's supporting document and verify it matches "
            "the claimed action type and expense category. "
            "Report the verification result clearly so the participant knows what the plan sponsor will see."
        ),
        backstory=(
            "You are responsible for ingesting supporting documentation for ERISA hardship "
            "distributions and QDRO requests. You call UploadDocument with the exact parameters "
            "provided, then summarize the outcome — doc ID, whether verification passed, key details "
            "extracted, and what next steps the participant should expect."
        ),
        tools=[UploadDocumentTool()],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    task_upload_and_verify = Task(
        description=(
            f"Upload and verify a supporting document for this human_review request.\n\n"
            f"Call UploadDocument with EXACTLY these parameters:\n"
            f"  participant_id: {participant_id}\n"
            f"  plan_id: {plan_id}\n"
            f"  queue_entry_id: {queue_entry_id}\n"
            f"  action_type: {action_type}\n"
            f"  expense_type: {expense_type}\n"
            f"  doc_type: {doc_type}\n"
            f"  file_path: {file_path}\n"
            f"  object_key: {object_key}\n\n"
            "After the tool returns, write a concise participant-facing summary:\n"
            "- State whether the document was verified (Passed / Needs review)\n"
            "- Include the document ID\n"
            "- Report key details found in the document (amount, date, provider)\n"
            "- Confirm the document is now in the plan sponsor's review queue\n"
            "- One sentence on what the participant should expect next"
        ),
        expected_output=(
            "A 4-6 line plain-English summary: upload status, doc ID, verification result, "
            "key details extracted, and next-steps note for the participant."
        ),
        agent=document_agent,
    )

    return Crew(
        agents=[document_agent],
        tasks=[task_upload_and_verify],
        process=Process.sequential,
        verbose=False,
    )
