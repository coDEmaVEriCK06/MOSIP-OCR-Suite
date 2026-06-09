"""Application configuration loaded from environment variables.

Settings are read at import time from process environment variables, with
fallback to a .env file in the backend/ directory during development.
The Settings instance is exposed via get_settings() and cached for the
process lifetime.

List-typed fields (e.g. cors_allowed_origins) accept either a comma-separated
string or a JSON array from environment sources. Source classes are subclassed
to suppress pydantic-settings' default JSON-only decoding for complex types so
the field_validator below can handle both formats uniformly.
"""

import json
from functools import lru_cache
from typing import List, Tuple, Type

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class _LenientEnvSource(EnvSettingsSource):
    def decode_complex_value(self, field_name, field, value):
        if isinstance(value, str) and not value.lstrip().startswith(("[", "{")):
            return value
        return super().decode_complex_value(field_name, field, value)


class _LenientDotEnvSource(DotEnvSettingsSource):
    def decode_complex_value(self, field_name, field, value):
        if isinstance(value, str) and not value.lstrip().startswith(("[", "{")):
            return value
        return super().decode_complex_value(field_name, field, value)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "MOSIP OCR Suite"
    environment: str = Field(default="development")
    log_level: str = Field(default="INFO")

    max_file_size_mb: int = Field(default=10, ge=1, le=100)
    allowed_mime_types: List[str] = Field(
        default_factory=lambda: [
            "image/jpeg",
            "image/png",
            "image/jpg",
            "application/pdf",
        ]
    )

    tesseract_cmd: str = Field(default="tesseract")
    tesseract_lang: str = Field(default="eng")

    trocr_model_name: str = Field(default="microsoft/trocr-base-handwritten")
    trocr_use_gpu: bool = Field(default=False)
    preprocessing_steps: List[str] = Field(
    default_factory = lambda: ["grayscale", "denoise", "threshold"])

    cors_allowed_origins: List[str] = Field(
        default_factory=lambda: ["http://localhost:5173", "http://127.0.0.1:5173"]
    )

    @field_validator("allowed_mime_types", "cors_allowed_origins", "preprocessing_steps", mode="before")
    @classmethod
    def parse_string_list(cls, value):
        if isinstance(value, str):
            stripped = value.strip()
            if stripped.startswith("[") and stripped.endswith("]"):
                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return value

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> Tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            _LenientEnvSource(settings_cls),
            _LenientDotEnvSource(settings_cls),
            file_secret_settings,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
