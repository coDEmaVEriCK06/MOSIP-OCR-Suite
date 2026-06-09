"""OCR service: wraps Tesseract and PDF rasterization behind an async-safe interface.

Tesseract is a blocking, CPU-bound subprocess; endpoints are async. Calling it
directly would block the event loop and serialize all requests, so the blocking
work is offloaded to a worker thread via anyio.to_thread.run_sync — the
Starlette/FastAPI-sanctioned mechanism for running sync code off the loop.

A single image_to_data call per page yields words, confidences, and bounding
boxes together; readable full text is reconstructed from the same call by
grouping words into lines, avoiding a wasteful second OCR pass.
"""

import io
import time
from typing import Dict, List, Tuple

import anyio
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import Settings
from app.models.common import BoundingBox
from app.models.extraction import ExtractionMetadata, ExtractionResponse, Word


def _ocr_image(image: Image.Image, lang: str, page_number: int) -> Tuple[List[Word], str]:
    """OCR a single image. Returns (words, reconstructed_page_text). Blocking."""
    data = pytesseract.image_to_data(
        image, lang=lang, output_type=pytesseract.Output.DICT
    )
    words: List[Word] = []
    lines: Dict[Tuple[int, int, int], List[Tuple[int, str]]] = {}

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
        # Skip empty cells, non-text blocks (conf == -1), and degenerate boxes.
        if not text or conf < 0 or width <= 0 or height <= 0:
            continue
        words.append(
            Word(
                text=text,
                confidence=conf,
                bbox=BoundingBox(
                    x=int(data["left"][i]),
                    y=int(data["top"][i]),
                    width=width,
                    height=height,
                ),
                page=page_number,
            )
        )
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        lines.setdefault(key, []).append((data["word_num"][i], text))

    line_texts = [
        " ".join(t for _, t in sorted(lines[k])) for k in sorted(lines.keys())
    ]
    return words, "\n".join(line_texts)


def _extract_sync(contents: bytes, mime_type: str, lang: str) -> Tuple[List[Word], str, int]:
    """Rasterize PDFs if needed, OCR every page. Blocking; runs in a worker thread."""
    if mime_type == "application/pdf":
        images = convert_from_bytes(contents)
    else:
        images = [Image.open(io.BytesIO(contents))]

    all_words: List[Word] = []
    page_texts: List[str] = []
    for page_index, image in enumerate(images, start=1):
        words, page_text = _ocr_image(image, lang, page_index)
        all_words.extend(words)
        page_texts.append(page_text)

    return all_words, "\n\n".join(page_texts), len(images)


async def extract_text(
    contents: bytes, mime_type: str, settings: Settings
) -> ExtractionResponse:
    """Async-safe OCR. Offloads the blocking Tesseract work to a worker thread."""
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    start = time.perf_counter()
    words, full_text, page_count = await anyio.to_thread.run_sync(
        _extract_sync, contents, mime_type, settings.tesseract_lang
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    return ExtractionResponse(
        text=full_text,
        words=words,
        metadata=ExtractionMetadata(
            engine="tesseract",
            page_count=page_count,
            processing_time_ms=elapsed_ms,
            preprocessing_applied=[],
        ),
    )
