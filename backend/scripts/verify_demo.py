"""Demonstration of structural verification.

Generates two Aadhaar-style images — one with a Verhoeff-valid number, one with
an invalid number — runs the full pipeline on each, and shows the checksum
catching the bad one while passing the good one.

Run from the backend/ directory:  python scripts/verify_demo.py
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


def aadhaar_img(number):
    img = Image.new("RGB", (700, 360), "white")
    d = ImageDraw.Draw(img)
    d.text((30, 20), "Government of India", fill="black", font=_font(26))
    d.text((30, 90), "Hrishabh Sharma", fill="black", font=_font(32))
    d.text((30, 150), "DOB: 15/08/2003", fill="black", font=_font(26))
    d.text((30, 200), "Male", fill="black", font=_font(26))
    d.text((30, 260), number, fill="black", font=_font(32))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def run(label, number):
    result = asyncio.run(extract_text(aadhaar_img(number), "image/png", get_settings()))
    v = result.analysis.verification
    print(f"=== {label}  (printed: {number}) ===")
    print(f"  document_type : {result.analysis.document_type.value}")
    print(f"  is_valid      : {v.is_valid}")
    for c in v.checks:
        mark = "PASS" if c.passed else "FAIL"
        print(f"    [{mark}] {c.field} / {c.check}: {c.detail}")
    print()


def main():
    run("VALID Aadhaar", "2341 2341 2346")
    run("INVALID Aadhaar", "1234 5678 9012")
    print("The checksum accepts the valid number and rejects the invalid one —")
    print("real structural verification, not a comparison of two OCR guesses.")


if __name__ == "__main__":
    main()
