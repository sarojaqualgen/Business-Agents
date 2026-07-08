"""
Session auth — /auth/login issues a short-lived JWT.
All protected routes require: Authorization: Bearer <session_token>
"""

import os
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from data.participants import get_participant
from data.db import get_plan

SECRET = os.getenv("FAP_JWT_SECRET", "dev-insecure-secret")
SESSION_TTL = 3600  # 1 hour

router = APIRouter()
_bearer = HTTPBearer()


class LoginRequest(BaseModel):
    principal_type: str        # participant | plan_sponsor | plan_trustee | investment_advisor
    participant_id: Optional[str] = None
    plan_id: Optional[str] = None
    agent_id: Optional[str] = None


class SessionToken(BaseModel):
    principal_type: str
    participant_id: Optional[str] = None
    plan_id: Optional[str] = None
    agent_id: str


_DEFAULT_AGENTS = {
    "participant":        "AGENT-PARTICIPANT-001",
    "participant_delegate": "AGENT-PARTICIPANT-001",
    "plan_sponsor":       "AGENT-SPONSOR-001",
    "plan_trustee":       "AGENT-SPONSOR-001",
    "investment_advisor": "AGENT-ADVISOR-001",
}


@router.post("/login")
def login(req: LoginRequest):
    pt = req.principal_type

    if pt in ("participant", "participant_delegate", "investment_advisor"):
        if not req.participant_id or not req.plan_id:
            raise HTTPException(400, "participant_id and plan_id are required")
        p = get_participant(req.participant_id)
        if not p:
            raise HTTPException(404, f"Participant '{req.participant_id}' not found")

    elif pt in ("plan_sponsor", "plan_trustee"):
        if not req.plan_id:
            raise HTTPException(400, "plan_id is required")
        plan = get_plan(req.plan_id)
        if not plan:
            raise HTTPException(404, f"Plan '{req.plan_id}' not found")

    else:
        raise HTTPException(400, f"Unknown principal_type: '{pt}'")

    agent_id = req.agent_id or _DEFAULT_AGENTS.get(pt, "AGENT-001")

    payload = {
        "principal_type": pt,
        "participant_id": req.participant_id,
        "plan_id":        req.plan_id,
        "agent_id":       agent_id,
        "iat":            int(time.time()),
        "exp":            int(time.time()) + SESSION_TTL,
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    return {"session_token": token, "expires_in": SESSION_TTL}


def get_session(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> SessionToken:
    try:
        payload = jwt.decode(
            credentials.credentials, SECRET, algorithms=["HS256"]
        )
        return SessionToken(
            principal_type=payload["principal_type"],
            participant_id=payload.get("participant_id"),
            plan_id=payload.get("plan_id"),
            agent_id=payload["agent_id"],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired — please log in again")
    except Exception:
        raise HTTPException(401, "Invalid session token")
