"""Field validator for dates (calendar truth, format constraints, Devanagari numerals)."""

import datetime
import re
from typing import List, Optional, Tuple

from app.core.config import Settings, get_settings
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import FieldValidationResult, ValidationStatus
from app.validation.validators.base import BaseFieldValidator

DEVANAGARI_TO_ASCII = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}


class DateFieldValidator(BaseFieldValidator):
    """Validates calendar dates, converts Devanagari digits, and strictly rejects incomplete dates."""

    @property
    def field_type(self) -> str:
        return "DATE"

    @classmethod
    def _devanagari_to_ascii(cls, text: str) -> str:
        """Deterministically map Devanagari digits to ASCII."""
        chars = [DEVANAGARI_TO_ASCII.get(c, c) for c in text]
        return "".join(chars)

    def validate(
        self,
        field_id: str,
        raw_text: str,
        confidence: Optional[float] = None,
        is_confidence_calibrated: bool = False,
        bounding_box: Optional[BoundingBox] = None,
        settings: Optional[Settings] = None,
    ) -> FieldValidationResult:
        if settings is None:
            settings = get_settings()

        review_reasons: List[str] = []
        warning_codes: List[str] = []
        requires_review = False
        status = ValidationStatus.VALID

        # 1. Check for empty or None text
        if raw_text is None or len(raw_text.strip()) == 0:
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text if raw_text is not None else "",
                normalized_text=None,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                review_reasons=["Date field is empty or contains only whitespace"],
                warning_codes=["EMPTY_VALUE"],
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        trimmed = raw_text.strip()
        # Convert Devanagari numerals to ASCII digits
        ascii_text = self._devanagari_to_ascii(trimmed)

        # 2. Check for unexpected alphabetic characters (e.g. 'O' confused with '0')
        alpha_chars = [c for c in ascii_text if c.isalpha()]
        if alpha_chars:
            warning_codes.append("ALPHABETIC_IN_DATE")
            review_reasons.append(
                f"Date contains non-numeric alphabetic characters ({', '.join(sorted(set(alpha_chars)))}). Possible OCR character confusion (e.g., 'O' vs '0')."
            )
            requires_review = True
            status = ValidationStatus.INVALID
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text,
                normalized_text=None,
                validation_status=status,
                requires_review=requires_review,
                review_reasons=review_reasons,
                warning_codes=warning_codes,
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        # 3. Check for incomplete date structures (e.g. only 2 parts like '08/2024')
        # Split on common separators: /, -, .
        parts = re.split(r"[/\-.\s]+", ascii_text.strip())
        parts = [p for p in parts if p]

        if len(parts) < 3:
            warning_codes.append("INCOMPLETE_DATE")
            review_reasons.append(
                f"Date '{trimmed}' is incomplete (found {len(parts)} component(s), expected 3: day, month, year). Missing components are never guessed."
            )
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text,
                normalized_text=None,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                review_reasons=review_reasons,
                warning_codes=warning_codes,
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        if len(parts) > 3:
            warning_codes.append("UNSUPPORTED_DATE_FORMAT")
            review_reasons.append(
                f"Date '{trimmed}' contains too many components ({len(parts)})."
            )
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text,
                normalized_text=None,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                review_reasons=review_reasons,
                warning_codes=warning_codes,
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        # 4. Parse day, month, year
        p0, p1, p2 = parts[0], parts[1], parts[2]
        day: Optional[int] = None
        month: Optional[int] = None
        year: Optional[int] = None

        # Determine if format is YYYY-MM-DD or DD-MM-YYYY
        if len(p0) == 4 and len(p2) <= 2:
            # YYYY-MM-DD
            try:
                year = int(p0)
                month = int(p1)
                day = int(p2)
            except ValueError:
                pass
        else:
            # DD-MM-YYYY or DD-MM-YY
            try:
                day = int(p0)
                month = int(p1)
                year = int(p2)
                # Expand 2-digit year safely if present
                if len(p2) == 2 and year is not None:
                    year = 2000 + year if year < 70 else 1900 + year
            except ValueError:
                pass

        if day is None or month is None or year is None:
            warning_codes.append("UNSUPPORTED_DATE_FORMAT")
            review_reasons.append(f"Failed to parse integer components from date '{trimmed}'")
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text,
                normalized_text=None,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                review_reasons=review_reasons,
                warning_codes=warning_codes,
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        # 5. Year sanity bound
        if year < 1900 or year > 2100:
            warning_codes.append("YEAR_OUT_OF_RANGE")
            review_reasons.append(f"Year {year} is outside acceptable range [1900, 2100]")
            requires_review = True
            status = ValidationStatus.INVALID

        # 6. Strict Calendar Truth Validation via datetime.date
        valid_date_obj: Optional[datetime.date] = None
        try:
            valid_date_obj = datetime.date(year, month, day)
        except ValueError as exc:
            warning_codes.append("INVALID_CALENDAR_DATE")
            review_reasons.append(
                f"Date {day:02d}/{month:02d}/{year:04d} is not a valid calendar day: {exc}"
            )
            requires_review = True
            status = ValidationStatus.INVALID

        # 7. Confidence Evaluation
        conf_reasons, conf_codes, conf_trigger = self._evaluate_confidence(
            confidence=confidence,
            is_calibrated=is_confidence_calibrated,
            threshold=settings.DATE_MIN_CONFIDENCE,
            require_on_uncalibrated=settings.REQUIRE_REVIEW_ON_UNAVAILABLE_CONFIDENCE,
        )
        review_reasons.extend(conf_reasons)
        warning_codes.extend(conf_codes)
        if conf_trigger:
            requires_review = True
            if status == ValidationStatus.VALID:
                status = ValidationStatus.WARNING

        # 8. Output Normalization: documented standard DD/MM/YYYY and ISO-8601 in parsed_value
        normalized_str: Optional[str] = None
        parsed_val: Optional[dict] = None
        if status != ValidationStatus.INVALID and valid_date_obj is not None:
            normalized_str = valid_date_obj.strftime("%d/%m/%Y")
            parsed_val = {
                "iso": valid_date_obj.isoformat(),
                "display": normalized_str,
                "year": valid_date_obj.year,
                "month": valid_date_obj.month,
                "day": valid_date_obj.day,
            }

        return FieldValidationResult(
            field_id=field_id,
            field_type=self.field_type,
            raw_text=raw_text,
            normalized_text=normalized_str,
            validation_status=status,
            requires_review=requires_review,
            review_reasons=review_reasons,
            warning_codes=warning_codes,
            confidence=confidence,
            is_confidence_calibrated=is_confidence_calibrated,
            bounding_box=bounding_box,
            parsed_value=parsed_val,
        )
