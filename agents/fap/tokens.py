"""
FAP JWT token issuance and validation.

Tokens are:
- Signed with a plan-level secret (mock: env var FAP_JWT_SECRET)
- Scoped to: agent_id, participant_id, plan_id, action, payload_hash
- Single-use: consumed tokens are tracked in an in-memory set (production: Redis)
- TTL: 300 seconds
"""

import hashlib
import json
import os
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from agents.fap.models import ActionType, AutonomyLevel

_SECRET = os.getenv("FAP_JWT_SECRET", "dev-only-insecure-secret-change-in-production")
_ALGORITHM = "HS256"
_TTL_SECONDS = 300

# In production this is Redis or a DB table.
_consumed_tokens: set[str] = set()


def _payload_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()


def issue_token(
    agent_id: str,
    participant_id: str,
    plan_id: str,
    action: ActionType,
    autonomy_level: AutonomyLevel,
    payload: dict,
) -> tuple[str, str, str]:
    """
    Issue a signed JWT authorization token.

    Returns (token_string, token_id, expires_at_iso).
    """
    token_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(seconds=_TTL_SECONDS)

    claims = {
        "jti": token_id,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "agent_id": agent_id,
        "participant_id": participant_id,
        "plan_id": plan_id,
        "action": action.value,
        "autonomy_level": autonomy_level.value,
        "payload_hash": _payload_hash(payload),
    }

    token_str = jwt.encode(claims, _SECRET, algorithm=_ALGORITHM)
    return token_str, token_id, expires_at.isoformat()


def validate_token(
    token_str: str,
    expected_action: str,
    expected_participant_id: str,
    expected_payload: dict,
) -> tuple[bool, str]:
    """
    Validate a FAP token before PAAP executes a write.

    Returns (is_valid, reason_if_invalid).
    """
    try:
        claims = jwt.decode(token_str, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return False, "Token has expired."
    except jwt.InvalidTokenError as exc:
        return False, f"Invalid token: {exc}"

    token_id = claims.get("jti", "")
    if token_id in _consumed_tokens:
        return False, "Token has already been consumed (single-use)."

    if claims.get("action") != expected_action:
        return False, f"Token action mismatch: expected '{expected_action}', got '{claims.get('action')}'."

    if claims.get("participant_id") != expected_participant_id:
        return False, "Token participant_id mismatch."

    actual_hash = _payload_hash(expected_payload)
    if claims.get("payload_hash") != actual_hash:
        return False, "Payload hash mismatch — token does not match submitted transaction."

    _consumed_tokens.add(token_id)
    return True, ""


def revoke_token(token_id: str) -> None:
    """Mark a token as consumed so it cannot be used."""
    _consumed_tokens.add(token_id)
