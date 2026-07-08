"""
Agent registry — authorized agents for Aldergate plans.
In production this is a database table (agent_registry).
"""

from agents.fap.models import ActionType, AgentRegistration, PrincipalType

AGENT_REGISTRY: dict[str, AgentRegistration] = {
    "AGENT-PARTICIPANT-001": AgentRegistration(
        agent_id="AGENT-PARTICIPANT-001",
        agent_name="Participant Self-Service Agent",
        principal_type=PrincipalType.participant,
        delegation_document_ref="delegation/participant-self-service-v1.pdf",
        allowed_plan_ids=["PLAN-003", "PLAN-004"],
        allowed_actions=list(ActionType),
        token_max_ttl_seconds=300,
        is_active=True,
    ),
    "AGENT-ADVISOR-001": AgentRegistration(
        agent_id="AGENT-ADVISOR-001",
        agent_name="Registered Investment Advisor Agent",
        principal_type=PrincipalType.investment_advisor,
        delegation_document_ref="delegation/ria-advisory-agreement-v2.pdf",
        allowed_plan_ids=["PLAN-003"],     # Capital One only
        allowed_actions=[
            ActionType.investment_reallocation,
            ActionType.deferral_change,
        ],
        token_max_ttl_seconds=300,
        is_active=True,
    ),
    "AGENT-SPONSOR-001": AgentRegistration(
        agent_id="AGENT-SPONSOR-001",
        agent_name="Plan Sponsor Admin Agent",
        principal_type=PrincipalType.plan_sponsor,
        delegation_document_ref="delegation/plan-sponsor-admin-v1.pdf",
        allowed_plan_ids=["*"],            # plan sponsor acts on all plans
        allowed_actions=[
            ActionType.beneficiary_update,
            ActionType.qdro,
            ActionType.rmd,
        ],
        token_max_ttl_seconds=300,
        is_active=True,
    ),
    "AGENT-INACTIVE-001": AgentRegistration(
        agent_id="AGENT-INACTIVE-001",
        agent_name="Revoked Agent",
        principal_type=PrincipalType.participant,
        delegation_document_ref="delegation/revoked.pdf",
        allowed_plan_ids=["PLAN-003"],
        allowed_actions=list(ActionType),
        token_max_ttl_seconds=300,
        is_active=False,
    ),
}
