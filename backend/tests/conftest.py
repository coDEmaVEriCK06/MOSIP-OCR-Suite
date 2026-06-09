"""Shared pytest fixtures for the test suite."""

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app


@pytest.fixture
def make_text_image():
    """Factory fixture: returns a function that renders text into PNG bytes."""

    def _make(text: str, width: int = 400, height: int = 120) -> bytes:
        img = Image.new("RGB", (width, height), color="white")
        draw = ImageDraw.Draw(img)
        try:
            font = ImageFont.truetype(
                "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 32
            )
        except OSError:
            font = ImageFont.load_default()
        draw.text((20, 40), text, fill="black", font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    return _make


@pytest.fixture
def client():
    """FastAPI TestClient with lifespan (startup/shutdown) triggered."""
    with TestClient(app) as c:
        yield c
