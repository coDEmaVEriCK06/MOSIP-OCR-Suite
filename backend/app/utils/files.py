"""File upload validation utilities.

Validation runs against file *content*, not client-supplied headers or
filenames, both of which can be spoofed. Each validator raises
FileValidationError on failure; the router layer translates that into an
HTTP error response (wired in Sub-step 1.6). Keeping validation independent
of FastAPI's HTTP types makes it unit-testable in isolation.
"""

from typing import Any, Dict, List, Optional

import filetype


class FileValidationError(Exception):
    """Raised when an uploaded file fails a validation check."""

    def __init__(
        self,
        error_type: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.error_type = error_type
        self.message = message
        self.details = details or {}
        super().__init__(message)


def validate_file_size(contents: bytes, max_size_mb: int) -> None:
    """Reject empty files and files exceeding the configured size limit."""
    size_bytes = len(contents)
    if size_bytes == 0:
        raise FileValidationError(
            error_type="empty_file",
            message="Uploaded file is empty.",
            details={"size_bytes": 0},
        )
    size_mb = size_bytes / (1024 * 1024)
    if size_mb > max_size_mb:
        raise FileValidationError(
            error_type="file_too_large",
            message=f"File size {size_mb:.2f} MB exceeds the {max_size_mb} MB limit.",
            details={"size_mb": round(size_mb, 2), "limit_mb": max_size_mb},
        )


def detect_and_validate_mime(contents: bytes, allowed_mime_types: List[str]) -> str:
    """Sniff the true file type from content and ensure it is allowed.

    Returns the detected MIME type on success.
    """
    kind = filetype.guess(contents)
    if kind is None:
        raise FileValidationError(
            error_type="unrecognized_file_type",
            message="Could not determine a supported file type from the file content.",
            details={"detected_mime": None, "allowed": allowed_mime_types},
        )
    if kind.mime not in allowed_mime_types:
        raise FileValidationError(
            error_type="unsupported_file_type",
            message=f"File type '{kind.mime}' is not supported.",
            details={"detected_mime": kind.mime, "allowed": allowed_mime_types},
        )
    return kind.mime


def validate_upload(
    contents: bytes, max_size_mb: int, allowed_mime_types: List[str]
) -> str:
    """Run all upload validations in order. Returns the detected MIME type."""
    validate_file_size(contents, max_size_mb)
    return detect_and_validate_mime(contents, allowed_mime_types)
