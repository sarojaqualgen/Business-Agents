"""
Crew router — selects the appropriate CrewAI crew based on who is logged in.

Principal type → Crew mapping:
  participant          → ParticipantCrew
  plan_sponsor         → SponsorCrew
  plan_trustee         → SponsorCrew  (trustees share the admin interface)
  investment_advisor   → AdvisorCrew
  participant_delegate → ParticipantCrew (delegate acts on participant's behalf)

Recordkeeper is NOT a conversational crew. It is an automated data ingestion pipeline
that runs on a schedule (Phase 5 — SFTP/API sync from Fidelity/Vanguard/Empower).
"""

from crewai import Crew

from agents.fap.models import PrincipalType
from crew.crews.participant_crew import build_participant_crew
from crew.crews.sponsor_crew import build_sponsor_crew
from crew.crews.advisor_crew import build_advisor_crew


def route(
    principal_type: str,
    query: str,
    participant_id: str = "",
    plan_id: str = "",
    agent_id: str = "",
) -> Crew:
    """
    Build and return the correct crew for the authenticated principal.

    Args:
        principal_type : PrincipalType value string, e.g. "participant"
        query          : Natural language input from the user
        participant_id : Required for participant and advisor crews
        plan_id        : Required for all crews
        agent_id       : Agent registry ID for the caller

    Returns:
        A configured, ready-to-kickoff Crew.
    """
    pt = principal_type.lower()

    if pt in (PrincipalType.participant.value, PrincipalType.participant_delegate.value):
        if not participant_id or not plan_id or not agent_id:
            raise ValueError("participant_id, plan_id, and agent_id are required for participant crew.")
        return build_participant_crew(
            participant_id=participant_id,
            plan_id=plan_id,
            agent_id=agent_id,
            query=query,
        )

    if pt in (PrincipalType.plan_sponsor.value, PrincipalType.plan_trustee.value):
        if not plan_id or not agent_id:
            raise ValueError("plan_id and agent_id are required for sponsor crew.")
        return build_sponsor_crew(
            plan_id=plan_id,
            sponsor_agent_id=agent_id,
            query=query,
        )

    if pt == PrincipalType.investment_advisor.value:
        if not participant_id or not plan_id or not agent_id:
            raise ValueError("participant_id, plan_id, and agent_id are required for advisor crew.")
        return build_advisor_crew(
            participant_id=participant_id,
            plan_id=plan_id,
            advisor_agent_id=agent_id,
            query=query,
        )

    raise ValueError(
        f"Unknown principal_type '{principal_type}'. "
        f"Valid values: {[p.value for p in PrincipalType]}"
    )
