"""Tests for the SHA-256 extraction cache."""

import asyncio
import io

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.models.analysis import DocumentAnalysis, DocumentType, VerificationResult
from app.models.extraction import ExtractionMetadata, ExtractionResponse
from app.services.cache import ExtractionCache
from app.services.ocr import _cache, extract_text


def _img(txt):
    im = Image.new("RGB", (400, 120), "white")
    d = ImageDraw.Draw(im)
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 30)
    except OSError:
        f = ImageFont.load_default()
    d.text((20, 40), txt, fill="black", font=f)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _fake():
    return ExtractionResponse(
        text="x", words=[],
        metadata=ExtractionMetadata(engine="tesseract", page_count=1, processing_time_ms=1),
        analysis=DocumentAnalysis(
            document_type=DocumentType.UNKNOWN, type_confidence=0.0,
            verification=VerificationResult(is_valid=False),
        ),
    )


def test_cache_set_get_miss():
    c = ExtractionCache(max_size=2)
    assert c.get("nope") is None
    c.set("a", _fake())
    assert c.get("a") is not None


def test_cache_lru_eviction():
    c = ExtractionCache(max_size=2)
    c.set("a", _fake())
    c.set("b", _fake())
    c.get("a")            # 'a' is now most-recently-used
    c.set("c", _fake())   # evicts least-recently-used, which is 'b'
    assert c.get("b") is None
    assert c.get("a") is not None and c.get("c") is not None


def test_key_depends_on_inputs():
    k1 = ExtractionCache.key_for(b"data", "eng", ["grayscale"])
    k2 = ExtractionCache.key_for(b"data", "eng", ["grayscale", "threshold"])
    k3 = ExtractionCache.key_for(b"data", "eng", ["grayscale"])
    assert k1 != k2 and k1 == k3


def test_integration_cache_hit():
    _cache.clear()
    png = _img("Cache Me")
    r1 = asyncio.run(extract_text(png, "image/png", get_settings()))
    assert r1.metadata.from_cache is False
    r2 = asyncio.run(extract_text(png, "image/png", get_settings()))
    assert r2.metadata.from_cache is True
    assert r2.text == r1.text
