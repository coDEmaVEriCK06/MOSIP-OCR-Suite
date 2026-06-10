"""Document classification and structured field extraction from OCR text.

Classification is marker-based: each document type has a set of keyword and
format-pattern markers; the type with the most matched markers wins, and
confidence scales with the match count. Field extraction is hybrid: distinctive
pattern fields (ID numbers, date of birth, gender) use type-aware regular
expressions, while label-anchored fields (name, father's name) use spatial
layout analysis over word bounding boxes when geometry is available, falling
back to a text heuristic otherwise. These are deterministic, explainable rules
rather than an ML model — appropriate for well-structured ID documents and easy
to defend and extend.
"""

import re
from typing import List, Optional, Sequence, Tuple

from app.models.analysis import DocumentAnalysis, DocumentType, ExtractedField
from app.models.extraction import Word
from app.extraction.layout import find_label_value, reconstruct_lines
from app.verification.validators import verify_document

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
    low = text.lower()
    candidates = {}
    for dtype, keywords in _KEYWORDS.items():
        markers = [k for k in keywords if k in low]
        candidates[dtype] = markers
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
    confidence = min(100.0, len(markers) * 35.0)
    return best, confidence, markers


def _extract_name(text: str) -> Optional[str]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    for ln in lines:
        m = _NAME_LABEL.match(ln)
        if m and m.group(1).strip():
            return m.group(1).strip()
    # Fallback: first line of 2-4 alphabetic words that is not an institutional
    # header (those are filtered by the blocklist).
    for ln in lines:
        low = ln.lower()
        if any(b in low for b in _NAME_BLOCKLIST):
            continue
        words = ln.split()
        if 2 <= len(words) <= 4 and re.fullmatch(r"[A-Za-z .]+", ln) and all(w[0].isupper() for w in words):
            return ln
    return None


def extract_fields(
    text: str, doc_type: DocumentType, words: Optional[Sequence[Word]] = None
) -> List[ExtractedField]:
    fields: List[ExtractedField] = []

    # Label-value fields use spatial layout analysis when word geometry is
    # available (the position of a value relative to its label is what
    # identifies it); we fall back to the text heuristic otherwise.
    lines = reconstruct_lines(words) if words else None

    name = None
    name_conf = 60.0
    if lines is not None:
        name = find_label_value(lines, ["name"])
        if name:
            name_conf = 75.0
    if not name:
        name = _extract_name(text)
    if name:
        fields.append(ExtractedField(name="name", value=name, confidence=name_conf))

    if lines is not None and doc_type in (DocumentType.PAN, DocumentType.PASSPORT):
        father = find_label_value(lines, ["father's name", "fathers name", "father"])
        if father:
            fields.append(ExtractedField(name="father_name", value=father, confidence=70.0))

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


def analyze_document(text: str, words: Optional[Sequence[Word]] = None) -> DocumentAnalysis:
    doc_type, confidence, markers = classify(text)
    fields = extract_fields(text, doc_type, words)
    return DocumentAnalysis(
        document_type=doc_type,
        type_confidence=confidence,
        matched_markers=markers,
        fields=fields,
        verification=verify_document(doc_type, fields, text),
    )
