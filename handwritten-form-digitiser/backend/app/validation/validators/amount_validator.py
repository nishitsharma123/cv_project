"""Field validator for amounts (currency parsing, Devanagari numerals, OCR digit confusion, zero preservation)."""

import re
from decimal import Decimal, InvalidOperation
from typing import List, Optional

from app.core.config import Settings, get_settings
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import FieldValidationResult, ValidationStatus
from app.validation.validators.base import BaseFieldValidator

DEVANAGARI_TO_ASCII = {
    "०": "0", "१": "1", "२": "2", "३": "3", "४": "4",
    "५": "5", "६": "6", "७": "7", "८": "8", "९": "9",
}

# Recognized currency decorators that can be safely stripped from the perimeter
CURRENCY_PREFIXES = ["₹", "rs.", "rs", "inr", "रु.", "रु"]
CURRENCY_SUFFIXES = ["/-", "/=", ".-", "cr", "lakh", "lac", "k"]


class AmountFieldValidator(BaseFieldValidator):
    """Semantic validator for currency amounts, checking separators, decimal constraints, and 'O' vs '0' confusion."""

    @property
    def field_type(self) -> str:
        return "AMOUNT"

    @classmethod
    def _devanagari_to_ascii(cls, text: str) -> str:
        """Deterministically map Devanagari numerals to ASCII digits."""
        return "".join(DEVANAGARI_TO_ASCII.get(c, c) for c in text)

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

        # 1. Distinguish empty field from valid zero
        if raw_text is None or len(raw_text.strip()) == 0:
            return FieldValidationResult(
                field_id=field_id,
                field_type=self.field_type,
                raw_text=raw_text if raw_text is not None else "",
                normalized_text=None,
                validation_status=ValidationStatus.INVALID,
                requires_review=True,
                review_reasons=["Amount field is empty or whitespace-only"],
                warning_codes=["EMPTY_VALUE"],
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        trimmed = raw_text.strip()
        # Convert Devanagari digits to ASCII
        ascii_text = self._devanagari_to_ascii(trimmed)

        # 2. Check for negative sign
        is_negative = ascii_text.startswith("-") or ascii_text.endswith("-")
        if is_negative and not ascii_text.endswith("/-"):
            warning_codes.append("NEGATIVE_AMOUNT")
            review_reasons.append("Negative monetary amounts are prohibited")
            requires_review = True
            status = ValidationStatus.INVALID

        # 3. Strip recognized currency prefixes and suffixes
        cleaned = ascii_text.strip()
        cleaned_lower = cleaned.lower()

        # Strip prefixes
        for pfx in sorted(CURRENCY_PREFIXES, key=len, reverse=True):
            if cleaned_lower.startswith(pfx):
                cleaned = cleaned[len(pfx):].strip()
                cleaned_lower = cleaned.lower()
                break

        # Strip suffixes
        for sfx in sorted(CURRENCY_SUFFIXES, key=len, reverse=True):
            if cleaned_lower.endswith(sfx):
                cleaned = cleaned[:-len(sfx)].strip()
                cleaned_lower = cleaned.lower()
                break

        # 4. Check for unexpected alphabetic characters (e.g. 'O' confused with '0', 'l' for '1')
        remaining_alpha = [c for c in cleaned if c.isalpha()]
        if remaining_alpha:
            warning_codes.append("ALPHABETIC_IN_NUMERIC")
            unique_alphas = sorted(set(remaining_alpha))
            reasons_str = f"Amount contains unexpected alphabetic characters: {', '.join(unique_alphas)}."
            if "O" in unique_alphas or "o" in unique_alphas:
                reasons_str += " Detected possible OCR confusion between letter 'O' and digit '0'."
            review_reasons.append(reasons_str)
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

        # 5. Check for invalid separators and multiple decimals
        decimal_count = cleaned.count(".")
        if decimal_count > 1:
            warning_codes.append("MULTIPLE_DECIMALS")
            review_reasons.append(f"Amount contains multiple decimal points ({decimal_count})")
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

        # Check if commas appear after a decimal point (e.g. "25.00,00")
        if "." in cleaned and "," in cleaned:
            dot_idx = cleaned.index(".")
            if any(i > dot_idx for i, c in enumerate(cleaned) if c == ","):
                warning_codes.append("INVALID_SEPARATOR")
                review_reasons.append("Grouping comma appears after decimal point")
                requires_review = True
                status = ValidationStatus.INVALID

        # 6. Parse numeric amount and enforce decimal rules
        # Remove valid grouping commas
        num_str = cleaned.replace(",", "").strip()

        if not num_str or not re.match(r"^\d+(\.\d+)?$", num_str):
            warning_codes.append("INVALID_AMOUNT_FORMAT")
            review_reasons.append(f"Unable to parse valid monetary number from '{trimmed}'")
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

        try:
            dec_val = Decimal(num_str)
        except InvalidOperation:
            warning_codes.append("INVALID_AMOUNT_FORMAT")
            review_reasons.append("Decimal parsing failed")
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

        # Decimal rules checks
        if "." in num_str:
            fractional_part = num_str.split(".")[1]
            if not settings.AMOUNT_ALLOW_DECIMAL and int(fractional_part) > 0:
                warning_codes.append("DECIMALS_DISALLOWED")
                review_reasons.append("Decimal fractions are disabled by configuration")
                requires_review = True
                status = ValidationStatus.INVALID

            if len(fractional_part) > settings.AMOUNT_MAX_DECIMALS:
                warning_codes.append("EXCESS_DECIMAL_PLACES")
                review_reasons.append(
                    f"Amount has {len(fractional_part)} decimal places (maximum allowed: {settings.AMOUNT_MAX_DECIMALS})"
                )
                requires_review = True
                status = ValidationStatus.INVALID

        # 7. Confidence Evaluation
        conf_reasons, conf_codes, conf_trigger = self._evaluate_confidence(
            confidence=confidence,
            is_calibrated=is_confidence_calibrated,
            threshold=settings.AMOUNT_MIN_CONFIDENCE,
            require_on_uncalibrated=settings.REQUIRE_REVIEW_ON_UNAVAILABLE_CONFIDENCE,
        )
        review_reasons.extend(conf_reasons)
        warning_codes.extend(conf_codes)
        if conf_trigger:
            requires_review = True
            if status == ValidationStatus.VALID:
                status = ValidationStatus.WARNING

        # 8. Normalized text: format to 2 decimal places e.g. "25000.00" or "0.00"
        normalized_str: Optional[str] = None
        parsed_float: Optional[float] = None
        if status != ValidationStatus.INVALID:
            quantized = dec_val.quantize(Decimal("0.01"))
            normalized_str = f"{quantized:.2f}"
            parsed_float = float(quantized)

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
            parsed_value=parsed_float,
        )
