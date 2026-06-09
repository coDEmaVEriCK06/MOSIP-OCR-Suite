"""Models for document classification, field extraction, and verification."""

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


class FieldVerification(BaseModel):
    field: str = Field(..., description="Field that was checked")
    check: str = Field(..., description="Check performed, e.g. 'verhoeff_checksum'")
    passed: bool
    detail: str = Field(..., description="Human-readable outcome")


class VerificationResult(BaseModel):
    is_valid: bool = Field(..., description="True only if every check passed")
    checks: List[FieldVerification] = Field(default_factory=list)


class DocumentAnalysis(BaseModel):
    document_type: DocumentType
    type_confidence: float = Field(..., ge=0.0, le=100.0)
    matched_markers: List[str] = Field(default_factory=list)
    fields: List[ExtractedField] = Field(default_factory=list)
    verification: VerificationResult
