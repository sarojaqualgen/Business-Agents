"""
Human Review Queue — stores transactions that FAP approved but flagged as autonomy_level=human_review.
Plan sponsor must approve or deny each entry before execution proceeds.

Phase 6: primary persistence is PostgreSQL (via data/db.py).
Falls back to in-memory list + review_queue_state.json if DATABASE_URL is not set.
"""

from dataclasses import dataclass
from typing import Any, Optional
from pathlib import Path
import json
import uuid

_QUEUE_FILE = Path(__file__).parent / "review_queue_state.json"


@dataclass
class ReviewQueueEntry:
    entry_id: str
    participant_id: str
    plan_id: str
    agent_id: str
    principal_type: str
    action: str
    payload: dict[str, Any]
    fap_audit_id: str
    fap_token: str              # stored until sponsor approves; re-issued on approval
    status: str                 # "pending" | "approved" | "denied" | "approved_awaiting_bank_details"
    sponsor_note: str
    created_at: str
    resolved_at: Optional[str] = None


# In-memory fallback
_queue: list[ReviewQueueEntry] = []


# ── JSON fallback helpers ────────────────────────────────────────────────────

def _save() -> None:
    data = [
        {
            "entry_id": e.entry_id,
            "participant_id": e.participant_id,
            "plan_id": e.plan_id,
            "agent_id": e.agent_id,
            "principal_type": e.principal_type,
            "action": e.action,
            "payload": e.payload,
            "fap_audit_id": e.fap_audit_id,
            "fap_token": e.fap_token,
            "status": e.status,
            "sponsor_note": e.sponsor_note,
            "created_at": e.created_at,
            "resolved_at": e.resolved_at,
        }
        for e in _queue
    ]
    try:
        _QUEUE_FILE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def _load() -> None:
    if not _QUEUE_FILE.exists():
        return
    try:
        data = json.loads(_QUEUE_FILE.read_text())
        for d in data:
            _queue.append(ReviewQueueEntry(**d))
    except Exception:
        pass


def _row_to_entry(r: dict) -> ReviewQueueEntry:
    return ReviewQueueEntry(
        entry_id=str(r["entry_id"]),
        participant_id=r.get("participant_id", ""),
        plan_id=r.get("plan_id", ""),
        agent_id=r.get("agent_id", ""),
        principal_type=r.get("principal_type", "participant"),
        action=r.get("action", ""),
        payload=r.get("payload") or {},
        fap_audit_id=r.get("fap_audit_id", ""),
        fap_token=r.get("fap_token", ""),
        status=r.get("status", "pending"),
        sponsor_note=r.get("sponsor_note", ""),
        created_at=str(r.get("created_at", "")),
        resolved_at=str(r["resolved_at"]) if r.get("resolved_at") else None,
    )


_load()


# ── Public API ───────────────────────────────────────────────────────────────

def enqueue(
    participant_id: str,
    plan_id: str,
    agent_id: str,
    principal_type: str,
    action: str,
    payload: dict[str, Any],
    fap_audit_id: str,
    fap_token: str,
    created_at: str,
) -> str:
    entry_id = str(uuid.uuid4())[:8].upper()

    # Try DB first
    try:
        from data import db  # noqa: PLC0415
        db.write_review_queue_entry(
            entry_id=entry_id,
            participant_id=participant_id,
            plan_id=plan_id,
            agent_id=agent_id,
            principal_type=principal_type,
            action=action,
            payload=payload,
            fap_audit_id=fap_audit_id,
            fap_token=fap_token,
            created_at=created_at,
        )
        return entry_id
    except Exception:
        pass

    # Fallback: in-memory + JSON
    _queue.append(ReviewQueueEntry(
        entry_id=entry_id,
        participant_id=participant_id,
        plan_id=plan_id,
        agent_id=agent_id,
        principal_type=principal_type,
        action=action,
        payload=payload,
        fap_audit_id=fap_audit_id,
        fap_token=fap_token,
        status="pending",
        sponsor_note="",
        created_at=created_at,
    ))
    _save()
    return entry_id


def get_pending() -> list[ReviewQueueEntry]:
    try:
        from data import db  # noqa: PLC0415
        rows = db.get_review_queue_pending()
        return [_row_to_entry(r) for r in rows]
    except Exception:
        pass
    return [e for e in _queue if e.status == "pending"]


def get_all() -> list[ReviewQueueEntry]:
    try:
        from data import db  # noqa: PLC0415
        rows = db.get_all_review_queue()
        return [_row_to_entry(r) for r in rows]
    except Exception:
        pass
    return list(_queue)


def reload() -> None:
    """Re-read the queue (from DB if available, otherwise from JSON).
    Call before status checks so sponsor actions in another session are visible."""
    global _queue
    _queue.clear()
    _load()


def get_entry(entry_id: str) -> Optional[ReviewQueueEntry]:
    try:
        from data import db  # noqa: PLC0415
        row = db.get_review_queue_entry(entry_id)
        if row:
            return _row_to_entry(row)
        return None
    except Exception:
        pass
    return next((e for e in _queue if e.entry_id == entry_id), None)


def approve(entry_id: str, sponsor_note: str = "", resolved_at: str = "") -> Optional[ReviewQueueEntry]:
    try:
        from data import db  # noqa: PLC0415
        db.update_review_queue_status(
            entry_id=entry_id,
            new_status="approved",
            sponsor_note=sponsor_note,
            resolved_at=resolved_at,
        )
        return get_entry(entry_id)
    except Exception:
        pass

    entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "pending"), None)
    if entry:
        entry.status = "approved"
        entry.sponsor_note = sponsor_note
        entry.resolved_at = resolved_at
        _save()
    return entry


def approve_awaiting_bank(entry_id: str, sponsor_note: str = "", resolved_at: str = "") -> Optional[ReviewQueueEntry]:
    """Approve a disbursement action; re-issue a fresh FAP token so participant has a full window."""
    # Fetch current entry to build token re-issue inputs
    entry = get_entry(entry_id)
    if not entry or entry.status != "pending":
        return entry

    new_token = entry.fap_token
    try:
        from agents.fap.tokens import issue_token
        from agents.fap.models import ActionType, AutonomyLevel
        new_token, _, _ = issue_token(
            agent_id=entry.agent_id,
            participant_id=entry.participant_id,
            plan_id=entry.plan_id,
            action=ActionType(entry.action),
            autonomy_level=AutonomyLevel.human_review,
            payload=entry.payload,
        )
    except Exception:
        pass

    # Persist new token then update status
    try:
        from data import db  # noqa: PLC0415
        db.update_review_queue_token(entry_id, new_token)
        db.update_review_queue_status(
            entry_id=entry_id,
            new_status="approved_awaiting_bank_details",
            sponsor_note=sponsor_note,
            resolved_at=resolved_at,
        )
        return get_entry(entry_id)
    except Exception:
        pass

    # Fallback
    mem_entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "pending"), None)
    if mem_entry:
        mem_entry.fap_token = new_token
        mem_entry.status = "approved_awaiting_bank_details"
        mem_entry.sponsor_note = sponsor_note
        mem_entry.resolved_at = resolved_at
        _save()
    return mem_entry


def reissue_bank_token(entry_id: str) -> Optional[ReviewQueueEntry]:
    """Re-issue a fresh FAP token for an entry already in approved_awaiting_bank_details."""
    entry = get_entry(entry_id)
    if not entry or entry.status != "approved_awaiting_bank_details":
        return entry
    try:
        from agents.fap.tokens import issue_token
        from agents.fap.models import ActionType, AutonomyLevel
        new_token, _, _ = issue_token(
            agent_id=entry.agent_id,
            participant_id=entry.participant_id,
            plan_id=entry.plan_id,
            action=ActionType(entry.action),
            autonomy_level=AutonomyLevel.human_review,
            payload=entry.payload,
        )
        try:
            from data import db  # noqa: PLC0415
            db.update_review_queue_token(entry_id, new_token)
        except Exception:
            pass
        mem_entry = next((e for e in _queue if e.entry_id == entry_id), None)
        if mem_entry:
            mem_entry.fap_token = new_token
            _save()
    except Exception:
        pass
    return get_entry(entry_id)


def finalize_disbursed(entry_id: str) -> Optional[ReviewQueueEntry]:
    """Mark entry as fully disbursed after participant provides bank details."""
    try:
        from data import db  # noqa: PLC0415
        db.update_review_queue_status(
            entry_id=entry_id,
            new_status="approved",
            sponsor_note="",
            resolved_at="",
        )
        return get_entry(entry_id)
    except Exception:
        pass

    entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "approved_awaiting_bank_details"), None)
    if entry:
        entry.status = "approved"
        _save()
    return entry


def deny(entry_id: str, sponsor_note: str = "", resolved_at: str = "") -> Optional[ReviewQueueEntry]:
    try:
        from data import db  # noqa: PLC0415
        db.update_review_queue_status(
            entry_id=entry_id,
            new_status="denied",
            sponsor_note=sponsor_note,
            resolved_at=resolved_at,
        )
        return get_entry(entry_id)
    except Exception:
        pass

    entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "pending"), None)
    if entry:
        entry.status = "denied"
        entry.sponsor_note = sponsor_note
        entry.resolved_at = resolved_at
        _save()
    return entry
