"""Passports prefer the check-digit-validated MRZ over printed-text regex."""

from app.extraction.analyzer import analyze_document, _mrz_date_to_display
from app.models.analysis import DocumentType

# ICAO 9303 specimen MRZ. Birth date token 740812 -> 12/08/1974.
L1 = "P<UTOERIKSSON<<ANNA<MARIA<<<<<<<<<<<<<<<<<<<"
L2 = "L898902C36UTO7408122F1204159ZE184226B<<<<<10"


def _field(fields, name):
    return next((f for f in fields if f.name == name), None)


def test_century_pivot():
    assert _mrz_date_to_display("860610") == "10/06/1986"   # 86 -> 1986 (not future)
    assert _mrz_date_to_display("050101") == "01/01/2005"   # 05 -> 2005
    assert _mrz_date_to_display("740812") == "12/08/1974"
    assert _mrz_date_to_display("99XX99") is None            # garbage rejected


def test_mrz_dob_and_number_win_over_printed():
    # Printed text claims a different (wrong) DOB; the validated MRZ must win.
    text = f"REPUBLIC OF INDIA\nPassport\nDate of Birth 01/01/2000\n{L1}\n{L2}"
    a = analyze_document(text)
    assert a.document_type == DocumentType.PASSPORT
    dob = _field(a.fields, "date_of_birth")
    assert dob is not None and dob.value == "12/08/1974"     # from MRZ, not 01/01/2000
    num = _field(a.fields, "passport_number")
    assert num is not None and num.value == "L898902C3"      # from MRZ


def test_falls_back_to_printed_when_no_mrz():
    text = "REPUBLIC OF INDIA\nPassport\nDate of Birth 01/01/2000"
    a = analyze_document(text)
    dob = _field(a.fields, "date_of_birth")
    assert dob is not None and dob.value == "01/01/2000"     # regex fallback unchanged


def test_falls_back_when_mrz_dob_check_invalid():
    # Tamper the DOB check digit (position 19: '2' -> '0') so its check fails.
    bad = L2.replace("7408122F", "7408120F")
    text = f"REPUBLIC OF INDIA\nPassport\nDate of Birth 01/01/2000\n{L1}\n{bad}"
    a = analyze_document(text)
    dob = _field(a.fields, "date_of_birth")
    assert dob is not None and dob.value == "01/01/2000"     # invalid MRZ DOB -> printed
