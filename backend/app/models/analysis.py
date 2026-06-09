"""Models for document classification and structured field extraction."""

from enum import Enum
from typing import List

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    AADHAAR = "aadhaar"
    PAN = "pan"
    PASSPORT = "passport"
    UNKNOWN = "unknown"


class ExtractedField(BaseModel):
    name: str = Field(..., description="Field identifier, e.g. 'date_of_birth'")
    value: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=100.0)


class DocumentAnalysis(BaseModel):
    document_type: DocumentType
    type_confidence: float = Field(..., ge=0.0, le=100.0)
    matched_markers: List[str] = Field(default_factory=list)
    fields: List[ExtractedField] = Field(default_factory=list)
