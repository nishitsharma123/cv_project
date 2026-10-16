"""Centralized exception handling and domain error definitions."""

import logging
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.common import ErrorDetail, ErrorPayload, ErrorResponse

logger = logging.getLogger("app.errors")


class AppException(Exception):
    """Base domain exception with standardized error details."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or []


class BadRequestException(AppException):
    """Exception for invalid client requests (HTTP 400)."""

    def __init__(
        self,
        message: str = "Invalid request payload or parameters.",
        code: str = "BAD_REQUEST",
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class NotFoundException(AppException):
    """Exception when a requested resource is not found (HTTP 404)."""

    def __init__(
        self,
        message: str = "The requested resource was not found.",
        code: str = "NOT_FOUND",
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ValidationException(AppException):
    """Exception for semantic validation errors (HTTP 422)."""

    def __init__(
        self,
        message: str = "Validation failed for one or more fields.",
        code: str = "VALIDATION_ERROR",
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


class PayloadTooLargeException(AppException):
    """Exception when upload exceeds size limits (HTTP 413)."""

    def __init__(
        self,
        message: str = "Uploaded file exceeds maximum allowed size.",
        code: str = "PAYLOAD_TOO_LARGE",
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            details=details,
        )


class InternalServerException(AppException):
    """Exception for unexpected internal processing errors (HTTP 500)."""

    def __init__(
        self,
        message: str = "An internal server error occurred.",
        code: str = "INTERNAL_SERVER_ERROR",
        details: Optional[List[Dict[str, Any]]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


def _build_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[List[ErrorDetail]] = None,
) -> JSONResponse:
    """Helper to construct standard ErrorResponse JSONResponse."""
    payload = ErrorResponse(
        success=False,
        error=ErrorPayload(
            code=code,
            message=message,
            details=details or [],
        ),
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(),
    )


async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
    """Handler for domain-specific AppException."""
    details = [
        ErrorDetail(
            field=str(d.get("field")) if d.get("field") else None,
            message=str(d.get("message", "")),
            type=str(d.get("type")) if d.get("type") else None,
        )
        for d in exc.details
    ]
    return _build_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=details,
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Handler for Starlette/FastAPI HTTPExceptions (e.g. 404, 405)."""
    code_map = {
        status.HTTP_404_NOT_FOUND: ("NOT_FOUND", "Resource not found"),
        status.HTTP_405_METHOD_NOT_ALLOWED: ("METHOD_NOT_ALLOWED", "Method not allowed"),
        status.HTTP_401_UNAUTHORIZED: ("UNAUTHORIZED", "Authentication required"),
        status.HTTP_403_FORBIDDEN: ("FORBIDDEN", "Access forbidden"),
    }
    default_code, default_msg = code_map.get(
        exc.status_code,
        (f"HTTP_{exc.status_code}", str(exc.detail) if exc.detail else "HTTP error"),
    )
    message = str(exc.detail) if exc.detail else default_msg

    return _build_error_response(
        status_code=exc.status_code,
        code=default_code,
        message=message,
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Handler for request schema validation errors (HTTP 422)."""
    details: List[ErrorDetail] = []
    for err in exc.errors():
        # Build clean dot-separated field locator
        loc = err.get("loc", ())
        # Filter out 'body' or 'query' prefix if present for cleaner frontend messaging
        field_path = ".".join(str(part) for part in loc if part not in ("body", "query")) or "payload"
        details.append(
            ErrorDetail(
                field=field_path,
                message=err.get("msg", "Invalid value"),
                type=err.get("type", "value_error"),
            )
        )

    return _build_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        code="VALIDATION_ERROR",
        message="Request validation failed. Check field details.",
        details=details,
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Fallback handler for unhandled exceptions (HTTP 500), avoiding stack trace leaks."""
    logger.error(
        f"Unhandled exception during {request.method} {request.url.path}: {str(exc)}",
        exc_info=True,
    )
    return _build_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please contact system support.",
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Register all centralized exception handlers on the FastAPI application."""
    app.add_exception_handler(AppException, app_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
