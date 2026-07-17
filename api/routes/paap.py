"""
PAAP REST endpoints — Participant Agent Protocol.

Read endpoints (no FAP token required):
  GET  /paap/participants/{id}/summary
  GET  /paap/participants/{id}/vesting
  GET  /paap/participants/{id}/loan-headroom
  GET  /paap/participants/{id}/rmd
  GET  /paap/participants/{id}/distribution-options

Write endpoints (PAAP calls PLAP → FAP → executes internally):
  POST /paap/participants/{id}/deferral
  POST /paap/participants/{id}/investment-reallocation
  POST /paap/participants/{id}/loan
  POST /paap/participants/{id}/distributions/hardship
  POST /paap/participants/{id}/distributions/in-service
  POST /paap/participants/{id}/distributions/separation
  POST /paap/participants/{id}/distributions/rmd
  PUT  /paap/participants/{id}/beneficiary
  POST /paap/participants/{id}/qdro

Security: participant sessions may only access their own participant_id.
Plan sponsors and advisors may access any participant in their plan.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator

from api.auth import SessionToken, get_session
from agents.paap.agent import (
    ParticipantNotFound,
    PlanDoesNotSupportAction,
    UnauthorizedByFAP,
    execute,
    get_distribution_options,
    get_loan_headroom,
    get_participant_summary,
    get_rmd_info,
    get_vesting_info,
)

router = APIRouter()


def _check_access(session: SessionToken, participant_id: str) -> None:
    """Participants may only read/write their own record."""
    if session.principal_type == "participant":
        if session.participant_id != participant_id:
            raise HTTPException(403, "You may only access your own account.")


def _agent_id(session: SessionToken) -> str:
    return session.agent_id or "portal"


# ---------------------------------------------------------------------------
# Read endpoints
# ---------------------------------------------------------------------------

@router.get("/participants/{participant_id}/summary")
def summary(participant_id: str, session: SessionToken = Depends(get_session)):
    _check_access(session, participant_id)
    try:
        return get_participant_summary(participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/participants/{participant_id}/vesting")
def vesting(participant_id: str, session: SessionToken = Depends(get_session)):
    _check_access(session, participant_id)
    try:
        return get_vesting_info(participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/participants/{participant_id}/loan-headroom")
def loan_headroom(participant_id: str, session: SessionToken = Depends(get_session)):
    _check_access(session, participant_id)
    try:
        return get_loan_headroom(participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/participants/{participant_id}/rmd")
def rmd_info(participant_id: str, session: SessionToken = Depends(get_session)):
    _check_access(session, participant_id)
    try:
        return get_rmd_info(participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/participants/{participant_id}/distribution-options")
def distribution_options(participant_id: str, session: SessionToken = Depends(get_session)):
    _check_access(session, participant_id)
    try:
        return get_distribution_options(participant_id)
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))


# ---------------------------------------------------------------------------
# Write request bodies
# ---------------------------------------------------------------------------

class DeferralBody(BaseModel):
    new_deferral_pct: float
    deferral_type: str = "pre_tax"
    catch_up: bool = False

    @field_validator("new_deferral_pct")
    @classmethod
    def pct_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("new_deferral_pct must be 0.0–1.0")
        return v


class InvestmentBody(BaseModel):
    elections: list[dict]  # [{"fund_id": str, "allocation_pct": float}]

    @field_validator("elections")
    @classmethod
    def sum_to_one(cls, v: list[dict]) -> list[dict]:
        total = sum(e.get("allocation_pct", 0) for e in v)
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Elections must sum to 1.0, got {total:.4f}")
        return v


class LoanBody(BaseModel):
    amount: float
    repayment_years: int
    purpose: str = "general"


class HardshipBody(BaseModel):
    amount: float
    qualifying_expense_type: str
    documentation_refs: list[str] = []


class SeparationBody(BaseModel):
    distribution_type: str  # "cash" | "direct_rollover_ira" | "direct_rollover_plan"
    amount: str = "full"   # "full" | "partial"
    rollover_destination: Optional[dict] = None


class RmdBody(BaseModel):
    payment_method: str = "check"


class BeneficiaryBody(BaseModel):
    beneficiaries: list[dict]


class QdroBody(BaseModel):
    alternate_payee_name: str
    benefit_pct: float
    payment_period: str
    documentation_refs: list[str] = []


# ---------------------------------------------------------------------------
# Write endpoints — PAAP calls PLAP → FAP → executes
# ---------------------------------------------------------------------------

def _write(
    session: SessionToken,
    participant_id: str,
    action: str,
    payload: dict[str, Any],
):
    _check_access(session, participant_id)
    try:
        return execute(
            participant_id=participant_id,
            agent_id=_agent_id(session),
            action=action,
            payload=payload,
        )
    except ParticipantNotFound as e:
        raise HTTPException(404, str(e))
    except PlanDoesNotSupportAction as e:
        raise HTTPException(422, str(e))
    except UnauthorizedByFAP as e:
        raise HTTPException(403, {"denial_reason": e.denial_reason, "denial_code": e.denial_code})


@router.post("/participants/{participant_id}/deferral")
def change_deferral(
    participant_id: str,
    body: DeferralBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "deferral_change", body.model_dump())


@router.post("/participants/{participant_id}/investment-reallocation")
def investment_reallocation(
    participant_id: str,
    body: InvestmentBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "investment_reallocation", body.model_dump())


@router.post("/participants/{participant_id}/loan")
def loan_request(
    participant_id: str,
    body: LoanBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "loan_initiation", body.model_dump())


@router.post("/participants/{participant_id}/distributions/hardship")
def hardship_distribution(
    participant_id: str,
    body: HardshipBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "hardship_distribution", body.model_dump())


@router.post("/participants/{participant_id}/distributions/in-service")
def in_service_distribution(
    participant_id: str,
    body: RmdBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "in_service_distribution", body.model_dump())


@router.post("/participants/{participant_id}/distributions/separation")
def separation_distribution(
    participant_id: str,
    body: SeparationBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "separation_distribution", body.model_dump())


@router.post("/participants/{participant_id}/distributions/rmd")
def rmd_distribution(
    participant_id: str,
    body: RmdBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "rmd", body.model_dump())


@router.put("/participants/{participant_id}/beneficiary")
def beneficiary_update(
    participant_id: str,
    body: BeneficiaryBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "beneficiary_update", body.model_dump())


@router.post("/participants/{participant_id}/qdro")
def qdro(
    participant_id: str,
    body: QdroBody,
    session: SessionToken = Depends(get_session),
):
    return _write(session, participant_id, "qdro", body.model_dump())
