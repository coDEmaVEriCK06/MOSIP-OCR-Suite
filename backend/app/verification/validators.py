"""Structural verification of extracted identity-document fields.

Unlike the original project's "verification" (which merely compared two OCR
passes against each other and proved nothing), these checks validate the data
against the documents' real-world rules: the Aadhaar Verhoeff checksum, PAN and
passport format structure, and date-of-birth plausibility.
"""

import re
from datetime import datetime
from typing import List, Tuple

from app.models.analysis import (
    DocumentType,
    ExtractedField,
    FieldVerification,
    VerificationResult,
)

# --- Verhoeff checksum tables (Aadhaar's 12th digit is a Verhoeff check digit) ---
_D = [
    [0,1,2,3,4,5,6,7,8,9],[1,2,3,4,0,6,7,8,9,5],[2,3,4,0,1,7,8,9,5,6],
    [3,4,0,1,2,8,9,5,6,7],[4,0,1,2,3,9,5,6,7,8],[5,9,8,7,6,0,4,3,2,1],
    [6,5,9,8,7,1,0,4,3,2],[7,6,5,9,8,2,1,0,4,3],[8,7,6,5,9,3,2,1,0,4],
    [9,8,7,6,5,4,3,2,1,0],
]
_P = [
    [0,1,2,3,4,5,6,7,8,9],[1,5,7,6,2,8,3,0,9,4],[5,8,0,3,7,9,6,1,4,2],
    [8,9,1,6,0,4,3,5,2,7],[9,4,5,3,1,2,6,8,7,0],[4,2,8,6,5,7,3,9,0,1],
    [2,7,9,3,8,0,6,4,1,5],[7,0,4,6,9,1,3,2,5,8],
]


def verhoeff_valid(number: str) -> bool:
    """Validate a 12-digit Aadhaar number against its Verhoeff check digit."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) != 12:
        return False
    c = 0
    for i, d in enumerate(reversed(digits)):
        c = _D[c][_P[i % 8][d]]
    return c == 0


_PAN_RE = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")
_PASSPORT_RE = re.compile(r"^[A-PR-WY][0-9]{7}$")


def pan_format_valid(pan: str) -> Tuple[bool, str]:
    if _PAN_RE.match(pan.upper()):
        return True, "matches PAN structure (AAAAA9999A)"
    return False, "does not match PAN structure (AAAAA9999A)"


def passport_format_valid(number: str) -> Tuple[bool, str]:
    if _PASSPORT_RE.match(number.upper()):
        return True, "matches Indian passport number format"
    return False, "does not match Indian passport number format"


def dob_valid(dob: str) -> Tuple[bool, str]:
    for fmt in ("%d/%m/%Y", "%d-%m-%Y"):
        try:
            dt = datetime.strptime(dob, fmt)
        except ValueError:
            continue
        today = datetime.now()
        if dt > today:
            return False, "date of birth is in the future"
        if (today - dt).days / 365.25 > 120:
            return False, "implies an implausible age over 120"
        return True, "plausible calendar date"
    return False, "not a recognizable date"


def verify_document(doc_type: DocumentType, fields: List[ExtractedField]) -> VerificationResult:
    """Run the appropriate structural checks for the document type and fields."""
    fmap = {f.name: f.value for f in fields}
    checks: List[FieldVerification] = []

    if doc_type == DocumentType.AADHAAR and "aadhaar_number" in fmap:
        ok = verhoeff_valid(fmap["aadhaar_number"])
        checks.append(FieldVerification(
            field="aadhaar_number", check="verhoeff_checksum", passed=ok,
            detail="Verhoeff checksum valid" if ok else "Verhoeff checksum invalid",
        ))
    elif doc_type == DocumentType.PAN and "pan_number" in fmap:
        ok, detail = pan_format_valid(fmap["pan_number"])
        checks.append(FieldVerification(field="pan_number", check="format", passed=ok, detail=detail))
    elif doc_type == DocumentType.PASSPORT and "passport_number" in fmap:
        ok, detail = passport_format_valid(fmap["passport_number"])
        checks.append(FieldVerification(field="passport_number", check="format", passed=ok, detail=detail))

    if "date_of_birth" in fmap:
        ok, detail = dob_valid(fmap["date_of_birth"])
        checks.append(FieldVerification(field="date_of_birth", check="date_validity", passed=ok, detail=detail))

    is_valid = bool(checks) and all(c.passed for c in checks)
    return VerificationResult(is_valid=is_valid, checks=checks)
