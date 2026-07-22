"""
FAP JWT token issuance and validation.

Tokens are:
- Signed with a plan-level secret (env var FAP_JWT_SECRET)
- Scoped to: agent_id, participant_id, plan_id, action, payload_hash
- Single-use: tracked in PostgreSQL fap_tokens table (fallback: in-memory set)
- TTL: 24 hours — human_review entries need time for sponsor + participant steps

Phase 6: issue_token() writes to fap_tokens, validate_token() uses atomic
db.consume_token(), unconsume_token() writes to db for saga rollback.
Falls back to the in-memory set if DATABASE_URL is not configured.
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
_TTL_SECONDS = 86400  # 24 hours

# Fallback when DB is not available
_consumed_tokens: set[str] = set()


def _normalize_payload(obj):
    """Normalize floats to int where possible so JSONB round-trips don't change the hash.
    PostgreSQL JSONB stores 30000.0 as 30000 — this keeps hashes consistent."""
    if isinstance(obj, float) and obj.is_integer():
        return int(obj)
    if isinstance(obj, dict):
        return {k: _normalize_payload(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_payload(v) for v in obj]
    return obj


def _payload_hash(payload: dict) -> str:
    canonical = json.dumps(_normalize_payload(payload), sort_keys=True, default=str)
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
    Writes to PostgreSQL fap_tokens table (best-effort; falls back silently if DB unavailable).
    Returns (token_string, token_id, expires_at_iso).
    """
    token_id = str(uuid.uuid4())
    now = datetime.now(tz=timezone.utc)
    expires_at = now + timedelta(seconds=_TTL_SECONDS)

    claims = {
        "jti":            token_id,
        "iat":            int(now.timestamp()),
        "exp":            int(expires_at.timestamp()),
        "agent_id":       agent_id,
        "participant_id": participant_id,
        "plan_id":        plan_id,
        "action":         action.value,
        "autonomy_level": autonomy_level.value,
        "payload_hash":   _payload_hash(payload),
    }

    token_str = jwt.encode(claims, _SECRET, algorithm=_ALGORITHM)

    # Persist to DB (best-effort — fallback is JWT signature alone)
    try:
        from data import db  # noqa: PLC0415
        db.write_token(
            token_id=token_id,
            expires_at=expires_at,
            agent_id=agent_id,
            participant_id=participant_id,
            plan_id=plan_id,
            action=action.value,
            payload_hash=claims["payload_hash"],
        )
    except Exception:
        pass

    return token_str, token_id, expires_at.isoformat()


def validate_token(
    token_str: str,
    expected_action: str,
    expected_participant_id: str,
    expected_payload: dict,
) -> tuple[bool, str]:
    """
    Validate a FAP token before PAAP executes a write.
    Uses atomic db.consume_token() (PostgreSQL) to prevent double-spend.
    Falls back to the in-memory set if DB is unavailable.
    Returns (is_valid, reason_if_invalid).
    """
    try:
        claims = jwt.decode(token_str, _SECRET, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        return False, "Token has expired."
    except jwt.InvalidTokenError as exc:
        return False, f"Invalid token: {exc}"

    token_id = claims.get("jti", "")

    if claims.get("action") != expected_action:
        return False, f"Token action mismatch: expected '{expected_action}', got '{claims.get('action')}'."

    if claims.get("participant_id") != expected_participant_id:
        return False, "Token participant_id mismatch."

    actual_hash = _payload_hash(expected_payload)
    if claims.get("payload_hash") != actual_hash:
        return False, "Payload hash mismatch — token does not match submitted transaction."

    # Atomically consume via DB — returns False if already consumed or expired
    try:
        from data import db  # noqa: PLC0415
        if not db.consume_token(token_id):
            # Distinguish "consumed/expired" from "never written to DB" (silent write failure).
            # If the row doesn't exist, the JWT is still cryptographically valid — use in-memory
            # double-spend tracking so participants can complete their transactions.
            try:
                if not db.token_exists(token_id):
                    if token_id in _consumed_tokens:
                        return False, "Token has already been consumed (single-use)."
                    _consumed_tokens.add(token_id)
                    return True, ""
            except Exception:
                pass
            return False, "Token has already been consumed (single-use) or has expired."
        return True, ""
    except Exception:
        # DB unavailable — fall back to in-memory set
        if token_id in _consumed_tokens:
            return False, "Token has already been consumed (single-use)."
        _consumed_tokens.add(token_id)
        return True, ""


def revoke_token(token_id: str) -> None:
    """Mark a token as consumed so it cannot be used."""
    try:
        from data import db  # noqa: PLC0415
        db.consume_token(token_id)
    except Exception:
        _consumed_tokens.add(token_id)


def unconsume_token(token_str: str) -> None:
    """Saga rollback compensation — reverse a token consumption if execution fails after
    the token was consumed. Allows the participant to retry with the same token."""
    try:
        claims = jwt.decode(
            token_str, _SECRET, algorithms=[_ALGORITHM],
            options={"verify_exp": False},
        )
        token_id = claims.get("jti", "")
        if not token_id:
            return
        # DB rollback first
        try:
            from data import db  # noqa: PLC0415
            db.unconsume_token_db(token_id)
        except Exception:
            pass
        # Also clear from fallback set
        _consumed_tokens.discard(token_id)
    except Exception:
        pass
