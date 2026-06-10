"""Tests for layout-aware spatial field extraction (deterministic geometry)."""

from app.extraction.analyzer import analyze_document
from app.extraction.layout import Line, find_label_value, reconstruct_lines
from app.models.common import BoundingBox
from app.models.extraction import Word


def W(text, x, y, w=60, h=20, page=1, conf=90.0):
    return Word(text=text, confidence=conf, bbox=BoundingBox(x=x, y=y, width=w, height=h), page=page)


def test_reconstruct_lines_groups_by_row_and_orders_by_x():
    words = [W("SHARMA", 200, 100), W("HRISHABH", 40, 102), W("Name", 40, 40)]
    lines = reconstruct_lines(words)
    assert [ln.text for ln in lines] == ["Name", "HRISHABH SHARMA"]


def test_reconstruct_lines_orders_pages_top_to_bottom():
    words = [W("second", 40, 200), W("first", 40, 40)]
    lines = reconstruct_lines(words)
    assert [ln.text for ln in lines] == ["first", "second"]


def test_inline_label_value():
    words = [W("Name", 40, 40, w=50), W("HRISHABH", 110, 40), W("SHARMA", 180, 40)]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["name"]) == "HRISHABH SHARMA"


def test_inline_label_value_with_colon():
    words = [W("Name", 40, 40, w=50), W(":", 95, 40, w=8), W("ANNA", 110, 40)]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["name"]) == "ANNA"


def test_stacked_label_value():
    words = [W("Name", 40, 40, w=50), W("HRISHABH", 40, 80), W("SHARMA", 130, 80)]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["name"]) == "HRISHABH SHARMA"


def test_multiword_label_fathers_name():
    words = [
        W("Father's", 40, 40, w=70), W("Name", 115, 40, w=50),
        W("RAJESH", 40, 80), W("SHARMA", 130, 80),
    ]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["father's name", "fathers name"]) == "RAJESH SHARMA"


def test_name_does_not_match_inside_fathers_name():
    words = [
        W("Father's", 40, 40, w=70), W("Name", 115, 40, w=50),
        W("RAJESH", 40, 80),
        W("Name", 40, 140, w=50),
        W("HRISHABH", 40, 180),
    ]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["name"]) == "HRISHABH"
    assert find_label_value(lines, ["father's name", "fathers name"]) == "RAJESH"


def test_missing_label_returns_none():
    words = [W("RANDOM", 40, 40), W("TEXT", 120, 40)]
    lines = reconstruct_lines(words)
    assert find_label_value(lines, ["name"]) is None


def test_analyze_document_uses_spatial_extraction():
    words = [
        W("Permanent", 40, 20, w=110), W("Account", 160, 20, w=90), W("Number", 260, 20, w=80),
        W("ABCDE1234F", 40, 60, w=130),
        W("Name", 40, 110, w=50),
        W("HRISHABH", 40, 150), W("SHARMA", 130, 150),
        W("Father's", 40, 210, w=70), W("Name", 115, 210, w=50),
        W("RAJESH", 40, 250), W("SHARMA", 130, 250),
    ]
    text = "Permanent Account Number\nABCDE1234F\nName\nHRISHABH SHARMA\nFather's Name\nRAJESH SHARMA"
    a = analyze_document(text, words)
    fmap = {f.name: f.value for f in a.fields}
    assert fmap.get("name") == "HRISHABH SHARMA"
    assert fmap.get("father_name") == "RAJESH SHARMA"
    assert fmap.get("pan_number") == "ABCDE1234F"
    name_field = next(f for f in a.fields if f.name == "name")
    assert name_field.confidence == 75.0


def test_analyze_document_without_words_still_works():
    text = "INCOME TAX DEPARTMENT\nName: HRISHABH SHARMA\nABCDE1234F"
    a = analyze_document(text)
    fmap = {f.name: f.value for f in a.fields}
    assert fmap.get("name") == "HRISHABH SHARMA"
    assert fmap.get("pan_number") == "ABCDE1234F"
