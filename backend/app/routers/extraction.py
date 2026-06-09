"""Extraction endpoints."""

import logging

from fastapi import APIRouter, Depends, File, UploadFile

from app.config import Settings, get_settings
from app.models.extraction import ExtractionResponse
from app.services.ocr import extract_text
from app.utils.files import validate_upload

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["extraction"])


@router.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...),
    settings: Settings = Depends(get_settings),
):
    contents = await file.read()
    logger.info(
        "Extract request received",
        extra={"upload_name": file.filename, "size_bytes": len(contents)},
    )

    mime_type = validate_upload(
        contents, settings.max_file_size_mb, settings.allowed_mime_types
    )

    result = await extract_text(contents, mime_type, settings)
    logger.info(
        "Extraction complete",
        extra={
            "word_count": len(result.words),
            "page_count": result.metadata.page_count,
            "processing_time_ms": result.metadata.processing_time_ms,
        },
    )
    return result
