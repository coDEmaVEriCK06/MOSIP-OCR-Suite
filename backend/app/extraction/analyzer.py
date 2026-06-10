"""Document classification and structured field extraction from OCR text.

Classification is marker-based: each document type has a set of keyword and
format-pattern markers; the type with the most matched markers wins. Field
extraction is hybrid: spatial layout analysis for label-anchored fields (name,
father's name) and type-aware regexes for pattern fields (ID numbers, DOB,
gender). Every field also records the source word boxes it came from, so a
value is traceable to its exact location on the document.
"""

import re
from typing import List, Optional, Sequence, Tuple

from app.models.analysis import DocumentAnalysis, DocumentType, ExtractedField
from app.models.extraction import Word
from app.extraction.layout import (
    locate_value_boxes,
    reconstruct_lines,
    value_words_for_label,
)
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
    # available; pattern fields use regex. Each field records the source word
    # boxes it came from, so the UI can trace a value to its place on the doc.
    lines = reconstruct_lines(words) if words else None
    word_list = list(words) if words else []

    name = None
    name_conf = 60.0
    name_boxes: List = []
    if lines is not None:
        value_words = value_words_for_label(lines, ["name"])
        if value_words:
            name = " ".join(w.text for w in value_words).strip(": ").strip()
            name_conf = 75.0
            name_boxes = [w.bbox for w in value_words]
    if not name:
        name = _extract_name(text)
        if name and word_list:
            name_boxes = locate_value_boxes(name, word_list)
    if name:
        fields.append(ExtractedField(name="name", value=name, confidence=name_conf, boxes=name_boxes))

    if lines is not None and doc_type in (DocumentType.PAN, DocumentType.PASSPORT):
        value_words = value_words_for_label(lines, ["father's name", "fathers name", "father"])
        if value_words:
            father = " ".join(w.text for w in value_words).strip(": ").strip()
            fields.append(ExtractedField(
                name="father_name", value=father, confidence=70.0,
                boxes=[w.bbox for w in value_words],
            ))

    dob = _DOB.search(text)
    if dob:
        fields.append(ExtractedField(
            name="date_of_birth", value=dob.group(1), confidence=90.0,
            boxes=locate_value_boxes(dob.group(1), word_list),
        ))

    gender = _GENDER.search(text)
    if gender:
        value = gender.group(1).title()
        fields.append(ExtractedField(
            name="gender", value=value, confidence=85.0,
            boxes=locate_value_boxes(value, word_list),
        ))

    if doc_type == DocumentType.AADHAAR:
        m = _AADHAAR_NUMBER.search(text)
        if m:
            value = re.sub(r"\s+", "", m.group(1))
            fields.append(ExtractedField(
                name="aadhaar_number", value=value, confidence=95.0,
                boxes=locate_value_boxes(m.group(1), word_list),
            ))
    elif doc_type == DocumentType.PAN:
        m = _PAN_NUMBER.search(text)
        if m:
            fields.append(ExtractedField(
                name="pan_number", value=m.group(1), confidence=95.0,
                boxes=locate_value_boxes(m.group(1), word_list),
            ))
    elif doc_type == DocumentType.PASSPORT:
        m = _PASSPORT_NUMBER.search(text)
        if m:
            fields.append(ExtractedField(
                name="passport_number", value=m.group(1), confidence=95.0,
                boxes=locate_value_boxes(m.group(1), word_list),
            ))

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
