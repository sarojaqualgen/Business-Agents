"""
Document upload routes.

POST /documents/upload-fast  — direct Haiku verification, returns JSON
GET  /documents/participant  — list participant's own documents

Accepts: .txt  .pdf  .docx
"""

import io
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.auth import SessionToken, get_session
from api.helpers.verify_document import verify_document
from data import document_store

router = APIRouter()

_ALLOWED = {".txt", ".pdf", ".docx", ".doc"}


def _minio_url(object_key: str):
    if not object_key:
        return None
    try:
        from data import minio_client  # noqa: PLC0415
        return minio_client.get_presigned_url(object_key)
    except Exception:
        return None


@router.get("/participant")
def get_participant_documents(session: SessionToken = Depends(get_session)):
    """Return all documents uploaded by the logged-in participant, with MinIO download URLs."""
    from data import document_store as ds
    ds.reload()
    docs = ds.get_by_participant(session.participant_id or "")
    return {
        "participant_id": session.participant_id,
        "count":          len(docs),
        "documents": [
            {
                "doc_id":               d.doc_id,
                "doc_type":             d.doc_type,
                "doc_type_label":       ds.DOC_TYPE_LABELS.get(d.doc_type, d.doc_type),
                "filename":             d.filename,
                "queue_entry_id":       d.queue_entry_id,
                "uploaded_at":          d.uploaded_at,
                "verified":             d.verified,
                "verification_note":    d.verification_note,
                "sponsor_doc_approved": d.sponsor_doc_approved,
                "content_preview":      d.content_preview,
                "download_url":         _minio_url(d.object_key),
            }
            for d in docs
        ],
    }


def _extract_text(filename: str, content: bytes) -> str:
    ext = Path(filename).suffix.lower()

    if ext not in _ALLOWED:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. Accepted: {', '.join(sorted(_ALLOWED))}"
        )

    if ext == ".txt":
        return content.decode("utf-8", errors="replace")

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                text = "\n".join(page.extract_text() or "" for page in pdf.pages)
            return text.strip()
        except ImportError:
            raise HTTPException(
                400, "PDF support requires pdfplumber — run: pip install pdfplumber"
            )
        except Exception as exc:
            raise HTTPException(400, f"Could not read PDF: {exc}")

    if ext in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs)
            return text.strip()
        except ImportError:
            raise HTTPException(
                400, "DOCX support requires python-docx — run: pip install python-docx"
            )
        except Exception as exc:
            raise HTTPException(400, f"Could not read DOCX: {exc}")

    raise HTTPException(400, f"Unsupported file type: {ext}")


@router.post(
    "/upload-fast",
    summary="Upload and verify a supporting document (fast path — JSON response, no SSE)",
)
async def upload_document_fast(
    queue_entry_id: str = Form(...),
    action_type: str   = Form(...),
    expense_type: str  = Form(...),
    doc_type: str      = Form(...),
    file: UploadFile   = File(...),
    session: SessionToken = Depends(get_session),
):
    """
    Same as /upload but calls verify_document() directly (Haiku, no CrewAI).
    Returns plain JSON — used by the fast chat portal UI.
    """
    if session.principal_type not in ("participant", "participant_delegate", "investment_advisor"):
        raise HTTPException(403, "Only participants can upload documents")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")

    text = _extract_text(file.filename or "document.txt", content)
    if not text.strip():
        raise HTTPException(400, "Could not extract any text from the document")

    # Optional MinIO upload — ignore if not configured
    object_key = ""
    try:
        from data import minio_client  # noqa: PLC0415
        object_key = minio_client.upload_document(
            participant_id=session.participant_id or "unknown",
            filename=file.filename or f"{doc_type}.bin",
            content=content,
            content_type=file.content_type or "application/octet-stream",
        )
    except Exception:
        pass

    # Look up participant name for name-match check
    participant_name = ""
    try:
        from data.db import get_participant_name  # noqa: PLC0415
        participant_name = get_participant_name(session.participant_id or "")
    except Exception:
        pass

    # LLM verification — direct Haiku call, no CrewAI
    verification = verify_document(
        doc_type=doc_type,
        expense_type=expense_type,
        action_type=action_type,
        content_text=text,
        participant_name=participant_name,
    )

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = document_store.upload(
        participant_id=session.participant_id or "",
        plan_id=session.plan_id or "",
        queue_entry_id=queue_entry_id,
        action_type=action_type,
        expense_type=expense_type,
        doc_type=doc_type,
        filename=file.filename or f"{doc_type}.txt",
        content_preview=text[:500],
        object_key=object_key,
        uploaded_at=now,
    )
    document_store.mark_verified(
        doc_id=doc_id,
        verified=verification.get("verified", False),
        note=verification.get("note", ""),
        verified_at=now,
    )

    return {
        "doc_id":              doc_id,
        "filename":            file.filename or f"{doc_type}.txt",
        "queue_entry_id":      queue_entry_id,
        "verified":            verification.get("verified", False),
        "verification_note":   verification.get("note", ""),
        "key_details":         verification.get("key_details", ""),
        "name_on_document":    verification.get("name_on_document", ""),
        "name_match":          verification.get("name_match", False),
    }
