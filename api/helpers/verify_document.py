"""
Document verification — Azure Document Intelligence + Claude Haiku.

Verification pipeline:
  1. Azure DI extraction result (ExtractionResult) arrives pre-populated from documents.py.
  2. Rule-based doc-type validity check (no LLM — pure lookup).
  3. Rule-based name match using Azure DI's extracted CustomerName (no LLM).
  4. Claude Haiku — three explicit checks in one call:
       a. Document authenticity — is this actually a [doc_type]?
       b. Expense coherence    — does content support the claimed [expense_type]?
       c. Name match           — does the person on the doc match the participant?
     Haiku receives the pre-extracted fields so its prompt is short and its job is narrow.

If Azure DI was not available (extraction.available == False), the caller passes the
locally extracted plain text through extraction.text and Haiku handles everything.
"""

import json
import logging

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static lookup tables
# ---------------------------------------------------------------------------

_VALID_DOC_TYPES: dict[str, list[str]] = {
    "medical":               ["medical_bill", "hospital_statement", "doctor_invoice", "explanation_of_benefits"],
    "tuition":               ["tuition_invoice", "enrollment_verification", "financial_aid_letter"],
    "prevent_eviction":      ["eviction_notice", "foreclosure_letter", "utility_shutoff_notice"],
    "funeral":               ["funeral_invoice", "death_certificate"],
    "primary_home_purchase": ["purchase_agreement", "contractor_estimate", "builder_contract"],
    "casualty_loss":         ["insurance_claim", "damage_assessment"],
    "FEMA_disaster":         ["FEMA_declaration", "damage_proof"],
    "qdro":                  ["court_order", "divorce_decree"],
}

_REQUIRED_FIELDS: dict[str, str] = {
    "medical_bill":             "patient name, medical provider/hospital, date of service, amount due",
    "hospital_statement":       "patient name, hospital name, admission or discharge dates, balance owed",
    "doctor_invoice":           "patient name, physician/clinic, visit date, amount due",
    "explanation_of_benefits":  "patient name, insurer name, claim date, covered/denied amounts",
    "tuition_invoice":          "student name, institution name, semester/term, tuition amount due",
    "enrollment_verification":  "student name, institution name, enrollment period/status",
    "financial_aid_letter":     "student name, institution name, aid award amounts",
    "eviction_notice":          "tenant name, property address, overdue rent amount, eviction/pay-or-quit date",
    "foreclosure_letter":       "borrower name, property address, lender name, foreclosure date",
    "utility_shutoff_notice":   "account holder name, utility company, amount owed, shutoff date",
    "funeral_invoice":          "deceased or payer name, funeral home name, service date, amount due",
    "death_certificate":        "deceased person name, date of death, issuing authority",
    "purchase_agreement":       "buyer name, property address, purchase price, closing date",
    "contractor_estimate":      "homeowner/client name, contractor name, work description, estimated cost",
    "builder_contract":         "buyer/owner name, builder name, property description, contract price",
    "insurance_claim":          "claimant name, insurance company, claim date, loss description, claim amount",
    "damage_assessment":        "property owner name, assessor/adjuster, damage description, repair estimate",
    "FEMA_declaration":         "applicant name or FEMA declaration number, disaster type, declared area",
    "damage_proof":             "property address or owner name, damage description",
    "court_order":              "participant name, alternate payee name, court name, case number, benefit amount or percentage",
    "divorce_decree":           "parties' names, court name, case number, date signed by judge",
}

# What the document clearly SHOULD NOT look like — used in the adversarial check prompt
_IMPOSTOR_HINTS: dict[str, str] = {
    "medical_bill":        "bank statement, pay stub, utility bill, grocery receipt, letter, ID, tax form",
    "hospital_statement":  "bank statement, pay stub, utility bill, grocery receipt, letter, ID",
    "doctor_invoice":      "bank statement, pay stub, utility bill, grocery receipt, letter, ID",
    "tuition_invoice":     "medical bill, eviction notice, bank statement, grocery receipt, personal letter",
    "eviction_notice":     "medical bill, tuition invoice, bank statement, court order, personal letter",
    "foreclosure_letter":  "medical bill, tuition invoice, bank statement, personal letter",
    "funeral_invoice":     "medical bill, tuition invoice, bank statement, grocery receipt, utility bill",
    "court_order":         "medical bill, tuition invoice, eviction notice, personal letter, bank statement",
    "divorce_decree":      "medical bill, tuition invoice, eviction notice, personal letter, bank statement",
    "purchase_agreement":  "medical bill, tuition invoice, bank statement, personal letter",
    "insurance_claim":     "bank statement, grocery receipt, personal letter, utility bill",
    "FEMA_declaration":    "bank statement, grocery receipt, personal letter, tuition invoice",
}


# ---------------------------------------------------------------------------
# Name matching helpers — rule-based, no LLM
# ---------------------------------------------------------------------------

# Suffixes that appear after surnames and must be stripped before comparison
_NAME_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "2nd", "3rd", "esq"}


def _name_tokens(raw: str) -> list[str]:
    """Lower-case, strip punctuation, drop name suffixes."""
    return [
        t.lower().strip(".,")
        for t in raw.split()
        if t.lower().strip(".,") not in _NAME_SUFFIXES and t.strip(".,")
    ]


def _names_match(participant_name: str, extracted_name: str) -> bool:
    """
    Return True if *extracted_name* belongs to *participant_name*.

    Rules (in order — first match wins):
    1. Exact token match (after suffix stripping and lower-casing).
    2. One token list is a subset of the other — handles "Amara Osei" vs "Amara B. Osei".
    3. Both first AND last name match — the only multi-token partial match allowed.
       (First-name-only match is rejected: too many people share a first name.)
    4. Extracted name is a single token → it must be the participant's LAST name.
    """
    p = _name_tokens(participant_name)
    e = _name_tokens(extracted_name)

    if not p or not e:
        return False

    # Rule 1 — exact
    if p == e:
        return True

    # Rule 2 — one is a subset of the other
    if set(p).issubset(set(e)) or set(e).issubset(set(p)):
        return True

    # Rule 3 — first AND last must both match (for multi-token names on both sides)
    if len(p) >= 2 and len(e) >= 2:
        return p[0] == e[0] and p[-1] == e[-1]

    # Rule 4 — extracted is a single token: must be the surname, not just a first name
    if len(p) >= 2 and len(e) == 1:
        return e[0] == p[-1]
    if len(e) >= 2 and len(p) == 1:
        return p[0] == e[-1]

    return False


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def verify_document(
    doc_type: str,
    expense_type: str,
    action_type: str,
    content_text: str,
    participant_name: str = "",
    extraction=None,          # ExtractionResult from azure_doc_intelligence (optional)
) -> dict:
    """
    Verify a document using Azure DI structured fields + Claude Haiku.

    Returns:
        {
          "verified":         bool,
          "note":             str,   # one sentence explaining the outcome
          "key_details":      str,   # amount + date + provider (for audit record)
          "name_on_document": str,   # name Azure DI or Haiku found on the document
          "name_match":       bool,
        }
    """
    # ------------------------------------------------------------------
    # 1. Rule-based doc-type validity (no LLM needed)
    # ------------------------------------------------------------------
    valid_types = _VALID_DOC_TYPES.get(expense_type, [])
    if valid_types and doc_type not in valid_types:
        return {
            "verified":         False,
            "note":             (
                f"Document type '{doc_type}' is not valid for expense category "
                f"'{expense_type}'. Expected one of: {', '.join(valid_types)}."
            ),
            "key_details":      "",
            "name_on_document": "",
            "name_match":       False,
        }

    # ------------------------------------------------------------------
    # 2. Rule-based name match using Azure DI's extracted CustomerName
    #    (skips one LLM call when the name is already structured)
    # ------------------------------------------------------------------
    adi_customer_name = ""
    adi_amount        = ""
    adi_date          = ""
    adi_vendor        = ""
    adi_available     = False

    if extraction is not None and getattr(extraction, "available", False):
        adi_available     = True
        adi_customer_name = extraction.customer_name or ""
        adi_amount        = extraction.amount        or ""
        adi_date          = extraction.date          or ""
        adi_vendor        = extraction.vendor_name   or ""
        if not content_text.strip():
            content_text = extraction.text

    name_on_document = adi_customer_name
    name_match: bool | None = None   # None = not yet determined

    if participant_name and adi_customer_name:
        name_match = _names_match(participant_name, adi_customer_name)
        if not name_match:
            return {
                "verified":         False,
                "note":             (
                    f"Name on document ('{adi_customer_name}') does not match "
                    f"participant '{participant_name}'. Rejected."
                ),
                "key_details":      _fmt_key_details(adi_amount, adi_date, adi_vendor),
                "name_on_document": adi_customer_name,
                "name_match":       False,
            }

    # ------------------------------------------------------------------
    # 3. Haiku — three adversarial checks in one call
    # ------------------------------------------------------------------
    return _haiku_verify(
        doc_type          = doc_type,
        expense_type      = expense_type,
        action_type       = action_type,
        content_text      = content_text,
        participant_name  = participant_name,
        adi_available     = adi_available,
        adi_customer_name = adi_customer_name,
        adi_amount        = adi_amount,
        adi_date          = adi_date,
        adi_vendor        = adi_vendor,
        name_match_known  = name_match,
    )


# ---------------------------------------------------------------------------
# Haiku call
# ---------------------------------------------------------------------------

def _fmt_key_details(amount: str, date: str, vendor: str) -> str:
    parts = [p for p in [amount, date, vendor] if p]
    return ", ".join(parts)


def _haiku_verify(
    doc_type: str,
    expense_type: str,
    action_type: str,
    content_text: str,
    participant_name: str,
    adi_available: bool,
    adi_customer_name: str,
    adi_amount: str,
    adi_date: str,
    adi_vendor: str,
    name_match_known: "bool | None",
) -> dict:
    try:
        import anthropic
        from data import document_store

        client    = anthropic.Anthropic(timeout=30.0)
        action_lbl = action_type.replace("_", " ")
        doc_lbl    = document_store.DOC_TYPE_LABELS.get(doc_type, doc_type)
        req_fields = _REQUIRED_FIELDS.get(doc_type, "relevant financial or legal information")
        impostors  = _IMPOSTOR_HINTS.get(doc_type, "an unrelated personal document")

        # Pre-extracted fields block (Azure DI)
        if adi_available and any([adi_vendor, adi_customer_name, adi_amount, adi_date]):
            extracted_block = (
                "PRE-EXTRACTED FIELDS (Azure Document Intelligence — treat as ground truth):\n"
                + (f"  Vendor / Provider : {adi_vendor}\n"        if adi_vendor        else "")
                + (f"  Customer / Patient: {adi_customer_name}\n" if adi_customer_name else "")
                + (f"  Amount            : {adi_amount}\n"        if adi_amount         else "")
                + (f"  Date              : {adi_date}\n"          if adi_date           else "")
                + "\n"
            )
        else:
            extracted_block = ""

        # Name check instruction
        if name_match_known is not None:
            name_instruction = (
                f"CHECK 3 — NAME MATCH (already resolved by Azure DI — do NOT override):\n"
                f"  name_on_document = '{adi_customer_name}'\n"
                f"  name_match       = {str(name_match_known).lower()}\n"
                f"  Copy these values exactly into your JSON response.\n"
            )
        elif participant_name:
            if action_type == "qdro":
                name_instruction = (
                    f"CHECK 3 — NAME MATCH (QDRO court order):\n"
                    f"  In a QDRO, the plan member who owns the 401(k) account is the PARTICIPANT.\n"
                    f"  The ex-spouse or other person receiving a portion of the benefit is the ALTERNATE PAYEE.\n"
                    f"  The document is submitted BY the plan participant — their name belongs in the PARTICIPANT field.\n"
                    f"  The logged-in participant is: '{participant_name}'.\n"
                    f"  PASS (name_match=true) if '{participant_name}' appears ANYWHERE in the document — as PARTICIPANT, as ALTERNATE PAYEE, or anywhere else.\n"
                    f"  FAIL (name_match=false, verified=false) ONLY if '{participant_name}' does not appear in the document at all.\n"
                    f"  The alternate payee having a different name is correct and expected — do NOT fail because of that.\n"
                    f"  Use strict matching: last name must match. First name alone is not enough.\n"
                )
            else:
                name_instruction = (
                    f"CHECK 3 — NAME MATCH:\n"
                    f"  Find any person name on the document (patient, tenant, student, buyer, payer, account holder).\n"
                    f"  The logged-in participant is: '{participant_name}'.\n"
                    f"  If the name on the document MATCHES '{participant_name}' → name_match=true.\n"
                    f"  If the name on the document does NOT match '{participant_name}' → verified=false, name_match=false.\n"
                    f"  If NO name is visible on the document at all → verified=false, name_match=false.\n"
                    f"  Use strict matching: last name must match. First name alone is not enough.\n"
                )
        else:
            name_instruction = (
                "CHECK 3 — NAME MATCH: No participant name supplied — skip it, set name_match=true.\n"
            )

        prompt = (
            f"You are a strict ERISA 401(k) document fraud-prevention agent.\n"
            f"Your default assumption is that the document may be INCORRECT or FRAUDULENT.\n"
            f"Set verified=true ONLY when all three checks below clearly pass.\n\n"
            f"A participant submitted a document for a '{action_lbl}' "
            f"(expense category: {expense_type}).\n\n"
            f"{extracted_block}"
            f"DOCUMENT TEXT (first 4000 characters):\n"
            f"──────────────────────────────────────\n"
            f"{content_text[:4000]}\n"
            f"──────────────────────────────────────\n\n"
            f"Run ALL three checks. Set verified=false if ANY check fails.\n\n"
            f"CHECK 1 — DOCUMENT AUTHENTICITY:\n"
            f"  The participant claims this is a '{doc_lbl}'.\n"
            f"  A genuine '{doc_lbl}' must contain ALL of: {req_fields}.\n"
            f"  Ask yourself: could this actually be a {impostors} that someone mislabeled?\n"
            f"  If the document is missing most required fields, looks like a different document type,\n"
            f"  or shows no clear evidence it was issued by a relevant institution → verified=false.\n\n"
            f"CHECK 2 — EXPENSE COHERENCE:\n"
            f"  Does the document's content directly support a '{expense_type}' expense?\n"
            f"  Example failures: a medical bill uploaded as an eviction notice; a grocery receipt\n"
            f"  uploaded as a funeral invoice; a personal letter uploaded as a court order.\n"
            f"  Even if the format looks right, the PURPOSE must match '{expense_type}' → "
            f"if not, verified=false.\n\n"
            f"{name_instruction}\n"
            f"Respond in JSON only (no markdown, no explanation outside the JSON):\n"
            f'{{"verified": true/false, '
            f'"note": "one sentence — which check failed and exactly why, or confirming all three passed", '
            f'"key_details": "amount + date + provider/institution extracted from the doc (empty string if not found)", '
            f'"name_on_document": "exact name found on the document, or empty string", '
            f'"name_match": true/false}}'
        )

        msg = client.messages.create(
            model      = "claude-haiku-4-5-20251001",
            max_tokens = 350,
            messages   = [{"role": "user", "content": prompt}],
        )

        raw = msg.content[0].text.strip()
        # Strip markdown fences Haiku occasionally wraps around JSON
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        result = json.loads(raw.strip())

        # Lock in rule-based values so Haiku cannot override them
        if name_match_known is not None:
            result["name_on_document"] = adi_customer_name
            result["name_match"]       = name_match_known

        # Merge Azure DI key_details if Haiku returned none
        if not result.get("key_details") and adi_available:
            result["key_details"] = _fmt_key_details(adi_amount, adi_date, adi_vendor)

        return result

    except Exception as exc:
        log.error("Haiku verification error: %s", exc)
        return {
            "verified":         False,
            "note":             f"Verification service unavailable: {str(exc)[:80]}",
            "key_details":      _fmt_key_details(adi_amount, adi_date, adi_vendor),
            "name_on_document": adi_customer_name,
            "name_match":       name_match_known if name_match_known is not None else False,
        }
