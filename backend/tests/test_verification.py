"""Tests for structural verification of extracted fields."""

from app.extraction.analyzer import analyze_document
from app.models.analysis import DocumentType, ExtractedField
from app.verification.validators import (
    dob_valid,
    pan_format_valid,
    passport_format_valid,
    verhoeff_valid,
    verify_document,
)

VALID_AADHAAR = "234123412346"      # Verhoeff-valid
INVALID_AADHAAR = "123456789012"    # sequential, fails Verhoeff


def test_verhoeff_accepts_valid():
    assert verhoeff_valid(VALID_AADHAAR) is True
    assert verhoeff_valid("999999990019") is True


def test_verhoeff_rejects_invalid():
    assert verhoeff_valid(INVALID_AADHAAR) is False
    assert verhoeff_valid("23412341234") is False  # wrong length


def test_pan_format():
    assert pan_format_valid("ABCDE1234F")[0] is True
    assert pan_format_valid("ABC1234F")[0] is False


def test_passport_format():
    assert passport_format_valid("A1234567")[0] is True
    assert passport_format_valid("12345678")[0] is False


def test_dob_validation():
    assert dob_valid("15/08/2003")[0] is True
    assert dob_valid("15-08-2003")[0] is True
    assert dob_valid("31/01/2099")[0] is False   # future
    assert dob_valid("not a date")[0] is False


def test_verify_document_aadhaar_valid():
    fields = [
        ExtractedField(name="aadhaar_number", value=VALID_AADHAAR, confidence=95.0),
        ExtractedField(name="date_of_birth", value="15/08/2003", confidence=90.0),
    ]
    result = verify_document(DocumentType.AADHAAR, fields)
    assert result.is_valid is True
    assert all(c.passed for c in result.checks)


def test_verify_document_aadhaar_invalid():
    fields = [ExtractedField(name="aadhaar_number", value=INVALID_AADHAAR, confidence=95.0)]
    result = verify_document(DocumentType.AADHAAR, fields)
    assert result.is_valid is False
    assert any(c.check == "verhoeff_checksum" and not c.passed for c in result.checks)


def test_analyze_document_includes_verification():
    text = f"Government of India\nHrishabh Sharma\nDOB: 15/08/2003\nMale\n{VALID_AADHAAR}"
    a = analyze_document(text)
    assert a.document_type == DocumentType.AADHAAR
    assert a.verification.is_valid is True
