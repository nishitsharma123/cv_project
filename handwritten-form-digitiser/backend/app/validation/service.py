"""Validation service orchestrating field-specific validators and document audits."""

import logging
from typing import Any, Dict, List, Optional, Union

from app.core.config import Settings, get_settings
from app.schemas.recognition import OCRResultData
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import (
    DocumentValidationRequest,
    DocumentValidationResponseData,
    FieldValidationRequest,
    FieldValidationResult,
    ValidationStatus,
)
from app.validation.validators import (
    AmountFieldValidator,
    BaseFieldValidator,
    DateFieldValidator,
    NameFieldValidator,
)

logger = logging.getLogger("app.validation")


class ValidationService:
    """Domain service managing validation execution, confidence policy, and review flag aggregation."""

    def __init__(self) -> None:
        self._validators: Dict[str, BaseFieldValidator] = {
            "NAME": NameFieldValidator(),
            "DATE": DateFieldValidator(),
            "AMOUNT": AmountFieldValidator(),
        }

    def register_validator(self, field_type: str, validator: BaseFieldValidator) -> None:
        """Register or override a validator for a specific field type."""
        self._validators[field_type.upper()] = validator

    def validate_field(
        self,
        field_id: str,
        field_type: str,
        raw_text: str,
        confidence: Optional[float] = None,
        is_confidence_calibrated: bool = False,
        bounding_box: Optional[BoundingBox] = None,
        settings: Optional[Settings] = None,
    ) -> FieldValidationResult:
        """Execute validation for a single field against domain rules."""
        if settings is None:
            settings = get_settings()

        normalized_type = (field_type or "").upper().strip()
        validator = self._validators.get(normalized_type)

        if validator is None:
            logger.warning("No specialized validator for field_type '%s'; using basic checks", field_type)
            # Default fallback for unconfigured field types
            review_reasons: List[str] = []
            warning_codes: List[str] = []
            requires_review = False
            status = ValidationStatus.VALID

            if not raw_text or not raw_text.strip():
                status = ValidationStatus.INVALID
                requires_review = True
                warning_codes.append("EMPTY_VALUE")
                review_reasons.append("Field is empty")

            return FieldValidationResult(
                field_id=field_id,
                field_type=field_type,
                raw_text=raw_text or "",
                normalized_text=raw_text.strip() if status != ValidationStatus.INVALID else None,
                validation_status=status,
                requires_review=requires_review,
                review_reasons=review_reasons,
                warning_codes=warning_codes,
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=raw_text.strip() if status != ValidationStatus.INVALID else None,
            )

        return validator.validate(
            field_id=field_id,
            raw_text=raw_text,
            confidence=confidence,
            is_confidence_calibrated=is_confidence_calibrated,
            bounding_box=bounding_box,
            settings=settings,
        )

    def validate_document(
        self,
        template_id: str,
        fields: Dict[str, Union[OCRResultData, FieldValidationRequest, dict]],
        engine_id: Optional[str] = None,
        bounding_boxes: Optional[Dict[str, BoundingBox]] = None,
        settings: Optional[Settings] = None,
    ) -> DocumentValidationResponseData:
        """Validate all fields in a document and compute aggregate review decisions."""
        if settings is None:
            settings = get_settings()

        validated_fields: Dict[str, FieldValidationResult] = {}
        document_warnings: List[str] = []
        valid_count = 0
        review_count = 0

        for fid, finput in fields.items():
            # Extract inputs whether from OCRResultData, FieldValidationRequest, or dict
            if isinstance(finput, OCRResultData):
                raw_text = finput.raw_text or finput.text
                ftype = finput.field_type
                conf = finput.confidence if finput.confidence > 0.0 else None
                calibrated = finput.is_confidence_calibrated
            elif isinstance(finput, FieldValidationRequest):
                raw_text = finput.raw_text
                ftype = finput.field_type
                conf = finput.confidence
                calibrated = finput.is_confidence_calibrated
            elif isinstance(finput, dict):
                raw_text = finput.get("raw_text") or finput.get("text") or ""
                ftype = finput.get("field_type") or "TEXT"
                conf = finput.get("confidence")
                calibrated = bool(finput.get("is_confidence_calibrated", False))
            else:
                raw_text = str(finput)
                ftype = "TEXT"
                conf = None
                calibrated = False

            bbox = None
            if bounding_boxes and fid in bounding_boxes:
                bbox = bounding_boxes[fid]
            elif isinstance(finput, FieldValidationRequest) and finput.bounding_box:
                bbox = finput.bounding_box

            result = self.validate_field(
                field_id=fid,
                field_type=ftype,
                raw_text=raw_text,
                confidence=conf,
                is_confidence_calibrated=calibrated,
                bounding_box=bbox,
                settings=settings,
            )

            validated_fields[fid] = result

            if result.validation_status == ValidationStatus.VALID:
                valid_count += 1
            if result.requires_review:
                review_count += 1

        total_fields = len(validated_fields)
        doc_requires_review = review_count > 0

        if doc_requires_review:
            document_warnings.append(
                f"{review_count} of {total_fields} field(s) require human review or verification"
            )

        logger.info(
            "Document validation complete: template=%s total=%d valid=%d review=%d",
            template_id,
            total_fields,
            valid_count,
            review_count,
        )

        return DocumentValidationResponseData(
            template_id=template_id,
            engine_id=engine_id,
            fields=validated_fields,
            total_fields=total_fields,
            valid_fields=valid_count,
            review_required_fields=review_count,
            document_requires_review=doc_requires_review,
            warnings=document_warnings,
        )
