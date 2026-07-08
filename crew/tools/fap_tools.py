"""
FAP CrewAI tool — wraps the Fiduciary Agent Protocol for use by the Compliance Agent.

The LLM never sees participant PII (vested_balance, DOB, marital status).
The tool fetches full data internally, runs all 12 ERISA rules, and returns only the result.
"""

import json
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from agents.fap.agent import authorize
from crew.tool_logger import record
from agents.fap.models import ActionType, PrincipalType
from data.participants import get_participant
from data.plans import get_plan
from data.agents import AGENT_REGISTRY


class RunComplianceCheckInput(BaseModel):
    agent_id: str = Field(description="Agent registry ID, e.g. AGENT-PARTICIPANT-001")
    participant_id: str = Field(description="Participant ID, e.g. PART-001")
    plan_id: str = Field(description="Plan ID, e.g. PLAN-001")
    action: str = Field(description="ActionType, e.g. loan_initiation, deferral_change, hardship_distribution")
    payload_json: str = Field(
        description=(
            "JSON string with action-specific parameters. "
            "loan_initiation: {\"amount\": 10000, \"repayment_years\": 5, \"purpose\": \"general\"}. "
            "  purpose must be 'general' (max 5yr term) or 'primary_residence' (max 15yr term). "
            "deferral_change: {\"new_deferral_pct\": 0.06, \"deferral_type\": \"pre_tax\"}. "
            "  deferral_type: pre_tax or roth. SECURE 2.0: age 50+ earners >$145k must use roth for catch-up. "
            "hardship_distribution: {\"amount\": 5000, \"qualifying_expense_type\": \"medical\"}. "
            "  Valid qualifying_expense_type values: medical, tuition, primary_home_purchase, "
            "  prevent_eviction, funeral, casualty_loss, FEMA_disaster. "
            "  Map user descriptions: 'medical emergency' → medical, 'housing/home purchase' → primary_home_purchase, "
            "  'eviction/foreclosure' → prevent_eviction, 'burial/funeral' → funeral, "
            "  'school/college' → tuition. "
            "  IMPORTANT: if participant summary shows rmd_required=True, add rmd_satisfied_for_year=true "
            "  to confirm the RMD for this plan year is already satisfied before allowing other distributions. "
            "investment_reallocation: {\"scope\": \"both\", \"elections\": [{\"fund_id\": \"COF-SP500\", \"allocation_pct\": 0.6}, {\"fund_id\": \"COF-LIFEPATH-2040\", \"allocation_pct\": 0.4}]}. "
            "  scope: future_only, existing_only, or both. allocations must sum to 1.0. "
            "  PLAN-003 (Capital One) fund IDs: COF-SP500, COF-BOND, COF-STABLE, COF-INTL, COF-RUSSELL2500, COF-CAPON, COF-LIFEPATH-2025 through COF-LIFEPATH-2050. "
            "  PLAN-004 (Prudential) fund IDs: PESP-SP500, PESP-BOND, PESP-STABLE, PESP-INTL, PESP-SMIDCAP, PESP-PRU-STOCK, PESP-GOALMAKER-AGG, PESP-GOALMAKER-MOD, PESP-GOALMAKER-CONS. "
            "in_service_distribution: {}. "
            "  Only allowed for participants age 59.5+. Optionally add penalty_exception if applicable. "
            "  If participant has rmd_required=True, also include rmd_satisfied_for_year=true. "
            "separation_distribution: {\"rollover_notice_issued\": true}. "
            "  Only allowed for terminated or retired participants. "
            "  If participant has rmd_required=True, also include rmd_satisfied_for_year=true. "
            "rmd: {\"rmd_notice_issued\": true, \"amount\": 16800}. "
            "  amount must meet or exceed the participant's rmd_amount_current_year. "
            "beneficiary_update: {}. "
            "  Optionally include spousal_consent_obtained=true if plan requires spousal consent. "
            "qdro: {\"participant_name\": \"Pat Rivera\", \"alternate_payee_name\": \"Jordan Rivera\", "
            "  \"plan_name\": \"Aldergate Technology 401k\", \"benefit_amount_or_pct\": \"50%\", \"payment_period\": \"until alternate payee age 65\"}. "
            "  CRITICAL FOR QDRO: include ALL FIVE fields using the exact values from the participant's message. "
            "  Do NOT infer fields from GetParticipantSummary results, GetPlanRules results, or your own knowledge. "
            "  Only omit a field if the participant genuinely did not mention it at all in their message — "
            "  in that case FAP will detect the missing field and deny. "
            "  If the participant stated all five values, you MUST include all five in the payload. "
            "address_update: {}."
        )
    )


class RunComplianceCheckTool(BaseTool):
    name: str = "RunComplianceCheck"
    description: str = (
        "Run all 12 ERISA compliance rules (FAP) for a proposed participant action. "
        "Returns either an approved FAP token with autonomy level, or a denial with the specific rule violated. "
        "This is the ONLY tool that must be called before any write operation. "
        "The LLM never sees participant PII — the tool fetches data internally."
    )
    args_schema: type[BaseModel] = RunComplianceCheckInput

    def _run(
        self,
        agent_id: str,
        participant_id: str,
        plan_id: str,
        action: str,
        payload_json: str,
    ) -> str:
        try:
            payload = json.loads(payload_json)
        except json.JSONDecodeError:
            return json.dumps({"error": "payload_json is not valid JSON."})

        participant = get_participant(participant_id)
        if not participant:
            return json.dumps({"error": f"Participant {participant_id} not found."})

        plan = get_plan(plan_id)
        if not plan:
            return json.dumps({"error": f"Plan {plan_id} not found."})

        registration = AGENT_REGISTRY.get(agent_id)
        if not registration:
            return json.dumps({"error": f"Agent {agent_id} not in registry."})

        try:
            action_enum = ActionType(action)
        except ValueError:
            valid = [a.value for a in ActionType]
            return json.dumps({"error": f"Unknown action '{action}'. Valid: {valid}"})

        result = authorize(
            agent_id=agent_id,
            principal_type=registration.principal_type,
            participant=participant,
            plan=plan,
            action=action_enum,
            payload=payload,
        )

        if result.authorized:
            record("RunComplianceCheck",
                   f"{action}  {participant_id}",
                   f"APPROVED  autonomy={result.autonomy_level.value}")
            # Return the canonical payload_json (sort_keys=True) so the LLM can
            # pass it verbatim to ExecuteTransaction — avoids payload hash mismatch.
            canonical_payload_json = json.dumps(payload, sort_keys=True, default=str)
            return json.dumps({
                "authorized": True,
                "fap_token": result.token,
                "token_expires_at": result.token_expires_at,
                "autonomy_level": result.autonomy_level.value,
                "conditions": result.conditions,
                "audit_id": result.audit_id,
                "erisa_citations": result.erisa_citations,
                "payload_json": canonical_payload_json,
                "next_step": (
                    "Call ExecuteTransaction with this fap_token and the payload_json field from this response "
                    "(use it verbatim — the token is cryptographically bound to this exact payload). "
                    "If autonomy_level is 'supervised', show the participant a summary and get confirmation first. "
                    "If autonomy_level is 'human_review', ExecuteTransaction will route to the plan sponsor queue."
                ),
            }, indent=2)
        else:
            denial_code = result.denial_code.value if result.denial_code else "unknown"
            record("RunComplianceCheck",
                   f"{action}  {participant_id}",
                   f"DENIED  {denial_code}")
            return json.dumps({
                "authorized": False,
                "denial_code": denial_code,
                "denial_reason": result.denial_reason,
                "erisa_citation": result.erisa_citation,
                "master_ref_section": result.master_ref_section,
                "audit_id": result.audit_id,
            }, indent=2)


class GetAuditLogInput(BaseModel):
    participant_id: str = Field(
        default="",
        description="Optional: filter by participant ID. Leave empty to get all recent entries.",
    )
    limit: int = Field(default=10, description="Number of most recent records to return (max 50)")


class GetAuditLogTool(BaseTool):
    name: str = "GetAuditLog"
    description: str = (
        "Retrieve recent FAP audit log entries. "
        "Every compliance decision (approved and denied) is logged here per ERISA § 107 (6-year retention). "
        "Plan sponsors can use this to review all decisions. "
        "Optionally filter by participant_id."
    )
    args_schema: type[BaseModel] = GetAuditLogInput

    def _run(self, participant_id: str = "", limit: int = 10) -> str:
        from agents.fap.agent import get_all_audit_records

        records = get_all_audit_records()
        if participant_id:
            records = [r for r in records if r.participant_id == participant_id]

        limit = min(limit, 50)
        recent = records[-limit:]

        entries = [
            {
                "audit_id": r.audit_id,
                "timestamp": r.timestamp,
                "participant_id": r.participant_id,
                "plan_id": r.plan_id,
                "action": r.action,
                "authorized": r.authorized,
                "denial_code": r.denial_code,
                "autonomy_level": r.autonomy_level.value if r.autonomy_level else None,
                "erisa_citation": r.erisa_citation,
            }
            for r in recent
        ]
        out = json.dumps({"count": len(entries), "entries": entries}, indent=2)
        record("GetAuditLog",
               f"filter={participant_id or 'all'}  limit={limit}",
               f"{len(entries)} entries")
        return out
