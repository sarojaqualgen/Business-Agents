"""
Human Review Queue — stores transactions that FAP approved but flagged as autonomy_level=human_review.
Plan sponsor must approve or deny each entry before execution proceeds.

In production: database table with email/Slack notifications and 18-month QDRO window tracking.
Demo: persists to review_queue_state.json so the queue survives Ctrl+C / session restarts.
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
    fap_token: str              # stored until sponsor approves; 5-min TTL in prod → re-issue on approval
    status: str                 # "pending" | "approved" | "denied"
    sponsor_note: str
    created_at: str
    resolved_at: Optional[str] = None


_queue: list[ReviewQueueEntry] = []


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
        pass  # corrupt file — start fresh


_load()


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
    return [e for e in _queue if e.status == "pending"]


def get_all() -> list[ReviewQueueEntry]:
    return list(_queue)


def reload() -> None:
    """Re-read the queue from disk. Call before status checks so sponsor approvals
    made in a different session are immediately visible."""
    global _queue
    _queue.clear()
    _load()


def get_entry(entry_id: str) -> Optional[ReviewQueueEntry]:
    return next((e for e in _queue if e.entry_id == entry_id), None)


def approve(entry_id: str, sponsor_note: str = "", resolved_at: str = "") -> Optional[ReviewQueueEntry]:
    entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "pending"), None)
    if entry:
        entry.status = "approved"
        entry.sponsor_note = sponsor_note
        entry.resolved_at = resolved_at
        _save()
    return entry


def deny(entry_id: str, sponsor_note: str = "", resolved_at: str = "") -> Optional[ReviewQueueEntry]:
    entry = next((e for e in _queue if e.entry_id == entry_id and e.status == "pending"), None)
    if entry:
        entry.status = "denied"
        entry.sponsor_note = sponsor_note
        entry.resolved_at = resolved_at
        _save()
    return entry
