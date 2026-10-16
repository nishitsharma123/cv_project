"""Structured logging configuration with PII and binary buffer redaction."""

import json
import logging
import re
import sys
import time
from typing import Any, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

# Patterns representing base64 image data or raw byte buffers
BASE64_IMAGE_PATTERN = re.compile(r"data:image\/[a-zA-Z]+;base64,[A-Za-z0-9+/=]{20,}")
BINARY_BUFFER_PATTERN = re.compile(r"b'[\x00-\xff]{20,}'|b\"[\x00-\xff]{20,}\"")
LONG_BASE64_PATTERN = re.compile(r"(?:[A-Za-z0-9+/]{4}){10,}(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?")


class SanitizingFilter(logging.Filter):
    """Logging filter that redacts raw image bytes, base64 buffers, and sensitive payloads."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.sanitize_string(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.sanitize_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.sanitize_value(arg) for arg in record.args)

        return True

    @classmethod
    def sanitize_string(cls, text: str) -> str:
        """Sanitize strings containing binary data or potential sensitive text."""
        if not text:
            return text
        # Redact data URLs
        text = BASE64_IMAGE_PATTERN.sub("[REDACTED_IMAGE_DATA_URL]", text)
        # Redact raw python bytes repr
        text = BINARY_BUFFER_PATTERN.sub("[REDACTED_BINARY_BUFFER]", text)
        # Redact raw base64 payloads longer than 60 chars
        if len(text) > 80:
            text = LONG_BASE64_PATTERN.sub("[REDACTED_BASE64_DATA]", text)
        return text

    @classmethod
    def sanitize_value(cls, val: Any) -> Any:
        """Recursively sanitize dictionary or sequence values."""
        if isinstance(val, (bytes, bytearray)):
            return f"[REDACTED_BINARY_DATA length={len(val)}]"
        elif isinstance(val, str):
            return cls.sanitize_string(val)
        elif isinstance(val, dict):
            return {k: cls.sanitize_value(v) for k, v in val.items()}
        elif isinstance(val, (list, tuple)):
            return type(val)(cls.sanitize_value(v) for v in val)
        return val


class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def setup_logging(level: str = "INFO", log_format: str = "text") -> None:
    """Initialize structured application logging with sanitization filters."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level.upper())

    # Clear existing handlers to prevent duplicate logs
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level.upper())

    sanitizer = SanitizingFilter()
    console_handler.addFilter(sanitizer)

    if log_format.lower() == "json":
        formatter = JSONFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set external libraries to appropriate log levels to prevent spam
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for structured HTTP access logging without dumping image/form data."""

    def __init__(self, app: Any, logger_name: str = "app.access"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        method = request.method
        path = request.url.path

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            status_code = response.status_code

            # Log request metrics cleanly
            self.logger.info(
                f"{method} {path} - {status_code} - {duration_ms}ms - client={client_ip}"
            )
            return response
        except Exception:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            self.logger.error(
                f"{method} {path} - FAILED - {duration_ms}ms - client={client_ip}",
                exc_info=True,
            )
            raise
