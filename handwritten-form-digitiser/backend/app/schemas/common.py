"""Standard response envelopes and common schema definitions."""

from datetime import datetime, timezone
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


def current_utc_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


class ErrorDetail(BaseModel):
    """Specific field or parameter validation error detail."""

    field: Optional[str] = Field(
        default=None,
        description="Name of the invalid field or parameter",
    )
    message: str = Field(
        ...,
        description="Specific error explanation",
    )
    type: Optional[str] = Field(
        default=None,
        description="Error classification type",
    )


class ErrorPayload(BaseModel):
    """Structured error payload enclosed in an ErrorResponse."""

    code: str = Field(
        ...,
        description="Standardized error code (e.g. BAD_REQUEST, NOT_FOUND)",
    )
    message: str = Field(
        ...,
        description="Human-readable error explanation",
    )
    details: List[ErrorDetail] = Field(
        default_factory=list,
        description="List of specific error details or field issues",
    )


class ErrorResponse(BaseModel):
    """Universal error response envelope."""

    success: bool = Field(
        default=False,
        description="Always false for error responses",
    )
    error: ErrorPayload = Field(
        ...,
        description="Structured error details",
    )
    timestamp: str = Field(
        default_factory=current_utc_iso,
        description="UTC timestamp of the error occurrence",
    )


class SuccessResponse(BaseModel, Generic[T]):
    """Universal success response envelope enclosing data payload."""

    success: bool = Field(
        default=True,
        description="Always true for successful operations",
    )
    data: T = Field(
        ...,
        description="Business payload",
    )
    timestamp: str = Field(
        default_factory=current_utc_iso,
        description="UTC timestamp of the response generation",
    )
