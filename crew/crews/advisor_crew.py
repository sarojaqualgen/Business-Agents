"""
Investment Advisor Crew — handles advisory actions for registered investment advisors.

Advisor scope (per agent registry — AGENT-ADVISOR-001):
  - investment_reallocation  (supervised autonomy — participant must confirm)
  - deferral_change          (supervised autonomy)

Advisor restrictions:
  - Cannot initiate loans, hardship withdrawals, or distributions
  - Cannot see participant DOB, SSN, marital status, or full balance
  - All recommendations go through FAP with principal_type=investment_advisor
  - PTE 2020-02 disclosure requirements apply for rollover recommendations

Entry point: build_advisor_crew(context) → Crew
"""

from crewai import Agent, Task, Crew, Process

from crew.agents.base import fap_llm
from crew.tools.plap_tools import GetPlanRulesTool, GetFundLineupTool
from crew.tools.paap_tools import GetParticipantSummaryTool, ExecuteTransactionTool
from crew.tools.fap_tools import RunComplianceCheckTool


def build_advisor_crew(
    participant_id: str,
    plan_id: str,
    advisor_agent_id: str,
    query: str,
) -> Crew:
    """
    Build and return a configured investment advisor crew for a client session.
    """

    # -------------------------------------------------------------------------
    # Agents
    # -------------------------------------------------------------------------

    advisor_intent_agent = Agent(
        role="Registered Investment Advisor",
        goal=(
            "Understand the advisor's investment recommendation for their client, "
            "structure it as a compliant transaction request, and communicate the outcome clearly. "
            "Ensure PTE 2020-02 disclosures are noted for any rollover-related recommendations."
        ),
        backstory=(
            "You are a registered investment advisor (RIA) who assists plan participants with "
            "investment decisions within their 401(k). You can recommend investment reallocations "
            "and deferral changes — but ALL changes require participant confirmation (supervised autonomy) "
            "before execution. You cannot initiate loans, withdrawals, or distributions. "
            "You are acting as a fiduciary under PTE 2020-02 for rollover recommendations."
        ),
        tools=[],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    advisor_data_agent = Agent(
        role="Investment Advisory Data Specialist",
        goal=(
            "Fetch the plan fund lineup and a limited client account summary needed to "
            "support an investment recommendation. Never expose client PII."
        ),
        backstory=(
            "You have access to plan fund data (PLAP) and a PII-minimized participant summary (PAAP). "
            "You do not see the client's full balance, date of birth, SSN, or marital status. "
            "After compliance approval, you submit the recommended transaction."
        ),
        tools=[
            GetPlanRulesTool(),
            GetFundLineupTool(),
            GetParticipantSummaryTool(),
            ExecuteTransactionTool(),
        ],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    advisor_compliance_agent = Agent(
        role="ERISA Fiduciary Compliance Officer",
        goal=(
            "Run the full 12-rule FAP compliance check for the advisor's recommended action. "
            "The FAP token will carry principal_type=investment_advisor and the limited action scope."
        ),
        backstory=(
            "You run FAP compliance for advisor-initiated transactions. "
            "The advisor's agent registration limits their scope to investment_reallocation and deferral_change. "
            "If the advisor attempts an action outside their scope, FAP Rule 1 will deny it immediately. "
            "You only have RunComplianceCheck — no data access, no execution."
        ),
        tools=[RunComplianceCheckTool()],
        llm=fap_llm,
        verbose=False,
        allow_delegation=False,
    )

    # -------------------------------------------------------------------------
    # Tasks
    # -------------------------------------------------------------------------

    task_interpret_advisory = Task(
        description=(
            f"Advisor query: \"{query}\"\n\n"
            f"Client (Participant) ID: {participant_id}\n"
            f"Plan ID: {plan_id}\n"
            f"Advisor Agent ID: {advisor_agent_id}\n\n"
            "Parse the advisor's recommendation and identify:\n"
            "1. Action type (must be investment_reallocation or deferral_change — advisors have no other scope)\n"
            "2. Specific parameters (new fund allocations with fund_ids and percentages, or new deferral_pct)\n"
            "3. Rationale (why is the advisor recommending this?)\n\n"
            "Note: if the advisor requests an action outside their scope (loan, distribution, etc.), "
            "flag this as a scope violation — do not proceed to compliance."
        ),
        expected_output=(
            "Advisory intent: action (investment_reallocation or deferral_change), "
            "parameters, rationale, and scope_violation flag if applicable."
        ),
        agent=advisor_intent_agent,
    )

    task_fetch_advisory_data = Task(
        description=(
            f"Fetch data for the advisory recommendation:\n"
            f"1. Call GetFundLineup for plan {plan_id} — identify the target funds by ID\n"
            f"2. Call GetParticipantSummary for participant {participant_id} — check current allocation and status\n"
            f"3. Call GetPlanRules for {plan_id} — verify no blackout is active\n\n"
            "Validate that all fund_ids in the advisor's recommendation exist in the plan lineup. "
            "If reallocating, confirm allocations sum to 100%."
        ),
        expected_output=(
            "Plan fund lineup, current participant allocation, blackout status, "
            "and validation of proposed allocations (do they sum to 100%? do fund_ids exist?)."
        ),
        agent=advisor_data_agent,
        context=[task_interpret_advisory],
    )

    task_advisory_compliance = Task(
        description=(
            f"Run RunComplianceCheck for the advisor's recommendation:\n"
            f"  agent_id: {advisor_agent_id}\n"
            f"  participant_id: {participant_id}\n"
            f"  plan_id: {plan_id}\n"
            "  action: (from intent task — must be investment_reallocation or deferral_change)\n"
            "  payload_json: (JSON of the proposed reallocation or deferral change)\n\n"
            "If the intent was flagged as a scope_violation, skip this step and output the violation details.\n\n"
            "Note: investment_reallocation and deferral_change have 'supervised' autonomy level — "
            "the participant must confirm before execution."
        ),
        expected_output=(
            "FAP compliance result: authorized=true with fap_token + autonomy_level='supervised', "
            "or authorized=false with specific denial."
        ),
        agent=advisor_compliance_agent,
        context=[task_interpret_advisory, task_fetch_advisory_data],
    )

    task_advisory_execute = Task(
        description=(
            "If FAP approved the recommendation (authorized=true):\n"
            "  Call ExecuteTransaction — autonomy_level will be 'supervised', so the CLI will have "
            "  shown the participant a summary and gotten their confirmation before this step runs.\n\n"
            "If FAP denied: output 'execution_skipped' with the denial reason.\n"
            "If scope_violation: output 'scope_violation' — advisor cannot request this action type.\n\n"
            f"Parameters: participant_id={participant_id}, action and payload_json from intent task, "
            "fap_token and autonomy_level from compliance task."
        ),
        expected_output=(
            "Transaction execution result or reason why execution was skipped."
        ),
        agent=advisor_data_agent,
        context=[task_interpret_advisory, task_advisory_compliance],
    )

    task_advisor_respond = Task(
        description=(
            "Compose the final response for the investment advisor. "
            "Professional and precise — include:\n"
            "- What was recommended and why\n"
            "- FAP compliance result (approved/denied with reason)\n"
            "- If approved + supervised: confirm participant confirmation was obtained\n"
            "- If denied: explain the ERISA rule violated and suggest alternatives\n"
            "- If scope violation: clearly state what actions advisors are authorized to submit\n\n"
            "Include a PTE 2020-02 disclosure reminder if the recommendation involved rollover guidance."
        ),
        expected_output=(
            "A professional advisor-facing response covering the recommendation outcome, "
            "compliance status, and any regulatory notes."
        ),
        agent=advisor_intent_agent,
        context=[
            task_interpret_advisory,
            task_fetch_advisory_data,
            task_advisory_compliance,
            task_advisory_execute,
        ],
    )

    # -------------------------------------------------------------------------
    # Crew assembly
    # -------------------------------------------------------------------------

    return Crew(
        agents=[advisor_intent_agent, advisor_data_agent, advisor_compliance_agent],
        tasks=[
            task_interpret_advisory,
            task_fetch_advisory_data,
            task_advisory_compliance,
            task_advisory_execute,
            task_advisor_respond,
        ],
        process=Process.sequential,
        verbose=False,
    )
