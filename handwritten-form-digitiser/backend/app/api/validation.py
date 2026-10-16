"""Validation API router — POST /validate and POST /validate/field."""

import logging
from fastapi import APIRouter, Request, status

from app.core.config import get_settings
from app.schemas.validation import (
    DocumentValidationRequest,
    DocumentValidationResponseEnvelope,
    FieldValidationRequest,
    FieldValidationResponseEnvelope,
)
from app.validation.service import ValidationService

logger = logging.getLogger("app.api.validation")

router = APIRouter(tags=["Validation & Human-in-the-Loop Review"])

# Module-level singleton
_validation_service = ValidationService()


@router.post(
    "/validate",
    response_model=DocumentValidationResponseEnvelope,
    summary="Validate document fields against domain rules and confidence thresholds",
    response_description="Structured field validation results with review flags and warnings",
    status_code=status.HTTP_200_OK,
)
async def validate_document(
    payload: DocumentValidationRequest,
    request: Request,
) -> DocumentValidationResponseEnvelope:
    """Validate all recognized fields in a form document.

    Checks:
    - Name: Unicode NFC consistency, Devanagari stroke integrity, digit/symbol absence, length.
    - Date: Devanagari digit mapping, strict calendar validity (no guessing missing parts).
    - Amount: Numeric separators, decimal rules, zero preservation, digit-confusion detection.
    - Confidence: Evaluates engine confidence against calibrated thresholds.

    Raw OCR text is always preserved unmodified in the output.
    """
    settings = getattr(request.app.state, "settings", None) or get_settings()

    result = _validation_service.validate_document(
        template_id=payload.template_id,
        fields=payload.fields,
        engine_id=payload.engine_id,
        settings=settings,
    )

    return DocumentValidationResponseEnvelope(data=result)


@router.post(
    "/validate/field",
    response_model=FieldValidationResponseEnvelope,
    summary="Validate an individual field against its domain rules",
    response_description="Validation result for a single field",
    status_code=status.HTTP_200_OK,
)
async def validate_single_field(
    payload: FieldValidationRequest,
    request: Request,
) -> FieldValidationResponseEnvelope:
    """Validate an individual field in isolation."""
    settings = getattr(request.app.state, "settings", None) or get_settings()

    result = _validation_service.validate_field(
        field_id=payload.field_id,
        field_type=payload.field_type,
        raw_text=payload.raw_text,
        confidence=payload.confidence,
        is_confidence_calibrated=payload.is_confidence_calibrated,
        bounding_box=payload.bounding_box,
        settings=settings,
    )

    return FieldValidationResponseEnvelope(data=result)
