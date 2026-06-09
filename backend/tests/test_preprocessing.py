"""Tests for the preprocessing pipeline and its integration with OCR."""

import io
import re

import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.preprocessing.pipeline import DEFAULT_STEPS, preprocess
from app.services.ocr import extract_text

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _text_image(text, w=700, h=150, size=40):
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    try:
        f = ImageFont.truetype(FONT, size)
    except OSError:
        f = ImageFont.load_default()
    d.text((20, 50), text, fill="black", font=f)
    return img


def _words(text):
    return [re.sub(r"[^A-Z0-9]", "", w) for w in text.upper().split()]


def test_preprocess_returns_pil_and_applied_steps():
    out, applied = preprocess(_text_image("Hello"))
    assert isinstance(out, Image.Image)
    assert applied == DEFAULT_STEPS


def test_default_pipeline_preserves_dimensions():
    img = _text_image("Coordinate Safety")
    out, _ = preprocess(img)
    assert out.size == img.size  # bbox coordinates stay valid against the original


def test_empty_and_unknown_steps():
    img = _text_image("Edge")
    same, applied = preprocess(img, steps=[])
    assert same is img and applied == []
    _, applied2 = preprocess(img, steps=["bogus", "threshold"])
    assert "threshold" in applied2 and "bogus" not in applied2


def test_preprocessing_improves_degraded_ocr():
    truth = "INVOICE 2026 TOTAL 4567"
    np.random.seed(42)
    clean = _text_image(truth)
    arr = np.array(clean.convert("L")).astype(np.float32)
    arr = arr * 0.35 + 110                                  # low contrast
    h, w = arr.shape
    arr = arr + np.tile(np.linspace(-40, 40, w), (h, 1))    # uneven lighting
    arr = arr + np.random.normal(0, 18, arr.shape)          # noise
    degraded = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    raw = _words(pytesseract.image_to_string(degraded))
    pre_img, _ = preprocess(degraded)
    pre = _words(pytesseract.image_to_string(pre_img))

    truth_words = truth.split()
    raw_hits = sum(1 for x in truth_words if x in raw)
    pre_hits = sum(1 for x in truth_words if x in pre)
    assert pre_hits > raw_hits  # preprocessing recovers a degraded scan


def test_metadata_records_applied_steps():
    import asyncio

    buf = io.BytesIO()
    _text_image("Engine Check").save(buf, format="PNG")
    result = asyncio.run(extract_text(buf.getvalue(), "image/png", get_settings()))
    assert result.metadata.preprocessing_applied == DEFAULT_STEPS
    assert len(result.words) > 0
