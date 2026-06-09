"""Application logging configuration.

Sets up Python's standard logging with two output modes:
- Development: human-readable single-line text format on stderr.
- Production: structured JSON (one JSON object per line) suitable for shipping
  to log aggregators like Datadog, Splunk, or ELK.

The mode is selected by the ENVIRONMENT setting. Log level is controlled by
LOG_LEVEL. Modules emit logs via logging.getLogger(__name__), which produces
a logger named after the module's dotted path (e.g. 'app.routers.extraction'),
allowing per-module filtering in production tools.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict


# Field names that Python's logging module attaches to every LogRecord and
# refuses to let user code overwrite. If you pass extra={"filename": ...},
# Python raises KeyError. We strip these out defensively before merging.
_RESERVED_KEYS = {
    "name", "msg", "args", "levelname", "levelno", "pathname",
    "filename", "module", "exc_info", "exc_text", "stack_info",
    "lineno", "funcName", "created", "msecs", "relativeCreated",
    "thread", "threadName", "processName", "process", "message",
    "taskName",
}


class JsonFormatter(logging.Formatter):
    """Formats each LogRecord as one JSON object on a single line."""

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED_KEYS:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def setup_logging(level: str = "INFO", environment: str = "development") -> None:
    """Configure the root logger. Idempotent - safe to call multiple times."""
    root_logger = logging.getLogger()

    # Clear any pre-existing handlers (from uvicorn or earlier setup calls)
    # before installing ours. Without this, repeated calls produce duplicate
    # log lines, which is a classic logging footgun.
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    handler = logging.StreamHandler(sys.stderr)

    if environment.lower() == "production":
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root_logger.addHandler(handler)
    root_logger.setLevel(level.upper())

    # Quiet down noisy library loggers we don't care about at INFO level.
    logging.getLogger("multipart").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
