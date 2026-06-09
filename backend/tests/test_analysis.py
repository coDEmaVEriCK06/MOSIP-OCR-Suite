"""Tests for document classification and field extraction."""

from app.extraction.analyzer import analyze_document, extract_fields
from app.models.analysis import DocumentType

AADHAAR = """Government of India
Hrishabh Sharma
DOB: 15/08/2003
Male
1234 5678 9012
Unique Identification Authority of India"""

PAN = """INCOME TAX DEPARTMENT
GOVT. OF INDIA
Permanent Account Number
ABCDE1234F
Hrishabh Sharma
15/08/2003"""

PASSPORT = """REPUBLIC OF INDIA
Passport No A1234567
Hrishabh Sharma
Date of Birth 15-08-2003
Female"""

RANDOM = """Quarterly revenue report
Total sales increased by 12 percent"""


def _fields(text, dtype):
    return {f.name: f.value for f in extract_fields(text, dtype)}


def test_classifies_aadhaar():
    a = analyze_document(AADHAAR)
    assert a.document_type == DocumentType.AADHAAR
    assert a.type_confidence > 0
    assert "aadhaar_number_format" in a.matched_markers


def test_classifies_pan():
    assert analyze_document(PAN).document_type == DocumentType.PAN


def test_classifies_passport():
    assert analyze_document(PASSPORT).document_type == DocumentType.PASSPORT


def test_unknown_for_random_text():
    a = analyze_document(RANDOM)
    assert a.document_type == DocumentType.UNKNOWN
    assert a.fields == []


def test_extracts_aadhaar_fields():
    f = _fields(AADHAAR, DocumentType.AADHAAR)
    assert f["aadhaar_number"] == "123456789012"
    assert f["date_of_birth"] == "15/08/2003"
    assert f["gender"] == "Male"
    assert f["name"] == "Hrishabh Sharma"


def test_extracts_pan_number():
    f = _fields(PAN, DocumentType.PAN)
    assert f["pan_number"] == "ABCDE1234F"


def test_extracts_passport_number():
    f = _fields(PASSPORT, DocumentType.PASSPORT)
    assert f["passport_number"] == "A1234567"


def test_name_skips_institutional_headers():
    assert _fields(PAN, DocumentType.PAN)["name"] == "Hrishabh Sharma"
    assert _fields(PASSPORT, DocumentType.PASSPORT)["name"] == "Hrishabh Sharma"
