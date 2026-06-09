"""Pydantic models for the extraction pipeline."""

from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.common import BoundingBox


class Word(BaseModel):
    """A single OCR-extracted word with confidence and spatial location."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "text": "Hrishabh",
                    "confidence": 92.4,
                    "bbox": {"x": 120, "y": 80, "width": 110, "height": 28},
                    "page": 1,
                }
            ]
        }
    )

    text: str = Field(..., min_length=1, description="The recognized text content")
    confidence: float = Field(
        ..., ge=0.0, le=100.0, description="OCR engine confidence score, 0-100"
    )
    bbox: BoundingBox = Field(..., description="Bounding box in source image coordinates")
    page: int = Field(
        default=1, ge=1, description="Source page number, 1-indexed (>1 for multi-page PDFs)"
    )

    @field_validator("text", mode="before")
    @classmethod
    def strip_whitespace(cls, value):
        if isinstance(value, str):
            return value.strip()
        return value


class ExtractionMetadata(BaseModel):
    """Observability metadata about how an extraction was performed."""

    engine: str = Field(..., description="OCR engine used: 'tesseract', 'trocr', or 'hybrid'")
    page_count: int = Field(..., ge=1, description="Number of pages processed")
    processing_time_ms: int = Field(..., ge=0, description="End-to-end processing time in milliseconds")
    preprocessing_applied: List[str] = Field(
        default_factory=list,
        description="Names of preprocessing steps applied (e.g. 'deskew', 'threshold')",
    )


class ExtractionResponse(BaseModel):
    """Response payload for POST /api/extract."""

    text: str = Field(..., description="Full extracted text with line breaks preserved")
    words: List[Word] = Field(
        ..., description="Per-word data with confidence scores and bounding boxes"
    )
    metadata: ExtractionMetadata = Field(
        ..., description="Information about how the extraction was performed"
    )
