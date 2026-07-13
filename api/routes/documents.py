"""
POST /documents/upload — participant uploads a supporting document.

Accepts: .txt  .pdf  .docx
Extracts text → passes to Document Verification Agent → streams SSE result.
"""

import io
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from api.auth import SessionToken, get_session
from api.streaming import stream_crew
from crew.crews.participant_crew import build_document_verification_crew

router = APIRouter()

_ALLOWED = {".txt", ".pdf", ".docx", ".doc"}


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


@router.post("/upload")
async def upload_document(
    queue_entry_id: str = Form(...),
    action_type: str   = Form(...),
    expense_type: str  = Form(...),
    doc_type: str      = Form(...),
    file: UploadFile   = File(...),
    session: SessionToken = Depends(get_session),
):
    if session.principal_type not in ("participant", "participant_delegate", "investment_advisor"):
        raise HTTPException(403, "Only participants can upload documents")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Uploaded file is empty")

    text = _extract_text(file.filename or "document.txt", content)
    if not text.strip():
        raise HTTPException(400, "Could not extract any text from the document")

    # Try to upload raw bytes to MinIO — gracefully falls back if MinIO is not configured
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
        pass  # MinIO not configured — store will use text-only mode

    # Pass extracted text via TEXT: prefix for LLM verification; object_key for MinIO reference
    crew = build_document_verification_crew(
        participant_id=session.participant_id or "",
        plan_id=session.plan_id or "",
        queue_entry_id=queue_entry_id,
        action_type=action_type,
        expense_type=expense_type,
        doc_type=doc_type,
        file_path=f"TEXT:{text}",
        object_key=object_key,
    )

    return StreamingResponse(
        stream_crew(crew, "document"),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",
            "Connection":       "keep-alive",
        },
    )
