"""
PLAP REST endpoints — Plan Agent Protocol.

GET /plap/plans/{plan_id}                  — full plan record
GET /plap/plans/{plan_id}/capabilities     — what this plan supports
GET /plap/plans/{plan_id}/vesting          — vesting schedule
GET /plap/plans/{plan_id}/funds            — fund lineup
GET /plap/plans/{plan_id}/blackout-status  — active blackout period

All endpoints require an authenticated session.
PLAP is read-only — no writes.
"""

from fastapi import APIRouter, Depends, HTTPException

from api.auth import SessionToken, get_session
from agents.plap.agent import (
    PlanNotFound,
    query_blackout_status,
    query_capabilities,
    query_fund_lineup,
    query_plan,
    query_vesting,
)

router = APIRouter()


def _get_plan_id(plan_id: str, session: SessionToken) -> str:
    """Verify the caller is allowed to read this plan."""
    if session.plan_id and session.plan_id != plan_id:
        raise HTTPException(403, "You are not associated with this plan.")
    return plan_id


@router.get("/plans/{plan_id}")
def get_plan_record(plan_id: str, session: SessionToken = Depends(get_session)):
    _get_plan_id(plan_id, session)
    try:
        plan = query_plan(plan_id)
    except PlanNotFound as e:
        raise HTTPException(404, str(e))
    return plan.model_dump()


@router.get("/plans/{plan_id}/capabilities")
def get_capabilities(plan_id: str, session: SessionToken = Depends(get_session)):
    _get_plan_id(plan_id, session)
    try:
        return query_capabilities(plan_id)
    except PlanNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/plans/{plan_id}/vesting")
def get_vesting(plan_id: str, session: SessionToken = Depends(get_session)):
    _get_plan_id(plan_id, session)
    try:
        return query_vesting(plan_id)
    except PlanNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/plans/{plan_id}/funds")
def get_funds(plan_id: str, session: SessionToken = Depends(get_session)):
    _get_plan_id(plan_id, session)
    try:
        return query_fund_lineup(plan_id)
    except PlanNotFound as e:
        raise HTTPException(404, str(e))


@router.get("/plans/{plan_id}/blackout-status")
def get_blackout_status(plan_id: str, session: SessionToken = Depends(get_session)):
    _get_plan_id(plan_id, session)
    try:
        return query_blackout_status(plan_id)
    except PlanNotFound as e:
        raise HTTPException(404, str(e))
