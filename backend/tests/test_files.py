"""Tests for file upload validation utilities."""

import io
import os

import pytest
from PIL import Image

from app.utils.files import (
    FileValidationError,
    detect_and_validate_mime,
    validate_file_size,
    validate_upload,
)

ALLOWED = ["image/jpeg", "image/png", "image/jpg", "application/pdf"]


def _make_png() -> bytes:
    img = Image.new("RGB", (60, 30), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_valid_png_passes():
    mime = validate_upload(_make_png(), max_size_mb=10, allowed_mime_types=ALLOWED)
    assert mime == "image/png"


def test_empty_file_rejected():
    with pytest.raises(FileValidationError) as exc:
        validate_file_size(b"", max_size_mb=10)
    assert exc.value.error_type == "empty_file"


def test_oversized_file_rejected():
    big = os.urandom(2 * 1024 * 1024)  # 2 MB incompressible
    with pytest.raises(FileValidationError) as exc:
        validate_file_size(big, max_size_mb=1)
    assert exc.value.error_type == "file_too_large"


def test_disguised_script_rejected():
    script = b"#!/bin/bash\nrm -rf /\n"
    with pytest.raises(FileValidationError) as exc:
        detect_and_validate_mime(script, ALLOWED)
    assert exc.value.error_type == "unrecognized_file_type"


def test_unsupported_but_real_type_rejected():
    gif = b"GIF89a" + b"\x00" * 20
    with pytest.raises(FileValidationError) as exc:
        detect_and_validate_mime(gif, ALLOWED)
    assert exc.value.error_type == "unsupported_file_type"
    assert exc.value.details["detected_mime"] == "image/gif"
