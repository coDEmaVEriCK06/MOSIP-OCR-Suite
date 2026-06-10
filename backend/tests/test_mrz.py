"""Tests for MRZ parsing, check-digit validation, and cross-consistency."""

from app.extraction.analyzer import analyze_document
from app.models.analysis import DocumentType, ExtractedField
from app.verification.mrz import check_digit, detect_mrz_lines, parse_td3
from app.verification.validators import verify_document

L1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
L2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def test_check_digit_matches_icao():
    assert check_digit("L898902C3") == 6
    assert check_digit("740812") == 2
    assert check_digit("120415") == 9


def test_parse_valid_specimen():
    r = parse_td3(L1, L2)
    assert r["all_valid"] is True
    assert r["fields"]["surname"] == "ERIKSSON"
    assert r["fields"]["given_names"] == "ANNA MARIA"
    assert r["fields"]["passport_number"] == "L898902C3"


def test_tampered_fails():
    r = parse_td3(L1, "L898902C36UTO7408122F1204159ZE184226B<<<<<11")
    assert r["all_valid"] is False


def test_detect_mrz_lines():
    text = f"REPUBLIC OF INDIA\nsome header\n{L1}\n{L2}"
    assert detect_mrz_lines(text) == (L1, L2)


def test_verify_includes_mrz_checks():
    result = verify_document(DocumentType.PASSPORT, [], f"REPUBLIC OF INDIA\n{L1}\n{L2}")
    mrz_checks = [c for c in result.checks if c.field.startswith("mrz_")]
    assert len(mrz_checks) == 4
    assert all(c.passed for c in mrz_checks)


def test_dob_cross_consistency_match():
    fields = [ExtractedField(name="date_of_birth", value="12/08/1974", confidence=90.0)]
    result = verify_document(DocumentType.PASSPORT, fields, f"{L1}\n{L2}")
    consistency = [c for c in result.checks if c.check == "mrz_vs_printed"]
    assert len(consistency) == 1 and consistency[0].passed is True


def test_dob_cross_consistency_mismatch():
    fields = [ExtractedField(name="date_of_birth", value="01/01/2000", confidence=90.0)]
    result = verify_document(DocumentType.PASSPORT, fields, f"{L1}\n{L2}")
    consistency = [c for c in result.checks if c.check == "mrz_vs_printed"]
    assert len(consistency) == 1 and consistency[0].passed is False


def test_analyze_document_runs_mrz():
    a = analyze_document(f"REPUBLIC OF INDIA\nPassport\n{L1}\n{L2}")
    assert a.document_type == DocumentType.PASSPORT
    assert any(c.field.startswith("mrz_") for c in a.verification.checks)
