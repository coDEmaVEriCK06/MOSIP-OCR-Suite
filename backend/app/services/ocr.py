"""OCR service: wraps Tesseract and PDF rasterization behind an async-safe interface.

Each page is preprocessed (app.preprocessing.pipeline) before OCR; the combined
text is then classified and mined for structured fields (app.extraction.analyzer)
so a single call returns raw text, per-word data, and a document analysis.
"""

import io
import time
from typing import Dict, List, Tuple

import anyio
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import Settings
from app.extraction.analyzer import analyze_document
from app.models.common import BoundingBox
from app.models.extraction import ExtractionMetadata, ExtractionResponse, Word
from app.preprocessing.pipeline import preprocess


def _ocr_image(
    image: Image.Image, lang: str, page_number: int, steps: List[str]
) -> Tuple[List[Word], str, List[str]]:
    """Preprocess then OCR a single image. Returns (words, page_text, applied_steps)."""
    processed, applied = preprocess(image, steps)
    data = pytesseract.image_to_data(
        processed, lang=lang, output_type=pytesseract.Output.DICT
    )
    words: List[Word] = []
    lines: Dict[Tuple[int, int, int], List[Tuple[int, str]]] = {}

    for i in range(len(data["text"])):
        text = data["text"][i].strip()
        conf = float(data["conf"][i])
        width = int(data["width"][i])
        height = int(data["height"][i])
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
    return words, "\n".join(line_texts), applied


def _extract_sync(
    contents: bytes, mime_type: str, lang: str, steps: List[str]
) -> Tuple[List[Word], str, int, List[str]]:
    """Rasterize PDFs if needed, preprocess + OCR every page. Runs in a worker thread."""
    if mime_type == "application/pdf":
        images = convert_from_bytes(contents)
    else:
        images = [Image.open(io.BytesIO(contents))]

    all_words: List[Word] = []
    page_texts: List[str] = []
    applied_steps: List[str] = []
    for page_index, image in enumerate(images, start=1):
        words, page_text, applied = _ocr_image(image, lang, page_index, steps)
        all_words.extend(words)
        page_texts.append(page_text)
        applied_steps = applied

    return all_words, "\n\n".join(page_texts), len(images), applied_steps


async def extract_text(
    contents: bytes, mime_type: str, settings: Settings
) -> ExtractionResponse:
    """Async-safe OCR + document analysis. Blocking work runs in a worker thread."""
    pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd
    start = time.perf_counter()
    words, full_text, page_count, applied_steps = await anyio.to_thread.run_sync(
        _extract_sync,
        contents,
        mime_type,
        settings.tesseract_lang,
        settings.preprocessing_steps,
    )
    elapsed_ms = int((time.perf_counter() - start) * 1000)

    analysis = analyze_document(full_text)

    return ExtractionResponse(
        text=full_text,
        words=words,
        metadata=ExtractionMetadata(
            engine="tesseract",
            page_count=page_count,
            processing_time_ms=elapsed_ms,
            preprocessing_applied=applied_steps,
        ),
        analysis=analysis,
    )
