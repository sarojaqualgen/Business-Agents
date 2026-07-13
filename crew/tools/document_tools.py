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
    participant_name: str = "",
) -> dict:
    """
    Call Claude Haiku to verify the uploaded document.
    Checks: correct type, key fields present, appears legitimate,
    and — when participant_name is supplied — that the name on the
    document matches the participant (not someone else's document).
    Returns {verified, note, key_details, name_match}.
    """
    try:
        import anthropic
        client = anthropic.Anthropic()

        action_label = action_type.replace("_", " ")
        doc_label = document_store.DOC_TYPE_LABELS.get(doc_type, doc_type)

        name_instruction = (
            f"4. The document must belong to the participant named '{participant_name}'. "
            f"If a patient name, account holder name, or recipient name is visible on the document "
            f"and it does NOT match '{participant_name}', set verified=false and explain the mismatch. "
            f"A document addressed to someone else is not acceptable — this protects against a participant "
            f"uploading another person's records.\n"
            if participant_name
            else "4. No participant name was supplied — skip the name check.\n"
        )

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
            f"3. Appears to be a legitimate document (not obviously fabricated)\n"
            f"{name_instruction}\n"
            f"Respond in JSON only:\n"
            f'{{"verified": true/false, "note": "one sentence reason", '
            f'"key_details": "amount, date, provider extracted from the doc", '
            f'"name_on_document": "name found on the document or empty string if none visible", '
            f'"name_match": true/false}}'
        )

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = message.content[0].text.strip()
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
            "name_on_document": "",
            "name_match": False,
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
    object_key: str = Field(default="", description="MinIO object key if the file was already uploaded to object storage by the API layer — leave empty for CLI/local uploads")


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
        object_key: str = "",
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

        # Look up participant name so LLM can check document belongs to them
        participant_name = ""
        try:
            from data.participants import get_participant  # noqa: PLC0415
            p = get_participant(participant_id)
            if p:
                participant_name = f"{p.first_name} {p.last_name}"
        except Exception:
            pass

        # Verify using full content text (LLM sees up to 2000 chars)
        verification = verify_document(doc_type, expense_type, action_type, content_text, participant_name)

        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        # Store first 500 chars as preview; full content lives in MinIO if object_key is set
        doc_id = document_store.upload(
            participant_id=participant_id,
            plan_id=plan_id,
            queue_entry_id=queue_entry_id,
            action_type=action_type,
            expense_type=expense_type,
            doc_type=doc_type,
            filename=filename,
            content_preview=content_text[:500],
            object_key=object_key,
            uploaded_at=now,
        )
        document_store.mark_verified(
            doc_id=doc_id,
            verified=verification.get("verified", False),
            note=verification.get("note", ""),
            verified_at=now,
        )

        result = {
            "doc_id": doc_id,
            "filename": filename,
            "verified": verification.get("verified", False),
            "verification_note": verification.get("note", ""),
            "key_details": verification.get("key_details", ""),
            "name_on_document": verification.get("name_on_document", ""),
            "name_match": verification.get("name_match", False),
            "queue_entry_id": queue_entry_id,
            "storage": "minio" if object_key else "local",
        }
        return json.dumps(result)


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

        doc_list = []
        for d in docs:
            entry = {
                "doc_id": d.doc_id,
                "doc_type": d.doc_type,
                "doc_type_label": document_store.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
                "filename": d.filename,
                "uploaded_at": d.uploaded_at,
                "verified": d.verified,
                "verification_note": d.verification_note,
                "content_preview": d.content_preview,
                "storage": "minio" if d.object_key else "local",
            }
            if d.object_key:
                try:
                    from data import minio_client  # noqa: PLC0415
                    entry["download_url"] = minio_client.get_presigned_url(d.object_key)
                except Exception:
                    entry["download_url"] = None
            doc_list.append(entry)

        return json.dumps({
            "queue_entry_id": queue_entry_id,
            "document_count": len(docs),
            "documents": doc_list,
        })
