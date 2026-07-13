"""
Document Store — stores supporting documents uploaded by participants for human_review actions.

Currently: JSON-backed flat file (data/document_store.json).
Phase 6: PostgreSQL table (documents).

Each document is linked to a review_queue entry_id so the plan sponsor
can see all documents for a request when reviewing the queue.
"""

from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path
import json
import uuid

_STORE_FILE = Path(__file__).parent / "document_store.json"

# Required document types per expense type (hardship)
HARDSHIP_DOC_REQUIREMENTS: dict[str, list[str]] = {
    "medical":               ["medical_bill", "hospital_statement", "doctor_invoice", "explanation_of_benefits"],
    "tuition":               ["tuition_invoice", "enrollment_verification", "financial_aid_letter"],
    "prevent_eviction":      ["eviction_notice", "foreclosure_letter", "utility_shutoff_notice"],
    "funeral":               ["funeral_invoice", "death_certificate"],
    "primary_home_purchase": ["purchase_agreement", "contractor_estimate", "builder_contract"],
    "casualty_loss":         ["insurance_claim", "damage_assessment"],
    "FEMA_disaster":         ["FEMA_declaration", "damage_proof"],
}

# Human-readable doc type labels for CLI display
DOC_TYPE_LABELS: dict[str, str] = {
    "medical_bill":             "Medical bill / invoice",
    "hospital_statement":       "Hospital statement",
    "doctor_invoice":           "Doctor's invoice",
    "explanation_of_benefits":  "Explanation of benefits (EOB)",
    "tuition_invoice":          "Tuition invoice",
    "enrollment_verification":  "Enrollment verification letter",
    "financial_aid_letter":     "Financial aid letter",
    "eviction_notice":          "Eviction notice",
    "foreclosure_letter":       "Foreclosure letter",
    "utility_shutoff_notice":   "Utility shutoff notice",
    "funeral_invoice":          "Funeral home invoice",
    "death_certificate":        "Death certificate",
    "purchase_agreement":       "Purchase agreement",
    "contractor_estimate":      "Contractor estimate",
    "builder_contract":         "Builder contract",
    "insurance_claim":          "Insurance claim",
    "damage_assessment":        "Damage assessment report",
    "FEMA_declaration":         "FEMA disaster declaration",
    "damage_proof":             "Damage proof / photos",
    "court_order":              "Signed court order (QDRO)",
    "divorce_decree":           "Divorce decree",
}

# Sample document files (relative to data/sample_docs/)
SAMPLE_DOCS: dict[str, str] = {
    "medical_bill":             "medical_bill.txt",
    "eviction_notice":          "eviction_notice.txt",
    "tuition_invoice":          "tuition_invoice.txt",
    "funeral_invoice":          "funeral_invoice.txt",
    "court_order":              "qdro_court_order.txt",
}


@dataclass
class DocumentRecord:
    doc_id: str
    participant_id: str
    plan_id: str
    queue_entry_id: str
    action_type: str         # "hardship_distribution", "qdro"
    expense_type: str        # "medical", "qdro", etc.
    doc_type: str            # "medical_bill", "eviction_notice", etc.
    filename: str
    content_preview: str     # first 500 chars for sponsor quick-view
    uploaded_at: str
    object_key: str = ""             # MinIO object key — empty if MinIO not configured
    verified: bool = False           # LLM auto-verification result
    verification_note: str = ""
    verified_at: str = ""
    sponsor_doc_approved: bool = False   # sponsor explicitly reviewed and approved the document
    sponsor_doc_note: str = ""
    sponsor_doc_approved_at: str = ""


_store: list[DocumentRecord] = []


def _save() -> None:
    data = [
        {
            "doc_id": d.doc_id,
            "participant_id": d.participant_id,
            "plan_id": d.plan_id,
            "queue_entry_id": d.queue_entry_id,
            "action_type": d.action_type,
            "expense_type": d.expense_type,
            "doc_type": d.doc_type,
            "filename": d.filename,
            "content_preview": d.content_preview,
            "object_key": d.object_key,
            "uploaded_at": d.uploaded_at,
            "verified": d.verified,
            "verification_note": d.verification_note,
            "verified_at": d.verified_at,
            "sponsor_doc_approved": d.sponsor_doc_approved,
            "sponsor_doc_note": d.sponsor_doc_note,
            "sponsor_doc_approved_at": d.sponsor_doc_approved_at,
        }
        for d in _store
    ]
    try:
        _STORE_FILE.write_text(json.dumps(data, indent=2))
    except OSError:
        pass


def _load() -> None:
    if not _STORE_FILE.exists():
        return
    try:
        data = json.loads(_STORE_FILE.read_text())
        for d in data:
            # content_preview falls back to content_text for backward compat with old store files
            preview = d.get("content_preview", d.get("content_text", ""))[:500]
            _store.append(DocumentRecord(
                doc_id=d["doc_id"],
                participant_id=d["participant_id"],
                plan_id=d["plan_id"],
                queue_entry_id=d["queue_entry_id"],
                action_type=d["action_type"],
                expense_type=d["expense_type"],
                doc_type=d["doc_type"],
                filename=d["filename"],
                content_preview=preview,
                object_key=d.get("object_key", ""),
                uploaded_at=d["uploaded_at"],
                verified=d.get("verified", False),
                verification_note=d.get("verification_note", ""),
                verified_at=d.get("verified_at", ""),
                sponsor_doc_approved=d.get("sponsor_doc_approved", False),
                sponsor_doc_note=d.get("sponsor_doc_note", ""),
                sponsor_doc_approved_at=d.get("sponsor_doc_approved_at", ""),
            ))
    except Exception:
        pass


_load()


def upload(
    participant_id: str,
    plan_id: str,
    queue_entry_id: str,
    action_type: str,
    expense_type: str,
    doc_type: str,
    filename: str,
    content_preview: str,
    uploaded_at: str,
    object_key: str = "",
) -> str:
    doc_id = str(uuid.uuid4())[:8].upper()
    _store.append(DocumentRecord(
        doc_id=doc_id,
        participant_id=participant_id,
        plan_id=plan_id,
        queue_entry_id=queue_entry_id,
        action_type=action_type,
        expense_type=expense_type,
        doc_type=doc_type,
        filename=filename,
        content_preview=content_preview[:500],
        object_key=object_key,
        uploaded_at=uploaded_at,
    ))
    _save()
    return doc_id


def get_by_entry(queue_entry_id: str) -> list[DocumentRecord]:
    return [d for d in _store if d.queue_entry_id == queue_entry_id]


def get_by_participant(participant_id: str) -> list[DocumentRecord]:
    return [d for d in _store if d.participant_id == participant_id]


def mark_verified(doc_id: str, verified: bool, note: str, verified_at: str) -> Optional[DocumentRecord]:
    doc = next((d for d in _store if d.doc_id == doc_id), None)
    if doc:
        doc.verified = verified
        doc.verification_note = note
        doc.verified_at = verified_at
        _save()
    return doc


def approve_by_sponsor(
    entry_id: str,
    note: str = "",
    approved_at: str = "",
) -> list[DocumentRecord]:
    """Mark all documents for this queue entry as sponsor-approved."""
    updated = []
    for d in _store:
        if d.queue_entry_id == entry_id:
            d.sponsor_doc_approved = True
            d.sponsor_doc_note = note
            d.sponsor_doc_approved_at = approved_at
            updated.append(d)
    if updated:
        _save()
    return updated


def clear_all() -> None:
    global _store
    _store.clear()
    _save()


def reload() -> None:
    global _store
    _store.clear()
    _load()
