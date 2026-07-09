"""
Review queue endpoints — plan sponsors only.

GET  /queue                      — list pending items
GET  /queue/{id}                 — single entry detail
GET  /queue/{id}/docs            — uploaded documents for an entry
POST /queue/{id}/approve-docs    — sponsor explicitly approves the documents
POST /queue/{id}/approve         — approve the request (blocked until docs approved for hardship/qdro)
POST /queue/{id}/deny            — deny the request
"""

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.auth import SessionToken, get_session
from data import document_store as ds
from data.review_queue import (
    approve,
    approve_awaiting_bank,
    deny,
    get_all,
    get_entry,
    get_pending,
    reload as rq_reload,
)

# Actions that disburse funds — sponsor approval moves them to awaiting_bank_details
# instead of fully approved, so participant can provide bank details next.
_DISBURSEMENT_ACTIONS = {"loan_initiation", "hardship_distribution", "in_service_distribution"}

router = APIRouter()

_DOC_REQUIRED = {"hardship_distribution", "qdro"}


def _sponsor_only(session: SessionToken) -> None:
    if session.principal_type not in ("plan_sponsor", "plan_trustee"):
        raise HTTPException(403, "Only plan sponsors can access the review queue")


class NoteBody(BaseModel):
    note: Optional[str] = ""


@router.get("")
def list_queue(session: SessionToken = Depends(get_session)):
    _sponsor_only(session)
    rq_reload()
    ds.reload()
    entries = get_pending()
    return {
        "count": len(entries),
        "entries": [
            {
                "entry_id":              e.entry_id,
                "participant_id":        e.participant_id,
                "plan_id":               e.plan_id,
                "action":                e.action,
                "payload":               e.payload,
                "status":                e.status,
                "created_at":            e.created_at,
                "doc_count":             len(ds.get_by_entry(e.entry_id)),
                "docs_llm_verified":     sum(1 for d in ds.get_by_entry(e.entry_id) if d.verified),
                "docs_sponsor_approved": sum(1 for d in ds.get_by_entry(e.entry_id) if d.sponsor_doc_approved),
                "requires_docs":         e.action in _DOC_REQUIRED,
            }
            for e in entries
        ],
    }


@router.get("/{entry_id}")
def get_queue_entry(entry_id: str, session: SessionToken = Depends(get_session)):
    _sponsor_only(session)
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(404, f"Queue entry '{entry_id}' not found")
    return entry


@router.get("/{entry_id}/docs")
def get_entry_documents(entry_id: str, session: SessionToken = Depends(get_session)):
    _sponsor_only(session)
    ds.reload()
    docs = ds.get_by_entry(entry_id)
    return {
        "entry_id":   entry_id,
        "doc_count":  len(docs),
        "documents": [
            {
                "doc_id":               d.doc_id,
                "doc_type":             d.doc_type,
                "doc_type_label":       ds.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
                "filename":             d.filename,
                "uploaded_at":          d.uploaded_at,
                "verified":             d.verified,
                "verification_note":    d.verification_note,
                "sponsor_doc_approved": d.sponsor_doc_approved,
                "sponsor_doc_note":     d.sponsor_doc_note,
                "content_preview":      d.content_text[:400],
            }
            for d in docs
        ],
    }


@router.post("/{entry_id}/approve-docs")
def approve_documents(
    entry_id: str,
    body: NoteBody,
    session: SessionToken = Depends(get_session),
):
    _sponsor_only(session)
    ds.reload()
    docs = ds.get_by_entry(entry_id)
    if not docs:
        raise HTTPException(404, f"No documents found for entry '{entry_id}'")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    updated = ds.approve_by_sponsor(entry_id=entry_id, note=body.note or "", approved_at=now)
    return {
        "entry_id":       entry_id,
        "approved_count": len(updated),
        "message":        "Documents approved. You may now approve the request.",
    }


@router.post("/{entry_id}/approve")
def approve_request(
    entry_id: str,
    body: NoteBody,
    session: SessionToken = Depends(get_session),
):
    _sponsor_only(session)
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(404, f"Queue entry '{entry_id}' not found")

    if entry.status != "pending":
        raise HTTPException(
            400,
            f"Cannot approve entry '{entry_id}' — current status is '{entry.status}'. "
            "Only pending entries can be approved."
        )

    # Gate: hardship and QDRO require sponsor-approved documents first
    if entry.action in _DOC_REQUIRED:
        ds.reload()
        sponsor_approved = [d for d in ds.get_by_entry(entry_id) if d.sponsor_doc_approved]
        if not sponsor_approved:
            raise HTTPException(
                400,
                "Documents must be reviewed and approved before approving this request. "
                "Call POST /queue/{entry_id}/approve-docs first."
            )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    if entry.action in _DISBURSEMENT_ACTIONS:
        # Funds need to move — hold until participant provides bank details
        result = approve_awaiting_bank(entry_id, sponsor_note=body.note or "", resolved_at=now)
        if not result:
            raise HTTPException(500, "Failed to approve entry")
        return {
            "status":   "approved_awaiting_bank_details",
            "entry_id": entry_id,
            "message":  "Approved. Participant must now provide bank details via POST /transactions/disburse to receive funds.",
        }

    result = approve(entry_id, sponsor_note=body.note or "", resolved_at=now)
    if not result:
        raise HTTPException(500, "Failed to approve entry")
    return {"status": "approved", "entry_id": entry_id}


@router.post("/{entry_id}/deny")
def deny_request(
    entry_id: str,
    body: NoteBody,
    session: SessionToken = Depends(get_session),
):
    _sponsor_only(session)
    entry = get_entry(entry_id)
    if not entry:
        raise HTTPException(404, f"Queue entry '{entry_id}' not found")

    if entry.status != "pending":
        raise HTTPException(
            400,
            f"Cannot deny entry '{entry_id}' — current status is '{entry.status}'. "
            "Only pending entries can be denied."
        )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = deny(entry_id, sponsor_note=body.note or "", resolved_at=now)
    if not result:
        raise HTTPException(500, "Failed to deny entry")
    return {"status": "denied", "entry_id": entry_id}
