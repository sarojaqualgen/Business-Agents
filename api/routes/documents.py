"""
Document upload routes.

POST /documents/upload-fast  — Azure DI extraction → Haiku verification → JSON response
GET  /documents/participant  — list participant's own documents

Accepted file types:
  Images (Azure DI OCR):  .jpg  .jpeg  .png  .tiff  .tif  .bmp
  Documents:              .pdf  .docx  .doc  .txt

Azure Document Intelligence is used first for all file types.
When not configured, falls back to local extraction (pdfplumber / python-docx / utf-8 decode).
"""

import io
import logging
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from api.auth import SessionToken, get_session
from api.helpers.azure_doc_intelligence import (
    ExtractionResult, SUPPORTED_EXTENSIONS, analyze_document, is_configured,
)
from api.helpers.verify_document import verify_document
from data import document_store

log    = logging.getLogger(__name__)
router = APIRouter()

# All file types accepted at the upload endpoint.
# Images are only useful when Azure DI is configured (OCR); otherwise they would produce
# no text and fail immediately — that is handled in _extract_text_local().
_ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt",
    ".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp",
}


# ---------------------------------------------------------------------------
# Local extraction fallback (no Azure DI)
# ---------------------------------------------------------------------------

def _extract_text_local(filename: str, content: bytes) -> str:
    """
    Best-effort local text extraction.  Only works well for digital (non-scanned)
    PDFs and DOCX.  Images return an empty string — caller will reject the upload
    with a clear message if Azure DI is not configured.
    """
    ext = Path(filename).suffix.lower()

    if ext == ".txt":
        return content.decode("utf-8", errors="replace")

    if ext == ".pdf":
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(content)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages).strip()
        except ImportError:
            raise HTTPException(400, "PDF support requires pdfplumber: pip install pdfplumber")
        except Exception as exc:
            raise HTTPException(400, f"Could not read PDF: {exc}")

    if ext in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            return "\n".join(p.text for p in doc.paragraphs).strip()
        except ImportError:
            raise HTTPException(400, "DOCX support requires python-docx: pip install python-docx")
        except Exception as exc:
            raise HTTPException(400, f"Could not read DOCX: {exc}")

    # Images — require Azure DI
    return ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minio_url(object_key: str):
    if not object_key:
        return None
    try:
        from data import minio_client
        return minio_client.get_presigned_url(object_key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/participant")
def get_participant_documents(session: SessionToken = Depends(get_session)):
    """Return all documents uploaded by the logged-in participant."""
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


@router.post(
    "/upload-fast",
    summary="Upload and verify a supporting document",
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
    1. Read the uploaded file.
    2. Send to Azure Document Intelligence for OCR + structured field extraction.
       Falls back to local text extraction when Azure DI is not configured.
    3. Verify the extracted content with Claude Haiku (semantic content + name match).
    4. Store the document record and return the verification result.
    """
    if session.principal_type not in ("participant", "participant_delegate", "investment_advisor"):
        raise HTTPException(403, "Only participants can upload documents")

    filename = file.filename or f"{doc_type}.bin"
    ext      = Path(filename).suffix.lower()

    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            400,
            f"Unsupported file type '{ext}'. "
            f"Accepted: {', '.join(sorted(_ALLOWED_EXTENSIONS))}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")

    # ------------------------------------------------------------------
    # Step 1 — Extract text and structured fields
    # ------------------------------------------------------------------
    extraction: ExtractionResult

    # PDFs and images always go through Azure DI — a PDF may contain scanned
    # pages or embedded images that pdfplumber cannot read.
    # DOCX and TXT are always pure text so local extraction is sufficient.
    _LOCAL_ONLY_EXTS = {".docx", ".doc", ".txt"}

    if ext in _LOCAL_ONLY_EXTS:
        content_text = _extract_text_local(filename, content)
        extraction   = ExtractionResult(available=False, text=content_text)
        log.info("Local extraction: %d chars from %s", len(content_text), ext)
    elif is_configured() and ext in SUPPORTED_EXTENSIONS:
        # PDF or image — send to Azure DI for OCR / structured extraction.
        extraction = analyze_document(
            file_bytes = content,
            filename   = filename,
            doc_type   = doc_type,
        )
        if extraction.available:
            content_text = extraction.text
            log.info(
                "Azure DI complete: model=%s vendor='%s' customer='%s' amount='%s'",
                extraction.model_used, extraction.vendor_name,
                extraction.customer_name, extraction.amount,
            )
        else:
            # Azure DI failed — fall back to local extraction.
            content_text = _extract_text_local(filename, content)
    else:
        # Azure DI not configured — local extraction for everything.
        content_text = _extract_text_local(filename, content)
        extraction   = ExtractionResult(available=False, text=content_text)

    # Images with no Azure DI produce no text — reject cleanly
    if not content_text.strip():
        if ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif", ".bmp"):
            raise HTTPException(
                400,
                "Image files require Azure Document Intelligence to be configured. "
                "Please upload a PDF, DOCX, or TXT file instead.",
            )
        raise HTTPException(400, "Could not extract any text from the uploaded document")

    # ------------------------------------------------------------------
    # Step 2 — Optional MinIO upload (ignore if not configured)
    # ------------------------------------------------------------------
    object_key = ""
    try:
        from data import minio_client
        object_key = minio_client.upload_document(
            participant_id = session.participant_id or "unknown",
            filename       = filename,
            content        = content,
            content_type   = file.content_type or "application/octet-stream",
        )
        log.info("MinIO upload OK: %s", object_key)
    except Exception as _minio_err:
        log.warning("MinIO upload failed (document saved without file): %s", _minio_err)

    # ------------------------------------------------------------------
    # Step 3 — Participant name for name-match check
    # ------------------------------------------------------------------
    participant_name = ""
    try:
        from data.db import get_participant_name
        participant_name = get_participant_name(session.participant_id or "") or ""
    except Exception:
        pass

    # ------------------------------------------------------------------
    # Step 4 — Verify (Azure DI structured fields + Haiku semantic check)
    # ------------------------------------------------------------------
    verification = verify_document(
        doc_type         = doc_type,
        expense_type     = expense_type,
        action_type      = action_type,
        content_text     = content_text,
        participant_name = participant_name,
        extraction       = extraction,
    )

    # ------------------------------------------------------------------
    # Step 5 — Persist document record
    # ------------------------------------------------------------------
    now    = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc_id = document_store.upload(
        participant_id = session.participant_id or "",
        plan_id        = session.plan_id or "",
        queue_entry_id = queue_entry_id,
        action_type    = action_type,
        expense_type   = expense_type,
        doc_type       = doc_type,
        filename       = filename,
        content_preview= content_text[:500],
        object_key     = object_key,
        uploaded_at    = now,
    )
    document_store.mark_verified(
        doc_id     = doc_id,
        verified   = verification.get("verified", False),
        note       = verification.get("note", ""),
        verified_at= now,
    )

    return {
        "doc_id":           doc_id,
        "filename":         filename,
        "queue_entry_id":   queue_entry_id,
        "extraction_model": extraction.model_used or "local",
        "verified":         verification.get("verified", False),
        "verification_note":verification.get("note", ""),
        "key_details":      verification.get("key_details", ""),
        "name_on_document": verification.get("name_on_document", ""),
        "name_match":       verification.get("name_match", False),
    }
