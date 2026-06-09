"""Demonstration of document classification + structured field extraction.

Generates a mock Aadhaar-style image, runs the full pipeline, and prints the
detected document type and extracted fields.

Run from the backend/ directory:  python scripts/analyze_demo.py
"""

import asyncio
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PIL import Image, ImageDraw, ImageFont

from app.config import get_settings
from app.services.ocr import extract_text

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _font(size):
    try:
        return ImageFont.truetype(FONT, size)
    except OSError:
        return ImageFont.load_default()


def mock_aadhaar():
    img = Image.new("RGB", (700, 360), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Government of India", fill="black", font=_font(26))
    d.text((30, 90), "Hrishabh Sharma", fill="black", font=_font(32))
    d.text((30, 150), "DOB: 15/08/2003", fill="black", font=_font(26))
    d.text((30, 200), "Male", fill="black", font=_font(26))
    d.text((30, 260), "1234 5678 9012", fill="black", font=_font(32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def main():
    result = asyncio.run(extract_text(mock_aadhaar(), "image/png", get_settings()))
    print("Detected document type:", result.analysis.document_type.value)
    print("Type confidence:       ", result.analysis.type_confidence)
    print("Matched markers:       ", result.analysis.matched_markers)
    print("Extracted fields:")
    for f in result.analysis.fields:
        print(f"  {f.name:16s} = {f.value!r}  (conf {f.confidence})")


if __name__ == "__main__":
    main()
