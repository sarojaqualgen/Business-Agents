"""
Document tools — handle participant document uploads and sponsor document retrieval.

UploadDocumentTool  — participant uploads a document (file path or text)
GetDocumentsTool    — sponsor retrieves all docs for a queue entry

Document verification runs automatically on upload via verify_document().
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from data import document_store


# ---------------------------------------------------------------------------
# Standalone document verification — uses Anthropic SDK directly
# ---------------------------------------------------------------------------

def verify_document(
    doc_type: str,
    expense_type: str,
    action_type: str,
    content_text: str,
) -> dict:
    """
    Call Claude to verify whether the uploaded document matches the claimed
    action and expense type. Returns {verified, note, key_details}.
    """
    try:
        import anthropic
        client = anthropic.Anthropic()

        action_label = action_type.replace("_", " ")
        doc_label = document_store.DOC_TYPE_LABELS.get(doc_type, doc_type)

        prompt = (
            f"You are a document verification agent for an ERISA 401(k) plan administrator.\n\n"
            f"A participant has submitted a document claiming it is a '{doc_label}' "
            f"in support of a '{action_label}' request (expense category: {expense_type}).\n\n"
            f"Document content:\n"
            f"──────────────────\n"
            f"{content_text[:2000]}\n"
            f"──────────────────\n\n"
            f"Evaluate whether this document:\n"
            f"1. Is the correct document type for the claimed expense\n"
            f"2. Contains the key information expected (amounts, dates, provider/institution)\n"
            f"3. Appears to be a legitimate document (not obviously fabricated)\n\n"
            f"Respond in JSON only:\n"
            f'{{"verified": true/false, "note": "one sentence reason", "key_details": "amount, date, provider extracted from the doc"}}'
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())

    except Exception as exc:
        return {
            "verified": False,
            "note": f"Verification service unavailable: {str(exc)[:80]}",
            "key_details": "",
        }


# ---------------------------------------------------------------------------
# UploadDocumentTool
# ---------------------------------------------------------------------------

class UploadDocumentInput(BaseModel):
    participant_id: str = Field(description="Participant ID, e.g. PART-008")
    plan_id: str = Field(description="Plan ID, e.g. PLAN-003")
    queue_entry_id: str = Field(description="Review queue entry ID this document belongs to")
    action_type: str = Field(description="Action type: hardship_distribution or qdro")
    expense_type: str = Field(description="Expense category: medical, tuition, prevent_eviction, funeral, etc. Use 'qdro' for QDRO court orders.")
    doc_type: str = Field(description="Document type: medical_bill, eviction_notice, tuition_invoice, funeral_invoice, court_order, etc.")
    file_path: str = Field(description="Absolute path to the document file, or pass the text content directly prefixed with 'TEXT:'")


class UploadDocumentTool(BaseTool):
    name: str = "UploadDocument"
    description: str = (
        "Upload a supporting document for a participant's human_review request. "
        "Automatically verifies the document matches the claimed action. "
        "Returns doc_id and verification result."
    )
    args_schema: type[BaseModel] = UploadDocumentInput

    def _run(
        self,
        participant_id: str,
        plan_id: str,
        queue_entry_id: str,
        action_type: str,
        expense_type: str,
        doc_type: str,
        file_path: str,
    ) -> str:
        # Read content
        if file_path.startswith("TEXT:"):
            content_text = file_path[5:].strip()
            filename = f"{doc_type}.txt"
        else:
            try:
                content_text = Path(file_path).read_text(encoding="utf-8", errors="replace")
                filename = Path(file_path).name
            except Exception as exc:
                return json.dumps({"error": f"Could not read file: {exc}"})

        if not content_text.strip():
            return json.dumps({"error": "Document is empty."})

        # Verify
        verification = verify_document(doc_type, expense_type, action_type, content_text)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        doc_id = document_store.upload(
            participant_id=participant_id,
            plan_id=plan_id,
            queue_entry_id=queue_entry_id,
            action_type=action_type,
            expense_type=expense_type,
            doc_type=doc_type,
            filename=filename,
            content_text=content_text,
            uploaded_at=now,
        )
        document_store.mark_verified(
            doc_id=doc_id,
            verified=verification.get("verified", False),
            note=verification.get("note", ""),
            verified_at=now,
        )

        return json.dumps({
            "doc_id": doc_id,
            "filename": filename,
            "verified": verification.get("verified", False),
            "verification_note": verification.get("note", ""),
            "key_details": verification.get("key_details", ""),
            "queue_entry_id": queue_entry_id,
        })


# ---------------------------------------------------------------------------
# GetDocumentsTool
# ---------------------------------------------------------------------------

class GetDocumentsInput(BaseModel):
    queue_entry_id: str = Field(description="Review queue entry ID to retrieve documents for")


class GetDocumentsTool(BaseTool):
    name: str = "GetDocuments"
    description: str = (
        "Retrieve all uploaded supporting documents for a specific review queue entry. "
        "Used by the plan sponsor when reviewing a human_review request. "
        "Returns document list with verification status."
    )
    args_schema: type[BaseModel] = GetDocumentsInput

    def _run(self, queue_entry_id: str) -> str:
        document_store.reload()
        docs = document_store.get_by_entry(queue_entry_id)

        if not docs:
            return json.dumps({
                "queue_entry_id": queue_entry_id,
                "document_count": 0,
                "documents": [],
                "note": "No documents uploaded for this entry yet.",
            })

        return json.dumps({
            "queue_entry_id": queue_entry_id,
            "document_count": len(docs),
            "documents": [
                {
                    "doc_id": d.doc_id,
                    "doc_type": d.doc_type,
                    "doc_type_label": document_store.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
                    "filename": d.filename,
                    "uploaded_at": d.uploaded_at,
                    "verified": d.verified,
                    "verification_note": d.verification_note,
                    "content_preview": d.content_text[:300],
                }
                for d in docs
            ],
        })
