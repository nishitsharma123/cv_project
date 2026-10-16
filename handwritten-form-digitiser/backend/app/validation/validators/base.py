"""Abstract base class for field validators."""

from abc import ABC, abstractmethod
from typing import List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import FieldValidationResult, ValidationStatus


class BaseFieldValidator(ABC):
    """Abstract specification for semantic field validation and normalization."""

    @property
    @abstractmethod
    def field_type(self) -> str:
        """Return the target field type identifier (e.g. 'NAME', 'DATE', 'AMOUNT')."""
        ...

    @abstractmethod
    def validate(
        self,
        field_id: str,
        raw_text: str,
        confidence: Optional[float] = None,
        is_confidence_calibrated: bool = False,
        bounding_box: Optional[BoundingBox] = None,
        settings: Optional[Settings] = None,
    ) -> FieldValidationResult:
        """Validate, normalize, and assess review requirements for an individual field.

        A validation failure MUST NOT silently delete or overwrite raw_text.
        """
        ...

    def _evaluate_confidence(
        self,
        confidence: Optional[float],
        is_calibrated: bool,
        threshold: float,
        require_on_uncalibrated: bool,
    ) -> Tuple[List[str], List[str], bool]:
        """Assess model confidence against calibration rules and threshold.

        Returns:
            Tuple of (review_reasons, warning_codes, triggers_review)
        """
        reasons: List[str] = []
        codes: List[str] = []
        triggers_review: bool = False

        if confidence is None or confidence <= 0.0:
            codes.append("CONFIDENCE_UNAVAILABLE")
            reasons.append("Model confidence score was not provided by the OCR engine")
            if require_on_uncalibrated:
                triggers_review = True
        elif not is_calibrated:
            codes.append("CONFIDENCE_UNCALIBRATED")
            reasons.append(
                f"Model confidence ({confidence:.2f}) is uncalibrated heuristic and cannot be statistically trusted"
            )
            if require_on_uncalibrated:
                triggers_review = True
        elif confidence < threshold:
            codes.append("LOW_CONFIDENCE")
            reasons.append(
                f"Model confidence ({confidence:.2f}) is below required threshold ({threshold:.2f})"
            )
            triggers_review = True

        return reasons, codes, triggers_review
