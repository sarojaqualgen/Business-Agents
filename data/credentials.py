"""
Demo user credentials — username + password authentication.

Password for every account: Demo2026!

Usernames:
  Participants:   gabriel.stone | amara.osei | daniela.reyes | yuki.tanaka
  Plan sponsors:  admin.capitalone | admin.prudential
"""

import hashlib
import hmac

_SALT = b"aldergate-erisa-demo-2026"


def _hash(pw: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", pw.encode("utf-8"), _SALT, 100_000).hex()


# Pre-computed hash for "Demo2026!" — avoids hashing on every startup
_DEMO_HASH = _hash("Demo2026!")

_CREDS: dict[str, dict] = {
    # ── Participants (Capital One PLAN-003) ─────────────────────────────────
    "gabriel.stone": {
        "hash":           _DEMO_HASH,
        "principal_type": "participant",
        "participant_id": "PART-006",
        "plan_id":        "PLAN-003",
        "display_name":   "Gabriel Stone",
    },
    "amara.osei": {
        "hash":           _DEMO_HASH,
        "principal_type": "participant",
        "participant_id": "PART-008",
        "plan_id":        "PLAN-003",
        "display_name":   "Amara Osei",
    },
    "daniela.reyes": {
        "hash":           _DEMO_HASH,
        "principal_type": "participant",
        "participant_id": "PART-009",
        "plan_id":        "PLAN-003",
        "display_name":   "Daniela Reyes",
    },
    # ── Participant (Prudential PLAN-004) ───────────────────────────────────
    "yuki.tanaka": {
        "hash":           _DEMO_HASH,
        "principal_type": "participant",
        "participant_id": "PART-007",
        "plan_id":        "PLAN-004",
        "display_name":   "Yuki Tanaka",
    },
    # ── Participant (Capital One PLAN-003) — RMD demo ──────────────────────
    "eleanor.walsh": {
        "hash":           _DEMO_HASH,
        "principal_type": "participant",
        "participant_id": "PART-010",
        "plan_id":        "PLAN-003",
        "display_name":   "Eleanor Walsh",
    },
    # ── Plan sponsors ───────────────────────────────────────────────────────
    "admin.capitalone": {
        "hash":           _DEMO_HASH,
        "principal_type": "plan_sponsor",
        "participant_id": None,
        "plan_id":        "PLAN-003",
        "display_name":   "Capital One Plan Administrator",
    },
    "admin.prudential": {
        "hash":           _DEMO_HASH,
        "principal_type": "plan_sponsor",
        "participant_id": None,
        "plan_id":        "PLAN-004",
        "display_name":   "Prudential Plan Administrator",
    },
}


def verify_credentials(username: str, password: str) -> dict | None:
    """Return credential dict if username + password are valid, else None."""
    cred = _CREDS.get(username.lower().strip())
    if cred is None:
        return None
    if hmac.compare_digest(_hash(password), cred["hash"]):
        return cred
    return None


# ── Lookup by participant_id / plan_id (used by the role-card UI) ───────────

_BY_PARTICIPANT_ID: dict[str, dict] = {
    v["participant_id"]: v
    for v in _CREDS.values()
    if v.get("participant_id")
}

_BY_PLAN_SPONSOR: dict[str, dict] = {
    v["plan_id"]: v
    for v in _CREDS.values()
    if v["principal_type"] == "plan_sponsor"
}


def verify_by_ids(
    principal_type: str,
    participant_id: str | None,
    plan_id: str | None,
    password: str,
) -> dict | None:
    """Look up credentials by role + ID instead of username — used by the dropdown UI."""
    if principal_type == "participant" and participant_id:
        cred = _BY_PARTICIPANT_ID.get(participant_id)
    elif principal_type == "plan_sponsor" and plan_id:
        cred = _BY_PLAN_SPONSOR.get(plan_id)
    else:
        return None
    if cred is None:
        return None
    if hmac.compare_digest(_hash(password), cred["hash"]):
        return cred
    return None
