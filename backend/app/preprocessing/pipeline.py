"""Image preprocessing pipeline for OCR.

Each step operates on a grayscale numpy array. The default pipeline
(grayscale, denoise, threshold) is coordinate-preserving: it changes pixel
VALUES but not pixel POSITIONS, so Tesseract bounding boxes still align with
the original image. Deskew is available but OFF by default because rotating
pixels shifts bounding-box coordinates relative to the original.
"""

from typing import List, Tuple

import cv2
import numpy as np
from PIL import Image

DEFAULT_STEPS: List[str] = ["grayscale", "denoise", "threshold"]
_VALID_STEPS = {"grayscale", "denoise", "deskew", "threshold"}


def _denoise(gray: np.ndarray) -> np.ndarray:
    # Median blur removes salt-and-pepper speckle while preserving edges.
    return cv2.medianBlur(gray, 3)


def _deskew(gray: np.ndarray) -> np.ndarray:
    # Estimate the dominant text angle from the minimum-area rectangle of text pixels.
    inverted = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(inverted > 0))
    if coords.shape[0] < 10:
        return gray  # too little text to estimate an angle reliably
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    if abs(angle) < 0.5 or abs(angle) > 15:
        return gray  # skip negligible or implausible rotations
    h, w = gray.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        gray, matrix, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE
    )


def _threshold(gray: np.ndarray) -> np.ndarray:
    # Adaptive (local) thresholding handles uneven lighting, where Tesseract's
    # internal single global Otsu cutoff fails.
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 15
    )


def preprocess(image: Image.Image, steps: List[str] = None) -> Tuple[Image.Image, List[str]]:
    """Apply the requested preprocessing steps in canonical order.

    Returns (processed_pil_image, applied_step_names). Unknown step names are
    ignored. 'grayscale' is implicit whenever any step runs, since every OpenCV
    op here operates on a single-channel image.
    """
    if steps is None:
        steps = DEFAULT_STEPS
    requested = {s for s in steps if s in _VALID_STEPS}
    if not requested:
        return image, []

    gray = cv2.cvtColor(np.array(image.convert("RGB")), cv2.COLOR_RGB2GRAY)
    applied = ["grayscale"]

    if "denoise" in requested:
        gray = _denoise(gray)
        applied.append("denoise")
    if "deskew" in requested:
        gray = _deskew(gray)
        applied.append("deskew")
    if "threshold" in requested:
        gray = _threshold(gray)
        applied.append("threshold")

    return Image.fromarray(gray), applied
