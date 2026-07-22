"""
FAP Pydantic models — authorization requests, responses, audit records, and agent registry.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field


class PrincipalType(str, Enum):
    participant = "participant"
    plan_sponsor = "plan_sponsor"
    investment_advisor = "investment_advisor"
    plan_trustee = "plan_trustee"
    participant_delegate = "participant_delegate"


class ActionType(str, Enum):
    deferral_change = "deferral_change"
    investment_reallocation = "investment_reallocation"
    loan_initiation = "loan_initiation"
    hardship_distribution = "hardship_distribution"
    in_service_distribution = "in_service_distribution"
    separation_distribution = "separation_distribution"
    rmd = "rmd"
    beneficiary_update = "beneficiary_update"
    qdro = "qdro"
    address_update = "address_update"  # PAAP §3.3 — Full autonomy, no tax/legal consequence


class AutonomyLevel(str, Enum):
    full = "full"
    supervised = "supervised"
    human_review = "human_review"


class DenialCode(str, Enum):
    # Rule 1
    agent_not_registered = "AGENT_NOT_REGISTERED"
    delegation_scope_exceeded = "DELEGATION_SCOPE_EXCEEDED"
    # Rule 2
    blackout_active = "BLACKOUT_ACTIVE"
    # Rule 3
    eligibility_not_met = "ELIGIBILITY_NOT_MET"
    entry_date_not_reached = "ENTRY_DATE_NOT_REACHED"
    # Rule 4
    insufficient_vesting = "INSUFFICIENT_VESTING"
    # Rule 5
    deferral_limit_exceeded = "DEFERRAL_LIMIT_EXCEEDED"
    annual_additions_limit_exceeded = "ANNUAL_ADDITIONS_LIMIT_EXCEEDED"
    # Rule 6
    loan_cap_exceeded = "LOAN_CAP_EXCEEDED"
    loan_not_permitted = "LOAN_NOT_PERMITTED"
    loans_outstanding_limit = "LOANS_OUTSTANDING_LIMIT"
    hardship_not_permitted = "HARDSHIP_NOT_PERMITTED"
    hardship_criteria_not_met = "HARDSHIP_CRITERIA_NOT_MET"
    hardship_not_active_employee = "HARDSHIP_NOT_ACTIVE_EMPLOYEE"
    in_service_age_not_met = "IN_SERVICE_AGE_NOT_MET"
    in_service_not_active_employee = "IN_SERVICE_NOT_ACTIVE_EMPLOYEE"
    separation_status_invalid = "SEPARATION_STATUS_INVALID"
    rollover_notice_not_issued = "ROLLOVER_NOTICE_NOT_ISSUED"
    rmd_not_yet_required = "RMD_NOT_YET_REQUIRED"
    rmd_amount_insufficient = "RMD_AMOUNT_INSUFFICIENT"
    qjsa_consent_required = "QJSA_CONSENT_REQUIRED"
    qdro_fields_missing = "QDRO_FIELDS_MISSING"
    # Rule 7
    early_withdrawal_penalty_applies = "EARLY_WITHDRAWAL_PENALTY_APPLIES"
    # Rule 8
    anti_alienation_violation = "ANTI_ALIENATION_VIOLATION"
    # Rule 9
    prohibited_transaction = "PROHIBITED_TRANSACTION"
    # Rule 10
    prudent_expert_review_required = "PRUDENT_EXPERT_REVIEW_REQUIRED"
    # Rule 11
    rmd_shortfall_risk = "RMD_SHORTFALL_RISK"
    # Rule 5 — SECURE 2.0
    roth_catchup_required = "ROTH_CATCHUP_REQUIRED"
    # Rule 6 — RMD notice
    rmd_notice_not_issued = "RMD_NOTICE_NOT_ISSUED"
    # Rule 10 — taxable event disclosure
    taxable_event_not_acknowledged = "TAXABLE_EVENT_NOT_ACKNOWLEDGED"


# ---------------------------------------------------------------------------
# Authorization request / response
# ---------------------------------------------------------------------------

class AuthorizationRequest(BaseModel):
    agent_id: str
    principal_type: PrincipalType
    participant_id: str
    plan_id: str
    action: ActionType
    payload: dict[str, Any] = Field(default_factory=dict)


class AuthorizationApproved(BaseModel):
    authorized: bool = True
    token: str
    token_expires_at: str
    autonomy_level: AutonomyLevel
    conditions: list[str] = Field(default_factory=list)
    erisa_citations: list[str] = Field(default_factory=list)
    audit_id: str


class AuthorizationDenied(BaseModel):
    authorized: bool = False
    denial_reason: str
    denial_code: DenialCode
    erisa_citation: str
    master_ref_section: str
    audit_id: str


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

class AgentRegistration(BaseModel):
    agent_id: str
    agent_name: str
    principal_type: PrincipalType
    delegation_document_ref: str
    allowed_plan_ids: list[str]
    allowed_actions: list[ActionType]
    token_max_ttl_seconds: int = 300
    is_active: bool = True


# ---------------------------------------------------------------------------
# Audit log (immutable — every FAP decision produces one)
# ---------------------------------------------------------------------------

class FapAuditRecord(BaseModel):
    audit_id: str
    timestamp: str
    agent_id: str
    principal_type: PrincipalType
    participant_id: str
    plan_id: str
    action: str
    authorized: bool
    denial_code: Optional[str] = None
    erisa_citation: str
    master_ref_section: str
    autonomy_level: Optional[AutonomyLevel] = None
    token_id: Optional[str] = None
    plap_snapshot_version: str
    erisa_master_ref_version: str = "2026-06"
    fap_rule_engine_version: str = "1.0.0"


# ---------------------------------------------------------------------------
# Compliance rule result — returned by each of the 12 rule functions
# ---------------------------------------------------------------------------

class RuleResult(BaseModel):
    passed: bool
    rule_number: int
    rule_name: str
    denial_code: Optional[DenialCode] = None
    denial_reason: Optional[str] = None
    erisa_citation: Optional[str] = None
    master_ref_section: Optional[str] = None
    autonomy_level: Optional[AutonomyLevel] = None
    conditions: list[str] = Field(default_factory=list)
