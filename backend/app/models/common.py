"""Common Pydantic models reused across the application."""

from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class BoundingBox(BaseModel):
    """A rectangular region in source-image pixel coordinates."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"x": 120, "y": 80, "width": 200, "height": 32},
            ]
        }
    )

    x: int = Field(..., ge=0, description="Left edge in pixels from image origin")
    y: int = Field(..., ge=0, description="Top edge in pixels from image origin")
    width: int = Field(..., gt=0, description="Box width in pixels")
    height: int = Field(..., gt=0, description="Box height in pixels")


class ErrorResponse(BaseModel):
    """Standardized error response returned for non-2xx HTTP responses."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "error_type": "validation_error",
                    "message": "File size exceeds maximum allowed (10 MB)",
                    "details": {"received_size_mb": 25.4, "limit_mb": 10},
                }
            ]
        }
    )

    error_type: str = Field(..., description="Machine-readable error category")
    message: str = Field(..., description="Human-readable error description")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional structured context attached to the error"
    )
