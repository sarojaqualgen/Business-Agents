"""
Azure Document Intelligence — extraction helper.

Submits a document (PDF, image, DOCX, or plain text) to Azure Document Intelligence
for OCR and structured field extraction.  Falls back gracefully when the service is
not configured or unavailable.

Models used:
  prebuilt-invoice  — invoice-type documents: extracts VendorName, CustomerName,
                      InvoiceTotal, InvoiceDate as structured JSON fields.
  prebuilt-read     — everything else: OCR-quality text extraction that works on
                      scanned images and digital documents alike.

Environment variables required:
  AZURE_DOC_INTELLIGENCE_ENDPOINT  e.g. https://qualgen-document-intelligence.cognitiveservices.azure.com
  AZURE_DOC_INTELLIGENCE_KEY       your Azure resource key (never committed to source control)
"""

import logging
import os
import time
from dataclasses import dataclass

import requests

log = logging.getLogger(__name__)

_ENDPOINT    = os.getenv("AZURE_DOC_INTELLIGENCE_ENDPOINT", "").rstrip("/")
_API_KEY     = os.getenv("AZURE_DOC_INTELLIGENCE_KEY", "")
_API_VERSION = "2024-11-30"

_POLL_TIMEOUT_S  = 20   # give up after this many seconds
_POLL_INTERVAL_S = 2    # re-check every N seconds

# File extension → Content-Type sent to Azure DI
_MIME: dict[str, str] = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
    ".tiff": "image/tiff",
    ".tif":  "image/tiff",
    ".bmp":  "image/bmp",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc":  "application/msword",
}

# File types Azure DI can process — plain text (.txt) is NOT supported by the service
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset(_MIME.keys())

# These doc types carry structured invoice fields — use the invoice model so Azure DI
# returns VendorName, CustomerName, InvoiceTotal, etc. as typed fields.
_INVOICE_DOC_TYPES: set[str] = {
    "medical_bill",
    "hospital_statement",
    "doctor_invoice",
    "tuition_invoice",
    "funeral_invoice",
    "insurance_claim",
    "contractor_estimate",
    "builder_contract",
}


@dataclass
class ExtractionResult:
    """Structured output from Azure Document Intelligence."""
    available: bool     = False  # False → service not configured or call failed
    text: str           = ""     # Full OCR text (all pages combined)
    model_used: str     = ""     # "prebuilt-invoice" or "prebuilt-read"
    vendor_name: str    = ""     # Provider / institution name (invoice model only)
    customer_name: str  = ""     # Patient / student / tenant name (invoice model only)
    amount: str         = ""     # Formatted currency string e.g. "$1,865.00"
    date: str           = ""     # Invoice or service date string
    confidence: float   = 0.0   # Azure DI document-level confidence (0–1)


def is_configured() -> bool:
    """Return True if Azure DI credentials are present in the environment."""
    return bool(_ENDPOINT and _API_KEY)


def analyze_document(
    file_bytes: bytes,
    filename: str,
    doc_type: str,
) -> ExtractionResult:
    """
    Submit *file_bytes* to Azure Document Intelligence and return an ExtractionResult.

    If the service is not configured or the call fails for any reason, returns
    ExtractionResult(available=False) so the caller can fall back to local extraction.
    """
    if not is_configured():
        return ExtractionResult(available=False)

    ext         = ("." + filename.rsplit(".", 1)[-1]).lower() if "." in filename else ""
    content_type = _MIME.get(ext, "application/octet-stream")
    model        = "prebuilt-invoice" if doc_type in _INVOICE_DOC_TYPES else "prebuilt-read"

    try:
        result = _submit_and_poll(file_bytes, content_type, model)
        return _parse_result(result, model)
    except Exception as exc:
        log.warning("Azure DI extraction failed (%s) — caller will fall back to local extraction", exc)
        return ExtractionResult(available=False)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _submit_and_poll(file_bytes: bytes, content_type: str, model: str) -> dict:
    """POST the document and poll until Azure DI returns 'succeeded'."""
    submit_url = (
        f"{_ENDPOINT}/documentintelligence/documentModels/"
        f"{model}:analyze?api-version={_API_VERSION}"
    )
    resp = requests.post(
        submit_url,
        headers={
            "Ocp-Apim-Subscription-Key": _API_KEY,
            "Content-Type": content_type,
        },
        data=file_bytes,
        timeout=15,
    )
    resp.raise_for_status()

    operation_url = (
        resp.headers.get("Operation-Location")
        or resp.headers.get("operation-location")
    )
    if not operation_url:
        raise ValueError("Azure DI response missing Operation-Location header")

    poll_headers = {"Ocp-Apim-Subscription-Key": _API_KEY}
    deadline     = time.time() + _POLL_TIMEOUT_S

    while time.time() < deadline:
        time.sleep(_POLL_INTERVAL_S)
        poll = requests.get(operation_url, headers=poll_headers, timeout=15)
        poll.raise_for_status()
        data   = poll.json()
        status = data.get("status")

        if status == "succeeded":
            return data
        if status == "failed":
            raise RuntimeError(f"Azure DI analysis failed: {data.get('error', {})}")

    raise TimeoutError(f"Azure DI analysis did not complete within {_POLL_TIMEOUT_S}s")


def _parse_result(data: dict, model: str) -> ExtractionResult:
    """Convert the raw Azure DI JSON response into an ExtractionResult."""
    analyze = data.get("analyzeResult", {})
    text    = analyze.get("content", "")

    out = ExtractionResult(
        available  = True,
        text       = text,
        model_used = model,
    )

    if model != "prebuilt-invoice":
        return out

    documents = analyze.get("documents", [])
    if not documents:
        return out

    doc    = documents[0]
    fields = doc.get("fields", {})
    out.confidence = doc.get("confidence", 0.0)

    def _str(key: str) -> str:
        f = fields.get(key, {})
        return str(f.get("valueString") or f.get("content") or "").strip()

    def _currency(key: str) -> str:
        f   = fields.get(key, {})
        val = f.get("valueCurrency")
        if val and val.get("amount") is not None:
            return f"${val['amount']:,.2f}"
        return str(f.get("content") or "").strip()

    out.vendor_name   = _str("VendorName")
    out.customer_name = _str("CustomerName")
    out.date          = _str("InvoiceDate") or _str("DueDate") or _str("ServiceDate")
    out.amount        = (
        _currency("InvoiceTotal")
        or _currency("AmountDue")
        or _currency("SubTotal")
    )

    return out
