"""Structural verification of extracted identity-document fields.

Unlike the original project's "verification" (which merely compared two OCR
passes against each other and proved nothing), these checks validate the data
against the documents' real-world rules: the Aadhaar Verhoeff checksum, PAN and
passport format structure, date-of-birth plausibility, and — for passports —
full MRZ check-digit validation plus MRZ-versus-printed cross-consistency.
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
from app.verification.mrz import detect_mrz_lines, parse_td3

# --- Verhoeff checksum (used by Aadhaar's 12th digit) ---
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


def _mrz_dob_tuple(yymmdd: str):
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    pivot = datetime.now().year % 100
    yyyy = 2000 + yy if yy <= pivot else 1900 + yy
    return (yyyy, mm, dd)


def _printed_dob_tuple(s: str):
    m = re.match(r"(\d{2})[/-](\d{2})[/-](\d{4})", s.strip())
    if not m:
        return None
    return (int(m.group(3)), int(m.group(2)), int(m.group(1)))


def verify_document(
    doc_type: DocumentType, fields: List[ExtractedField], text: str = ""
) -> VerificationResult:
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

    mrz = detect_mrz_lines(text)
    if mrz:
        parsed = parse_td3(mrz[0], mrz[1])
        for name, ok in parsed["checks"].items():
            checks.append(FieldVerification(
                field=f"mrz_{name}", check="check_digit", passed=ok,
                detail="MRZ check digit valid" if ok else "MRZ check digit invalid",
            ))
        printed = fmap.get("date_of_birth")
        if printed:
            pt, mt = _printed_dob_tuple(printed), _mrz_dob_tuple(parsed["fields"]["date_of_birth"])
            if pt and mt:
                ok = pt == mt
                checks.append(FieldVerification(
                    field="date_of_birth", check="mrz_vs_printed", passed=ok,
                    detail="printed DOB agrees with MRZ" if ok else "printed DOB disagrees with MRZ",
                ))

    is_valid = bool(checks) and all(c.passed for c in checks)
    return VerificationResult(is_valid=is_valid, checks=checks)
