"""Field validator for applicant names (Devanagari, Latin, and bilingual entries)."""

import re
import unicodedata
from typing import List, Optional

from app.core.config import Settings, get_settings
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import FieldValidationResult, ValidationStatus
from app.validation.validators.base import BaseFieldValidator

# Devanagari block: U+0900 to U+097F
DEVANAGARI_DIGITS = set("०१२३४५६७८९")
ASCII_DIGITS = set("0123456789")

# Combining marks in Devanagari (Matras, Nukta, Virama, Anusvara, etc.)
DEVANAGARI_COMBINING_MARKS = {
    chr(cp) for cp in range(0x0901, 0x0904)
} | {
    chr(cp) for cp in range(0x093A, 0x094F)
} | {
    chr(0x0951), chr(0x0952), chr(0x0953), chr(0x0954), chr(0x0962), chr(0x0963)
}

# Suspicious punctuation / symbols that never belong in a legitimate legal name
PROHIBITED_NAME_SYMBOLS = set("@#$%^&*()_+=<>[]{}|\\~`!?;:\"/\\")


class NameFieldValidator(BaseFieldValidator):
    """Semantic validator for personal and applicant names."""

    @property
    def field_type(self) -> str:
        return "NAME"

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
                review_reasons=["Name field is empty or contains only whitespace"],
                warning_codes=["EMPTY_VALUE"],
                confidence=confidence,
                is_confidence_calibrated=is_confidence_calibrated,
                bounding_box=bounding_box,
                parsed_value=None,
            )

        # 2. Unicode and Whitespace Normalization (NFC preserves Devanagari conjuncts & matras)
        nfc_text = unicodedata.normalize("NFC", raw_text)
        # Collapse multiple spaces, tabs, newlines into a single standard space
        normalized_whitespace = re.sub(r"\s+", " ", nfc_text).strip()

        # 3. Detect digits inside the name
        has_ascii_digits = any(c in ASCII_DIGITS for c in normalized_whitespace)
        has_devanagari_digits = any(c in DEVANAGARI_DIGITS for c in normalized_whitespace)
        if has_ascii_digits or has_devanagari_digits:
            warning_codes.append("NUMERIC_IN_NAME")
            review_reasons.append(
                "Name contains numeric digits which suggests an OCR misrecognition or barcode artifact"
            )
            requires_review = True
            status = ValidationStatus.INVALID

        # 4. Detect prohibited symbols or OCR garbage
        found_symbols = [c for c in normalized_whitespace if c in PROHIBITED_NAME_SYMBOLS]
        if found_symbols:
            warning_codes.append("SUSPICIOUS_CHARACTERS")
            review_reasons.append(
                f"Name contains suspicious non-alphabetic symbols: {', '.join(sorted(set(found_symbols)))}"
            )
            requires_review = True
            status = ValidationStatus.INVALID

        # 5. Detect isolated combining diacritics at start of text
        if normalized_whitespace and normalized_whitespace[0] in DEVANAGARI_COMBINING_MARKS:
            warning_codes.append("ISOLATED_DIACRITICS")
            review_reasons.append("Name begins with an isolated vowel mark without a preceding base consonant")
            requires_review = True
            if status != ValidationStatus.INVALID:
                status = ValidationStatus.WARNING

        # 6. Check length of purely alphabetic characters
        letters_only = [
            c for c in normalized_whitespace
            if unicodedata.category(c).startswith("L")
        ]
        if len(letters_only) < 2:
            warning_codes.append("SUSPICIOUSLY_SHORT")
            review_reasons.append(
                f"Name has only {len(letters_only)} letter(s), which is suspiciously brief"
            )
            requires_review = True
            if status != ValidationStatus.INVALID:
                status = ValidationStatus.WARNING

        # 7. Confidence evaluation
        conf_reasons, conf_codes, conf_trigger = self._evaluate_confidence(
            confidence=confidence,
            is_calibrated=is_confidence_calibrated,
            threshold=settings.NAME_MIN_CONFIDENCE,
            require_on_uncalibrated=settings.REQUIRE_REVIEW_ON_UNAVAILABLE_CONFIDENCE,
        )
        review_reasons.extend(conf_reasons)
        warning_codes.extend(conf_codes)
        if conf_trigger:
            requires_review = True
            if status == ValidationStatus.VALID:
                status = ValidationStatus.WARNING

        # 8. Normalized text: only emitted when not critically invalid
        safe_normalized = normalized_whitespace if status != ValidationStatus.INVALID else None

        return FieldValidationResult(
            field_id=field_id,
            field_type=self.field_type,
            raw_text=raw_text,
            normalized_text=safe_normalized,
            validation_status=status,
            requires_review=requires_review,
            review_reasons=review_reasons,
            warning_codes=warning_codes,
            confidence=confidence,
            is_confidence_calibrated=is_confidence_calibrated,
            bounding_box=bounding_box,
            parsed_value=safe_normalized,
        )
