"""
FAP authorization engine — pure Python orchestrator.
Wraps the compliance engine and token service into the full authorize() flow.
CrewAI tool wrappers are at the bottom of this file.
"""

import uuid
from datetime import datetime, timezone
from typing import Any

from agents.fap.compliance import run_compliance_check
from agents.fap.models import (
    ActionType,
    AuthorizationApproved,
    AuthorizationDenied,
    FapAuditRecord,
    PrincipalType,
    RuleResult,
)
from agents.fap.tokens import issue_token
from agents.plap.models import PlanRecord
from agents.paap.models import ParticipantRecord

# In-memory audit log (production: append to immutable store / database)
_audit_log: list[FapAuditRecord] = []


def authorize(
    agent_id: str,
    principal_type: PrincipalType,
    participant: ParticipantRecord,
    plan: PlanRecord,
    action: ActionType,
    payload: dict[str, Any],
) -> AuthorizationApproved | AuthorizationDenied:
    """
    Core FAP authorization entry point.

    1. Runs the 12-rule compliance check.
    2. If approved: issues a scoped JWT and writes an audit record.
    3. If denied: writes an audit record and returns the denial.
    """
    audit_id = str(uuid.uuid4())
    timestamp = datetime.now(tz=timezone.utc).isoformat()

    result: RuleResult = run_compliance_check(
        agent_id=agent_id,
        principal_type=principal_type,
        participant=participant,
        plan=plan,
        action=action,
        payload=payload,
    )

    if not result.passed:
        audit = FapAuditRecord(
            audit_id=audit_id,
            timestamp=timestamp,
            agent_id=agent_id,
            principal_type=principal_type,
            participant_id=participant.participant_id,
            plan_id=plan.plan_id,
            action=action.value,
            authorized=False,
            denial_code=result.denial_code.value if result.denial_code else None,
            erisa_citation=result.erisa_citation or "",
            master_ref_section=result.master_ref_section or "",
            autonomy_level=None,
            token_id=None,
            plap_snapshot_version=plan.snapshot_version,
        )
        _audit_log.append(audit)

        return AuthorizationDenied(
            authorized=False,
            denial_reason=result.denial_reason or "Compliance check failed.",
            denial_code=result.denial_code,
            erisa_citation=result.erisa_citation or "",
            master_ref_section=result.master_ref_section or "",
            audit_id=audit_id,
        )

    # All rules passed — issue token
    token_str, token_id, expires_at = issue_token(
        agent_id=agent_id,
        participant_id=participant.participant_id,
        plan_id=plan.plan_id,
        action=action,
        autonomy_level=result.autonomy_level,
        payload=payload,
    )

    audit = FapAuditRecord(
        audit_id=audit_id,
        timestamp=timestamp,
        agent_id=agent_id,
        principal_type=principal_type,
        participant_id=participant.participant_id,
        plan_id=plan.plan_id,
        action=action.value,
        authorized=True,
        denial_code=None,
        erisa_citation="All 12 FAP rules passed.",
        master_ref_section="§1-§12",
        autonomy_level=result.autonomy_level,
        token_id=token_id,
        plap_snapshot_version=plan.snapshot_version,
    )
    _audit_log.append(audit)

    return AuthorizationApproved(
        authorized=True,
        token=token_str,
        token_expires_at=expires_at,
        autonomy_level=result.autonomy_level,
        conditions=result.conditions,
        erisa_citations=["All 12 FAP rules passed."],
        audit_id=audit_id,
    )


def get_audit_record(audit_id: str) -> FapAuditRecord | None:
    return next((r for r in _audit_log if r.audit_id == audit_id), None)


def get_all_audit_records() -> list[FapAuditRecord]:
    return list(_audit_log)
