"""
Session auth — /auth/login issues a short-lived JWT.
Accepts either:
  { username, password }                                  — direct username login
  { principal_type, participant_id|plan_id, password }    — role-card dropdown UI

All protected routes require: Authorization: Bearer <session_token>
"""

import os
import time
from typing import Optional

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

SECRET = os.getenv("FAP_JWT_SECRET", "dev-insecure-secret")
SESSION_TTL = 3600  # 1 hour

router = APIRouter()
_bearer = HTTPBearer()


class LoginRequest(BaseModel):
    password: str
    # Username path
    username: Optional[str] = None
    # Role-card path (dropdown UI)
    principal_type: Optional[str] = None
    participant_id: Optional[str] = None
    plan_id: Optional[str] = None


class SessionToken(BaseModel):
    principal_type: str
    participant_id: Optional[str] = None
    plan_id: Optional[str] = None
    agent_id: str
    display_name: Optional[str] = None


_DEFAULT_AGENTS = {
    "participant":          "AGENT-PARTICIPANT-001",
    "participant_delegate": "AGENT-PARTICIPANT-001",
    "plan_sponsor":         "AGENT-SPONSOR-001",
    "plan_trustee":         "AGENT-SPONSOR-001",
    "investment_advisor":   "AGENT-ADVISOR-001",
}


@router.post("/login")
def login(req: LoginRequest):
    from data.credentials import verify_credentials, verify_by_ids

    if req.username:
        cred = verify_credentials(req.username, req.password)
    elif req.principal_type:
        cred = verify_by_ids(req.principal_type, req.participant_id, req.plan_id, req.password)
    else:
        raise HTTPException(400, "Provide username or principal_type.")

    if cred is None:
        raise HTTPException(401, "Invalid credentials.")

    pt       = cred["principal_type"]
    agent_id = _DEFAULT_AGENTS.get(pt, "AGENT-PARTICIPANT-001")

    payload = {
        "principal_type": pt,
        "participant_id": cred["participant_id"],
        "plan_id":        cred["plan_id"],
        "agent_id":       agent_id,
        "display_name":   cred["display_name"],
        "iat":            int(time.time()),
        "exp":            int(time.time()) + SESSION_TTL,
    }
    token = jwt.encode(payload, SECRET, algorithm="HS256")
    return {
        "session_token":  token,
        "expires_in":     SESSION_TTL,
        "principal_type": pt,
        "participant_id": cred["participant_id"],
        "plan_id":        cred["plan_id"],
        "display_name":   cred["display_name"],
    }


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
            display_name=payload.get("display_name"),
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Session expired — please log in again")
    except Exception:
        raise HTTPException(401, "Invalid session token")
