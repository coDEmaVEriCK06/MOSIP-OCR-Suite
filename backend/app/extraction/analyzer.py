"""Document classification and structured field extraction from OCR text.

Classification is marker-based: each document type has keyword and
format-pattern markers; the type with the most matched markers wins, and
confidence scales with the match count. Field extraction uses type-aware
regular expressions for ID numbers, shared patterns for date-of-birth and
gender, and a heuristic name extractor that skips institutional headers.

These are deterministic, explainable rules rather than an ML model — the right
fit for well-structured identity documents with known formats: no training
data, fully debuggable, and trivial to extend with new document types.
"""

import re
from typing import List, Optional, Tuple

from app.models.analysis import DocumentAnalysis, DocumentType, ExtractedField

_KEYWORDS = {
    DocumentType.AADHAAR: ["aadhaar", "uidai", "unique identification", "government of india"],
    DocumentType.PAN: ["permanent account number", "income tax department"],
    DocumentType.PASSPORT: ["passport", "republic of india"],
}

_AADHAAR_NUMBER = re.compile(r"\b(\d{4}\s?\d{4}\s?\d{4})\b")
_PAN_NUMBER = re.compile(r"\b([A-Z]{5}\d{4}[A-Z])\b")
_PASSPORT_NUMBER = re.compile(r"\b([A-PR-WY][0-9]{7})\b")
_DOB = re.compile(r"\b(\d{2}[/-]\d{2}[/-]\d{4})\b")
_GENDER = re.compile(r"\b(male|female|transgender)\b", re.IGNORECASE)
_NAME_LABEL = re.compile(r"^name\s*[:\-]\s*(.+)$", re.IGNORECASE)
_NAME_BLOCKLIST = (
    "government", "republic", "department", "income tax", "permanent account",
    "unique identification", "authority", "passport", "aadhaar", "uidai",
    "govt", "india", "number",
)


def classify(text: str) -> Tuple[DocumentType, float, List[str]]:
    """Return (document_type, confidence, matched_markers) for the OCR text."""
    low = text.lower()
    candidates = {dtype: [k for k in kws if k in low] for dtype, kws in _KEYWORDS.items()}
    if _AADHAAR_NUMBER.search(text):
        candidates[DocumentType.AADHAAR].append("aadhaar_number_format")
    if _PAN_NUMBER.search(text):
        candidates[DocumentType.PAN].append("pan_number_format")
    if _PASSPORT_NUMBER.search(text):
        candidates[DocumentType.PASSPORT].append("passport_number_format")

    best = max(candidates, key=lambda k: len(candidates[k]))
    markers = candidates[best]
    if not markers:
        return DocumentType.UNKNOWN, 0.0, []
    return best, min(100.0, len(markers) * 35.0), markers


def _extract_name(text: str) -> Optional[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    # Prefer an explicit "Name:" label.
    for ln in lines:
        m = _NAME_LABEL.match(ln)
        if m and m.group(1).strip():
            return m.group(1).strip()
    # Fallback: first 2-4 word alphabetic line that is not an institutional header.
    for ln in lines:
        if any(b in ln.lower() for b in _NAME_BLOCKLIST):
            continue
        words = ln.split()
        if 2 <= len(words) <= 4 and re.fullmatch(r"[A-Za-z .]+", ln) and all(w[0].isupper() for w in words):
            return ln
    return None


def extract_fields(text: str, doc_type: DocumentType) -> List[ExtractedField]:
    """Extract structured fields, using type-aware patterns for the ID number."""
    fields: List[ExtractedField] = []

    name = _extract_name(text)
    if name:
        fields.append(ExtractedField(name="name", value=name, confidence=60.0))

    dob = _DOB.search(text)
    if dob:
        fields.append(ExtractedField(name="date_of_birth", value=dob.group(1), confidence=90.0))

    gender = _GENDER.search(text)
    if gender:
        fields.append(ExtractedField(name="gender", value=gender.group(1).title(), confidence=85.0))

    if doc_type == DocumentType.AADHAAR:
        m = _AADHAAR_NUMBER.search(text)
        if m:
            fields.append(ExtractedField(name="aadhaar_number", value=re.sub(r"\s+", "", m.group(1)), confidence=95.0))
    elif doc_type == DocumentType.PAN:
        m = _PAN_NUMBER.search(text)
        if m:
            fields.append(ExtractedField(name="pan_number", value=m.group(1), confidence=95.0))
    elif doc_type == DocumentType.PASSPORT:
        m = _PASSPORT_NUMBER.search(text)
        if m:
            fields.append(ExtractedField(name="passport_number", value=m.group(1), confidence=95.0))

    return fields


def analyze_document(text: str) -> DocumentAnalysis:
    """Classify the document and extract its structured fields."""
    doc_type, confidence, markers = classify(text)
    return DocumentAnalysis(
        document_type=doc_type,
        type_confidence=confidence,
        matched_markers=markers,
        fields=extract_fields(text, doc_type),
    )
