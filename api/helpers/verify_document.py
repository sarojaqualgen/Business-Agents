"""
LLM-based document verification — calls Claude Haiku directly.

Checks that an uploaded document:
  - is the correct type for the claimed expense
  - contains the expected key fields (amounts, dates, provider)
  - appears legitimate
  - (when participant_name supplied) belongs to the correct person

No CrewAI dependency. Used by both the fast chat upload path and the
UploadDocumentTool CrewAI tool.
"""

import json

# Which doc_types are valid for each expense_type.
# If the submitted doc_type is not in this list → automatic rejection.
_VALID_DOC_TYPES: dict[str, list[str]] = {
    "medical":              ["medical_bill", "hospital_statement", "doctor_invoice", "explanation_of_benefits"],
    "tuition":              ["tuition_invoice", "enrollment_verification", "financial_aid_letter"],
    "prevent_eviction":     ["eviction_notice", "foreclosure_letter", "utility_shutoff_notice"],
    "funeral":              ["funeral_invoice", "death_certificate"],
    "primary_home_purchase":["purchase_agreement", "contractor_estimate", "builder_contract"],
    "casualty_loss":        ["insurance_claim", "damage_assessment"],
    "FEMA_disaster":        ["FEMA_declaration", "damage_proof"],
    "qdro":                 ["court_order", "divorce_decree"],
}

# What content signals identify each doc_type — tells Haiku what to look for
# to confirm the document actually IS what the participant claims.
_DOC_TYPE_SIGNALS: dict[str, str] = {
    "medical_bill":              "patient name, medical provider/hospital name, date of service, amount due/balance",
    "hospital_statement":        "patient name, hospital name, admission or discharge dates, balance owed",
    "doctor_invoice":            "patient name, physician/clinic name, visit date, amount due",
    "explanation_of_benefits":   "patient name, insurer name, claim date, covered/denied amounts",
    "tuition_invoice":           "student name, institution name, semester/term, tuition amount due",
    "enrollment_verification":   "student name, institution name, enrollment period/status",
    "financial_aid_letter":      "student name, institution name, aid award amounts",
    "eviction_notice":           "tenant name, property address, overdue rent amount, eviction/pay-or-quit date",
    "foreclosure_letter":        "borrower name, property address, lender name, foreclosure date",
    "utility_shutoff_notice":    "account holder name, utility company, amount owed, shutoff date",
    "funeral_invoice":           "deceased or payer name, funeral home name, service date, amount due",
    "death_certificate":         "deceased person name, date of death, issuing authority",
    "purchase_agreement":        "buyer name, property address, purchase price, closing date",
    "contractor_estimate":       "homeowner/client name, contractor name, work description, estimated cost",
    "builder_contract":          "buyer/owner name, builder name, property description, contract price",
    "insurance_claim":           "claimant name, insurance company, claim date, loss description, claim amount",
    "damage_assessment":         "property owner name, assessor/adjuster, damage description, repair estimate",
    "FEMA_declaration":          "applicant name or FEMA declaration number, disaster type, declared area",
    "damage_proof":              "property address or owner name, damage description, photos or written evidence",
    "court_order":               "participant name, alternate payee name, court name, case number, benefit amount or percentage",
    "divorce_decree":            "parties' names, court name, case number, date signed by judge",
}


def verify_document(
    doc_type: str,
    expense_type: str,
    action_type: str,
    content_text: str,
    participant_name: str = "",
) -> dict:
    """
    Returns { verified, note, key_details, name_on_document, name_match }.
    """
    try:
        import anthropic
        from data import document_store

        client = anthropic.Anthropic()

        action_label = action_type.replace("_", " ")
        doc_label = document_store.DOC_TYPE_LABELS.get(doc_type, doc_type)

        # Build doc-type validity context
        valid_types_for_expense = _VALID_DOC_TYPES.get(expense_type, [])
        doc_type_valid = doc_type in valid_types_for_expense
        expected_signals = _DOC_TYPE_SIGNALS.get(doc_type, "relevant financial or legal information")

        doc_type_rule = (
            f"DOCUMENT TYPE CHECK:\n"
            f"  - Participant claims this is a '{doc_label}' (doc_type='{doc_type}').\n"
            f"  - Valid document types for expense '{expense_type}': {valid_types_for_expense}.\n"
            + (
                f"  - '{doc_type}' IS a valid type for '{expense_type}' — proceed to content check.\n"
                if doc_type_valid
                else f"  - '{doc_type}' is NOT valid for expense type '{expense_type}'. "
                     f"Set verified=false immediately.\n"
            )
        )

        content_check_rule = (
            f"CONTENT CHECK — does the document ACTUALLY match what the participant claims?\n"
            f"  A '{doc_label}' must contain: {expected_signals}.\n"
            f"  If the document content is clearly something else (e.g., participant claims it is a medical "
            f"  bill but it reads like an eviction notice), set verified=false.\n"
            f"  If the required fields above are missing or the document looks like the wrong type, "
            f"  set verified=false.\n"
        )

        name_instruction = (
            f"NAME CHECK (hard rejection — do this last):\n"
            f"   The logged-in participant is '{participant_name}'.\n"
            f"   Look for any person name on the document: patient name, account holder, "
            f"   tenant, student, buyer, payer, borrower, or any named individual.\n"
            f"   - Name on document matches '{participant_name}' → name_match=true.\n"
            f"   - Name on document does NOT match '{participant_name}' → verified=false, name_match=false.\n"
            f"     This is a hard rejection regardless of all other criteria.\n"
            f"   - No name visible anywhere on the document → verified=false, name_match=false.\n"
            if participant_name
            else "NAME CHECK: No participant name was supplied — skip the name check, set name_match=true.\n"
        )

        prompt = (
            f"You are a document verification agent for an ERISA 401(k) plan administrator.\n\n"
            f"A participant submitted a document for a '{action_label}' request "
            f"(expense category: {expense_type}).\n\n"
            f"Document content:\n"
            f"──────────────────\n"
            f"{content_text[:2000]}\n"
            f"──────────────────\n\n"
            f"Run all three checks in order. Set verified=false if ANY check fails.\n\n"
            f"CHECK 1 — {doc_type_rule}\n"
            f"CHECK 2 — {content_check_rule}\n"
            f"CHECK 3 — {name_instruction}\n"
            f"Respond in JSON only:\n"
            f'{{"verified": true/false, "note": "one sentence stating which check failed and why, '
            f'or confirming all passed", '
            f'"key_details": "amount, date, provider extracted from the doc (empty string if not found)", '
            f'"name_on_document": "exact name found on the document, or empty string if none visible", '
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
