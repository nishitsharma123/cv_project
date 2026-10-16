"""Pydantic schemas for field-level validation, review flags, and document audits."""

from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field

from app.schemas.common import SuccessResponse
from app.schemas.recognition import OCRResultData
from app.schemas.segmentation import BoundingBox


class ValidationStatus(str, Enum):
    """Overall semantic validity status of a processed field.

    VALID   -- Field passed all format, calendar/numerical, and confidence checks.
    WARNING -- Field is syntactically acceptable but triggers review (e.g. low confidence, short name).
    INVALID -- Field failed critical domain rules (e.g. impossible date, corrupt amount, empty required field).
    """

    VALID = "VALID"
    WARNING = "WARNING"
    INVALID = "INVALID"


class FieldValidationResult(BaseModel):
    """Complete validation record for an individual form field."""

    field_id: str = Field(..., description="Stable field identifier (e.g. applicant_name)")
    field_type: str = Field(..., description="Semantic type: NAME, DATE, or AMOUNT")
    raw_text: str = Field(..., description="Original OCR text. Never mutated or deleted.")
    normalized_text: Optional[str] = Field(
        default=None,
        description="Safely normalized representation. None if validation failed or normalization unsafe.",
    )
    validation_status: ValidationStatus = Field(
        ..., description="Validation outcome: VALID, WARNING, or INVALID"
    )
    requires_review: bool = Field(
        ..., description="True if human review or manual confirmation is required"
    )
    review_reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable explanations for why review was flagged",
    )
    warning_codes: List[str] = Field(
        default_factory=list,
        description="Programmatic warning identifiers (e.g. LOW_CONFIDENCE, INVALID_CALENDAR_DATE)",
    )
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Model confidence score in [0.0, 1.0]. None when unavailable.",
    )
    is_confidence_calibrated: bool = Field(
        default=False,
        description="Whether confidence represents a calibrated posterior probability",
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None,
        description="Pixel bounding box reference from segmentation stage",
    )
    parsed_value: Optional[Union[str, float, int, Dict[str, Any]]] = Field(
        default=None,
        description="Typed representation (e.g. ISO-8601 date string or float amount)",
    )


class FieldValidationRequest(BaseModel):
    """Input payload for validating a single field independently."""

    field_id: str = Field(..., description="Identifier of the field")
    field_type: str = Field(..., description="Field type: NAME, DATE, or AMOUNT")
    raw_text: str = Field(..., description="Recognized text to validate")
    confidence: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Engine confidence if available",
    )
    is_confidence_calibrated: bool = Field(
        default=False,
        description="Whether confidence is calibrated",
    )
    bounding_box: Optional[BoundingBox] = Field(
        default=None,
        description="Optional field bounding box",
    )


class DocumentValidationRequest(BaseModel):
    """Input payload for validating an entire document's fields."""

    template_id: str = Field(
        default="devanagari_synthetic_v1",
        description="Form layout template ID",
    )
    engine_id: Optional[str] = Field(
        default=None,
        description="Engine ID that produced the recognition results",
    )
    fields: Dict[str, FieldValidationRequest] = Field(
        ..., description="Mapping of field_id to field validation requests"
    )


class DocumentValidationResponseData(BaseModel):
    """Aggregated validation response for a complete form document."""

    template_id: str = Field(..., description="Applied form template identifier")
    engine_id: Optional[str] = Field(
        default=None, description="OCR engine identifier if provided"
    )
    fields: Dict[str, FieldValidationResult] = Field(
        ..., description="Per-field validation results keyed by field_id"
    )
    total_fields: int = Field(..., ge=0, description="Total number of evaluated fields")
    valid_fields: int = Field(..., ge=0, description="Count of fields with status VALID")
    review_required_fields: int = Field(
        ..., ge=0, description="Count of fields requiring human review"
    )
    document_requires_review: bool = Field(
        ..., description="True if any field requires human review"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Document-level validation notes or warnings",
    )


class DocumentValidationResponseEnvelope(SuccessResponse[DocumentValidationResponseData]):
    """Standardized API envelope for document validation responses."""
    pass


class FieldValidationResponseEnvelope(SuccessResponse[FieldValidationResult]):
    """Standardized API envelope for single field validation response."""
    pass
