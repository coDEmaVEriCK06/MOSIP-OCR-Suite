"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.models.common import ErrorResponse
from app.routers import extraction
from app.utils.files import FileValidationError
from app.utils.logging_setup import setup_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    setup_logging(level=settings.log_level, environment=settings.environment)
    logger.info(
        "Application starting",
        extra={
            "app_name": settings.app_name,
            "environment": settings.environment,
            "log_level": settings.log_level,
        },
    )
    yield
    logger.info("Application shutting down")


settings = get_settings()
app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extraction.router)


@app.exception_handler(FileValidationError)
async def file_validation_handler(request: Request, exc: FileValidationError):
    logger.warning("File validation failed", extra={"error_type": exc.error_type})
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=ErrorResponse(
            error_type=exc.error_type, message=exc.message, details=exc.details
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error", extra={"path": str(request.url.path)})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            error_type="internal_error",
            message="An unexpected error occurred while processing the request.",
        ).model_dump(),
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}
