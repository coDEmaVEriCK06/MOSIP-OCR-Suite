"""Before/after demonstration of the preprocessing pipeline.

Generates a deliberately degraded document image, then runs OCR with and
without preprocessing to show the accuracy difference. Saves both images so
you can see the visual transformation.

Run from the backend/ directory:  python scripts/preprocess_demo.py
"""

import sys
from pathlib import Path

# Allow direct invocation by putting backend/ (which contains the `app`
# package) on the import path, since running a script directly otherwise only
# puts the scripts/ folder on sys.path.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pytesseract
from PIL import Image, ImageDraw, ImageFont

from app.preprocessing.pipeline import preprocess

TRUTH = "INVOICE 2026 TOTAL 4567"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def make_degraded():
    img = Image.new("RGB", (700, 150), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype(FONT, 40)
    except OSError:
        font = ImageFont.load_default()
    draw.text((20, 50), TRUTH, fill="black", font=font)
    arr = np.array(img.convert("L")).astype(np.float32)
    arr = arr * 0.35 + 110
    h, w = arr.shape
    arr = arr + np.tile(np.linspace(-40, 40, w), (h, 1))
    np.random.seed(42)
    arr = arr + np.random.normal(0, 18, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def main():
    degraded = make_degraded()
    degraded.save("demo_degraded.png")
    raw = pytesseract.image_to_string(degraded).strip()

    processed, steps = preprocess(degraded)
    processed.save("demo_preprocessed.png")
    cleaned = pytesseract.image_to_string(processed).strip()

    print("Ground truth:          ", TRUTH)
    print("-" * 60)
    print("WITHOUT preprocessing: ", repr(raw))
    print("WITH preprocessing:    ", repr(cleaned))
    print("Steps applied:         ", steps)
    print("-" * 60)
    print("Saved demo_degraded.png and demo_preprocessed.png — open them to")
    print("see the noisy original vs the cleaned image Tesseract receives.")


if __name__ == "__main__":
    main()
