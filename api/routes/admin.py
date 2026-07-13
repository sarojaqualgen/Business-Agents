"""
Admin endpoints — plan sponsors only.

GET  /admin/audit        — FAP audit log (all compliance decisions)
GET  /admin/blackout     — blackout status for a plan
POST /admin/blackout     — activate or lift a blackout (crew-routed)
"""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from api.auth import SessionToken, get_session
from api.streaming import stream_crew
from agents.fap.agent import get_all_audit_records
from crew.router import route

router = APIRouter()


def _sponsor_only(session: SessionToken) -> None:
    if session.principal_type not in ("plan_sponsor", "plan_trustee"):
        raise HTTPException(403, "Only plan sponsors can access admin endpoints")


@router.get("/audit")
def audit_log(session: SessionToken = Depends(get_session)):
    _sponsor_only(session)
    records = get_all_audit_records()
    return {
        "count": len(records),
        "note":  "Audit log stored in PostgreSQL fap_audit_log (falls back to in-memory if DB unavailable).",
        "records": [
            {
                "audit_id":       r.audit_id,
                "timestamp":      r.timestamp,
                "agent_id":       r.agent_id,
                "participant_id": r.participant_id,
                "plan_id":        r.plan_id,
                "action":         r.action,
                "authorized":     r.authorized,
                "autonomy_level": getattr(r, "autonomy_level", None),
                "denial_code":    getattr(r, "denial_code", None),
                "denial_reason":  getattr(r, "denial_reason", None),
            }
            for r in records
        ],
    }


class BlackoutRequest(BaseModel):
    message: str   # natural-language — routed through SponsorCrew


@router.post("/blackout")
async def manage_blackout(
    req: BlackoutRequest,
    session: SessionToken = Depends(get_session),
):
    _sponsor_only(session)
    crew = route(
        principal_type=session.principal_type,
        query=req.message,
        participant_id=session.participant_id or "",
        plan_id=session.plan_id or "",
        agent_id=session.agent_id,
    )
    return StreamingResponse(
        stream_crew(crew, session.principal_type),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
