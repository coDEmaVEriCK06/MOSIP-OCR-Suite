"""Document classification and structured field extraction from OCR text.

Classification is marker-based: each document type has a set of keyword and
format-pattern markers; the type with the most matched markers wins. Field
extraction is hybrid: spatial layout analysis for label-anchored fields (name,
father's name) and type-aware regexes for pattern fields (ID numbers, DOB,
gender). Every field also records the source word boxes it came from, so a
value is traceable to its exact location on the document.

For passports specifically, the machine-readable zone (MRZ) is preferred as the
source of the structured fields (date of birth, number, sex) whenever it parses
and its ICAO check digit validates. The MRZ is printed to be machine-read and is
self-validating, so when it is readable it is more trustworthy than scraping the
printed labels — which is exactly the case where a printed-text regex can grab
the wrong date (e.g. the date of issue) on a document that carries several dates.
When no valid MRZ is available, extraction falls back to the printed-text regex.
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
from app.verification.mrz import detect_mrz_lines, parse_td3
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


def _mrz_date_to_display(yymmdd: str, current_year: int = 2026) -> Optional[str]:
    """Convert an MRZ ``YYMMDD`` date to ``dd/mm/yyyy``, applying a century pivot.

    The MRZ stores the year as two digits with no century. A birth date cannot be
    in the future, so a two-digit year that would land after the current year is
    read as 19YY rather than 20YY (e.g. ``86`` -> 1986, ``05`` -> 2005). Returns
    ``None`` if the token isn't a plausible YYMMDD.
    """
    if len(yymmdd) != 6 or not yymmdd.isdigit():
        return None
    yy, mm, dd = int(yymmdd[0:2]), int(yymmdd[2:4]), int(yymmdd[4:6])
    if not (1 <= mm <= 12 and 1 <= dd <= 31):
        return None
    year = 2000 + yy
    if year > current_year:
        year -= 100
    return f"{dd:02d}/{mm:02d}/{year:04d}"


def _parse_passport_mrz(text: str) -> Optional[dict]:
    """Return the parsed MRZ for a passport, or None if no MRZ is present."""
    found = detect_mrz_lines(text)
    if not found:
        return None
    return parse_td3(found[0], found[1])


def extract_fields(
    text: str, doc_type: DocumentType, words: Optional[Sequence[Word]] = None
) -> List[ExtractedField]:
    fields: List[ExtractedField] = []

    # Label-value fields use spatial layout analysis when word geometry is
    # available; pattern fields use regex. Each field records the source word
    # boxes it came from, so the UI can trace a value to its place on the doc.
    lines = reconstruct_lines(words) if words else None
    word_list = list(words) if words else []

    # For passports, parse the MRZ once up front. When a field's ICAO check digit
    # validates, the MRZ value is authoritative and overrides the printed-text
    # regex below; otherwise we fall back to the printed text.
    mrz = _parse_passport_mrz(text) if doc_type == DocumentType.PASSPORT else None

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

    # Date of birth: prefer the MRZ when its check digit validates.
    dob_field: Optional[ExtractedField] = None
    if mrz and mrz["checks"].get("date_of_birth"):
        display = _mrz_date_to_display(mrz["fields"]["date_of_birth"])
        if display:
            dob_field = ExtractedField(
                name="date_of_birth", value=display, confidence=98.0,
                boxes=locate_value_boxes(mrz["fields"]["date_of_birth"], word_list),
            )
    if dob_field is None:
        m = _DOB.search(text)
        if m:
            dob_field = ExtractedField(
                name="date_of_birth", value=m.group(1), confidence=90.0,
                boxes=locate_value_boxes(m.group(1), word_list),
            )
    if dob_field:
        fields.append(dob_field)

    # Sex/gender: prefer the MRZ's M/F when present (it is part of the
    # check-digit-protected line); otherwise fall back to the printed regex.
    gender_field: Optional[ExtractedField] = None
    if mrz and mrz["fields"].get("sex") in ("M", "F"):
        gender_field = ExtractedField(
            name="gender", value="Male" if mrz["fields"]["sex"] == "M" else "Female",
            confidence=95.0, boxes=[],
        )
    if gender_field is None:
        g = _GENDER.search(text)
        if g:
            value = g.group(1).title()
            gender_field = ExtractedField(
                name="gender", value=value, confidence=85.0,
                boxes=locate_value_boxes(value, word_list),
            )
    if gender_field:
        fields.append(gender_field)

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
        # Passport number: prefer the MRZ when its check digit validates.
        number_field: Optional[ExtractedField] = None
        if mrz and mrz["checks"].get("passport_number") and mrz["fields"]["passport_number"]:
            num = mrz["fields"]["passport_number"]
            number_field = ExtractedField(
                name="passport_number", value=num, confidence=98.0,
                boxes=locate_value_boxes(num, word_list),
            )
        if number_field is None:
            m = _PASSPORT_NUMBER.search(text)
            if m:
                number_field = ExtractedField(
                    name="passport_number", value=m.group(1), confidence=95.0,
                    boxes=locate_value_boxes(m.group(1), word_list),
                )
        if number_field:
            fields.append(number_field)

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
