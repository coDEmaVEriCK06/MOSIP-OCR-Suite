"""OCR service: async-safe Tesseract + PDF rasterization, with preprocessing,
document analysis, and a SHA-256 result cache in front of the expensive work.
"""

import io
import time
from typing import Dict, List, Tuple

import anyio
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from app.config import Settings, get_settings
from app.extraction.analyzer import analyze_document
from app.models.common import BoundingBox
from app.models.extraction import ExtractionMetadata, ExtractionResponse, Word
from app.preprocessing.pipeline import preprocess
from app.services.cache import ExtractionCache

_cache = ExtractionCache(max_size=get_settings().cache_max_size)


def _ocr_image(
    image: Image.Image, lang: str, page_number: int, steps: List[str]
) -> Tuple[List[Word], str, List[str]]:
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
    """Async-safe OCR + analysis, served from cache on a repeat upload."""
    cache_key = ExtractionCache.key_for(
        contents, settings.tesseract_lang, settings.preprocessing_steps
    )
    cached = _cache.get(cache_key)
    if cached is not None:
        return cached.model_copy(
            update={"metadata": cached.metadata.model_copy(update={"from_cache": True})}
        )

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

    response = ExtractionResponse(
        text=full_text,
        words=words,
        metadata=ExtractionMetadata(
            engine="tesseract",
            page_count=page_count,
            processing_time_ms=elapsed_ms,
            preprocessing_applied=applied_steps,
        ),
        analysis=analyze_document(full_text),
    )
    _cache.set(cache_key, response)
    return response
