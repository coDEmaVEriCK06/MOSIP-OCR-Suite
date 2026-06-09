"""Tests for the OCR service (app/services/ocr.py)."""

import asyncio
import io

from PIL import Image

from app.config import get_settings
from app.services.ocr import extract_text


def _run(coro):
    return asyncio.run(coro)


def test_extracts_text_from_image(make_text_image):
    png = make_text_image("Hello MOSIP")
    result = _run(extract_text(png, "image/png", get_settings()))
    lowered = result.text.lower()
    assert "hello" in lowered
    assert "mosip" in lowered
    assert len(result.words) >= 2


def test_words_have_valid_confidence_and_bbox(make_text_image):
    png = make_text_image("Sample Text")
    result = _run(extract_text(png, "image/png", get_settings()))
    assert len(result.words) > 0
    for w in result.words:
        assert 0.0 <= w.confidence <= 100.0
        assert w.bbox.width > 0 and w.bbox.height > 0
        assert w.bbox.x >= 0 and w.bbox.y >= 0
        assert w.page == 1


def test_metadata_is_populated(make_text_image):
    png = make_text_image("Metadata Check")
    result = _run(extract_text(png, "image/png", get_settings()))
    assert result.metadata.engine == "tesseract"
    assert result.metadata.page_count == 1
    assert result.metadata.processing_time_ms >= 0


def test_blank_image_yields_no_words():
    img = Image.new("RGB", (200, 100), color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    result = _run(extract_text(buf.getvalue(), "image/png", get_settings()))
    assert result.words == []
    assert result.metadata.page_count == 1


def test_multipage_pdf_tags_pages(make_text_image):
    img1 = Image.open(io.BytesIO(make_text_image("Page One")))
    img2 = Image.open(io.BytesIO(make_text_image("Page Two")))
    buf = io.BytesIO()
    img1.save(buf, format="PDF", save_all=True, append_images=[img2])
    result = _run(extract_text(buf.getvalue(), "application/pdf", get_settings()))
    assert result.metadata.page_count == 2
    assert {w.page for w in result.words} == {1, 2}
