"""Comprehensive test suite for Phase 05: Field-specific validation, review flags, and confidence handling."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.segmentation import BoundingBox
from app.schemas.validation import (
    DocumentValidationRequest,
    FieldValidationRequest,
    ValidationStatus,
)
from app.validation.service import ValidationService
from app.validation.validators.amount_validator import AmountFieldValidator
from app.validation.validators.date_validator import DateFieldValidator
from app.validation.validators.name_validator import NameFieldValidator


@pytest.fixture
def validation_service():
    return ValidationService()


@pytest.fixture
def name_validator():
    return NameFieldValidator()


@pytest.fixture
def date_validator():
    return DateFieldValidator()


@pytest.fixture
def amount_validator():
    return AmountFieldValidator()


@pytest.fixture
def default_bbox():
    return BoundingBox(x1=10, y1=20, x2=100, y2=50, width=90, height=30)


# ==============================================================================
# 1. NAME FIELD VALIDATION TESTS
# ==============================================================================

class TestNameFieldValidator:
    """Tests for personal and applicant name validation."""

    def test_valid_devanagari_name_high_confidence(self, name_validator, default_bbox):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="राकेश कुमार शर्मा",
            confidence=0.95,
            is_confidence_calibrated=True,
            bounding_box=default_bbox,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.requires_review is False
        assert res.normalized_text == "राकेश कुमार शर्मा"
        assert res.raw_text == "राकेश कुमार शर्मा"
        assert res.bounding_box == default_bbox
        assert len(res.warning_codes) == 0

    def test_valid_latin_name(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="Rakesh Kumar Sharma",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.requires_review is False
        assert res.normalized_text == "Rakesh Kumar Sharma"

    def test_whitespace_normalization(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="   राकेश   \t  कुमार    \n  शर्मा   ",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.normalized_text == "राकेश कुमार शर्मा"
        assert res.raw_text == "   राकेश   \t  कुमार    \n  शर्मा   "

    def test_unicode_normalization_preserves_matras_and_conjuncts(self, name_validator):
        # Name with anusvara, virama/conjunct, and matras: 'संतोष'
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="संतोष",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.normalized_text == "संतोष"

    def test_empty_name_flags_review_and_invalid(self, name_validator):
        for empty_input in ["", "   ", "\t\n"]:
            res = name_validator.validate(field_id="applicant_name", raw_text=empty_input)
            assert res.validation_status == ValidationStatus.INVALID
            assert res.requires_review is True
            assert "EMPTY_VALUE" in res.warning_codes
            assert res.normalized_text is None
            assert res.raw_text == empty_input

    def test_numeric_in_name_flags_invalid(self, name_validator):
        for bad_name in ["राम123", "Raj3sh", "अमित५"]:
            res = name_validator.validate(
                field_id="applicant_name",
                raw_text=bad_name,
                confidence=0.90,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.INVALID
            assert res.requires_review is True
            assert "NUMERIC_IN_NAME" in res.warning_codes
            assert res.normalized_text is None
            assert res.raw_text == bad_name  # Never overwritten!

    def test_suspicious_symbols_in_name(self, name_validator):
        for bad_name in ["राम@कुमार", "Rakesh#Sharma", "अमित!"]:
            res = name_validator.validate(
                field_id="applicant_name",
                raw_text=bad_name,
                confidence=0.90,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.INVALID
            assert res.requires_review is True
            assert "SUSPICIOUS_CHARACTERS" in res.warning_codes
            assert res.raw_text == bad_name

    def test_suspiciously_short_name(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="A",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.WARNING
        assert res.requires_review is True
        assert "SUSPICIOUSLY_SHORT" in res.warning_codes
        assert res.normalized_text == "A"

    def test_isolated_diacritic_at_start(self, name_validator):
        # Leading vowel sign '\u093e' (ा) without preceding consonant
        bad_str = "\u093eराम"
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text=bad_str,
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert "ISOLATED_DIACRITICS" in res.warning_codes
        assert res.requires_review is True


# ==============================================================================
# 2. DATE FIELD VALIDATION TESTS
# ==============================================================================

class TestDateFieldValidator:
    """Tests for calendar truth, format constraints, and Devanagari numerals."""

    def test_valid_standard_date_formats(self, date_validator):
        cases = [
            ("15/08/2024", "15/08/2024", "2024-08-15"),
            ("15-08-2024", "15/08/2024", "2024-08-15"),
            ("15.08.2024", "15/08/2024", "2024-08-15"),
            ("2024-08-15", "15/08/2024", "2024-08-15"),
        ]
        for inp, expected_disp, expected_iso in cases:
            res = date_validator.validate(
                field_id="submission_date",
                raw_text=inp,
                confidence=0.95,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.VALID
            assert res.requires_review is False
            assert res.normalized_text == expected_disp
            assert res.parsed_value["iso"] == expected_iso

    def test_valid_devanagari_numerals_date(self, date_validator):
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="१५/०८/२०२४",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.requires_review is False
        assert res.normalized_text == "15/08/2024"
        assert res.parsed_value["iso"] == "2024-08-15"
        assert res.raw_text == "१५/०८/२०२४"

    def test_leap_year_feb_29_valid(self, date_validator):
        # 2024 is a leap year -> Feb 29 is valid
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="29/02/2024",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.requires_review is False
        assert res.normalized_text == "29/02/2024"

    def test_non_leap_year_feb_29_invalid(self, date_validator):
        # 2023 is not a leap year -> Feb 29 does not exist!
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="29/02/2023",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "INVALID_CALENDAR_DATE" in res.warning_codes
        assert res.normalized_text is None
        assert res.raw_text == "29/02/2023"

    def test_impossible_days_per_month(self, date_validator):
        # April has 30 days; 31st does not exist
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="31/04/2024",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "INVALID_CALENDAR_DATE" in res.warning_codes
        assert res.normalized_text is None

    def test_invalid_month_rejected(self, date_validator):
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="15/13/2024",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert "INVALID_CALENDAR_DATE" in res.warning_codes

    def test_incomplete_date_never_guessed(self, date_validator):
        # Do not guess missing day, month, or year
        for incomplete in ["08/2024", "2024", "15/08"]:
            res = date_validator.validate(
                field_id="submission_date",
                raw_text=incomplete,
                confidence=0.90,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.INVALID
            assert res.requires_review is True
            assert "INCOMPLETE_DATE" in res.warning_codes
            assert res.normalized_text is None
            assert res.raw_text == incomplete

    def test_alphabetic_character_confusion_in_date(self, date_validator):
        # 'O' confused with '0'
        res = date_validator.validate(
            field_id="submission_date",
            raw_text="15/O8/2024",
            confidence=0.90,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "ALPHABETIC_IN_DATE" in res.warning_codes
        assert res.normalized_text is None
        assert res.raw_text == "15/O8/2024"

    def test_empty_date(self, date_validator):
        res = date_validator.validate(field_id="submission_date", raw_text="")
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "EMPTY_VALUE" in res.warning_codes


# ==============================================================================
# 3. AMOUNT FIELD VALIDATION TESTS
# ==============================================================================

class TestAmountFieldValidator:
    """Tests for currency formatting, separators, zero preservation, and OCR digit confusion."""

    def test_valid_integer_and_decimal_amounts(self, amount_validator):
        cases = [
            ("25000", "25000.00", 25000.0),
            ("25,000", "25000.00", 25000.0),
            ("1,00,000", "100000.00", 100000.0),
            ("25000.50", "25000.50", 25000.50),
        ]
        for inp, expected_norm, expected_val in cases:
            res = amount_validator.validate(
                field_id="declared_amount",
                raw_text=inp,
                confidence=0.95,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.VALID
            assert res.requires_review is False
            assert res.normalized_text == expected_norm
            assert res.parsed_value == expected_val

    def test_valid_zero_distinguished_from_empty(self, amount_validator):
        # 0 is a valid amount, NOT empty
        zero_cases = ["0", "0.00", "०", "०.००"]
        for zero_inp in zero_cases:
            res = amount_validator.validate(
                field_id="declared_amount",
                raw_text=zero_inp,
                confidence=0.95,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.VALID
            assert res.requires_review is False
            assert res.normalized_text == "0.00"
            assert res.parsed_value == 0.0

        # Contrast with empty
        empty_res = amount_validator.validate(field_id="declared_amount", raw_text="")
        assert empty_res.validation_status == ValidationStatus.INVALID
        assert empty_res.requires_review is True
        assert "EMPTY_VALUE" in empty_res.warning_codes

    def test_devanagari_numerals_amount(self, amount_validator):
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="२५,०००",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.VALID
        assert res.requires_review is False
        assert res.normalized_text == "25000.00"
        assert res.raw_text == "२५,०००"

    def test_currency_decorations_stripped_cleanly(self, amount_validator):
        cases = [
            ("Rs. 25,000/-", "25000.00"),
            ("₹ 500", "500.00"),
            ("INR 1000", "1000.00"),
            ("रु 2500", "2500.00"),
        ]
        for inp, expected_norm in cases:
            res = amount_validator.validate(
                field_id="declared_amount",
                raw_text=inp,
                confidence=0.95,
                is_confidence_calibrated=True,
            )
            assert res.validation_status == ValidationStatus.VALID
            assert res.normalized_text == expected_norm

    def test_alphabetic_confusion_flags_review(self, amount_validator):
        # 'O' confused with '0' inside numeric body
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="25O00",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "ALPHABETIC_IN_NUMERIC" in res.warning_codes
        assert res.normalized_text is None
        assert res.raw_text == "25O00"  # Original unmodified!

    def test_multiple_decimals_flagged(self, amount_validator):
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="25.00.00",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "MULTIPLE_DECIMALS" in res.warning_codes

    def test_misplaced_grouping_comma(self, amount_validator):
        # Comma after decimal point
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="25.00,00",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "INVALID_SEPARATOR" in res.warning_codes

    def test_negative_amount_flagged(self, amount_validator):
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="-500.00",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "NEGATIVE_AMOUNT" in res.warning_codes

    def test_excess_decimal_places(self, amount_validator):
        res = amount_validator.validate(
            field_id="declared_amount",
            raw_text="25.1234",
            confidence=0.95,
            is_confidence_calibrated=True,
        )
        assert res.validation_status == ValidationStatus.INVALID
        assert res.requires_review is True
        assert "EXCESS_DECIMAL_PLACES" in res.warning_codes


# ==============================================================================
# 4. CONFIDENCE HANDLING TESTS
# ==============================================================================

class TestConfidenceHandling:
    """Tests for calibrated vs uncalibrated scores, thresholds, and missing values."""

    def test_missing_confidence_handled_cleanly(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="राकेश कुमार",
            confidence=None,
            is_confidence_calibrated=False,
        )
        assert "CONFIDENCE_UNAVAILABLE" in res.warning_codes
        assert res.requires_review is True
        assert res.validation_status == ValidationStatus.WARNING

    def test_uncalibrated_confidence_triggers_review(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="राकेश कुमार",
            confidence=0.99,
            is_confidence_calibrated=False,  # Uncalibrated score
        )
        assert "CONFIDENCE_UNCALIBRATED" in res.warning_codes
        assert res.requires_review is True
        assert res.validation_status == ValidationStatus.WARNING

    def test_calibrated_low_confidence_triggers_review(self, name_validator):
        res = name_validator.validate(
            field_id="applicant_name",
            raw_text="राकेश कुमार",
            confidence=0.50,
            is_confidence_calibrated=True,  # Threshold is 0.70
        )
        assert "LOW_CONFIDENCE" in res.warning_codes
        assert res.requires_review is True
        assert res.validation_status == ValidationStatus.WARNING


# ==============================================================================
# 5. DOCUMENT VALIDATION & SERVICE TESTS
# ==============================================================================

class TestValidationService:
    """Tests for document-level validation aggregation and review flags."""

    def test_all_valid_fields_document_not_flagged(self, validation_service):
        fields = {
            "applicant_name": FieldValidationRequest(
                field_id="applicant_name",
                field_type="NAME",
                raw_text="राकेश कुमार शर्मा",
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
            "submission_date": FieldValidationRequest(
                field_id="submission_date",
                field_type="DATE",
                raw_text="15/08/2024",
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
            "declared_amount": FieldValidationRequest(
                field_id="declared_amount",
                field_type="AMOUNT",
                raw_text="25,000.00",
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
        }
        report = validation_service.validate_document(
            template_id="devanagari_synthetic_v1",
            fields=fields,
            engine_id="mock",
        )
        assert report.total_fields == 3
        assert report.valid_fields == 3
        assert report.review_required_fields == 0
        assert report.document_requires_review is False

    def test_one_invalid_field_triggers_document_review(self, validation_service):
        fields = {
            "applicant_name": FieldValidationRequest(
                field_id="applicant_name",
                field_type="NAME",
                raw_text="राकेश कुमार शर्मा",
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
            "submission_date": FieldValidationRequest(
                field_id="submission_date",
                field_type="DATE",
                raw_text="31/02/2024",  # Impossible calendar date!
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
            "declared_amount": FieldValidationRequest(
                field_id="declared_amount",
                field_type="AMOUNT",
                raw_text="25000",
                confidence=0.95,
                is_confidence_calibrated=True,
            ),
        }
        report = validation_service.validate_document(
            template_id="devanagari_synthetic_v1",
            fields=fields,
        )
        assert report.total_fields == 3
        assert report.valid_fields == 2
        assert report.review_required_fields == 1
        assert report.document_requires_review is True
        assert report.fields["submission_date"].validation_status == ValidationStatus.INVALID


# ==============================================================================
# 6. API INTEGRATION TESTS
# ==============================================================================

class TestValidationAPI:
    """Integration tests for POST /api/validate and POST /api/validate/field."""

    def test_post_validate_document_returns_200(self, client):
        payload = {
            "template_id": "devanagari_synthetic_v1",
            "engine_id": "mock",
            "fields": {
                "applicant_name": {
                    "field_id": "applicant_name",
                    "field_type": "NAME",
                    "raw_text": "राकेश कुमार",
                    "confidence": 0.95,
                    "is_confidence_calibrated": True,
                },
                "submission_date": {
                    "field_id": "submission_date",
                    "field_type": "DATE",
                    "raw_text": "15/08/2024",
                    "confidence": 0.95,
                    "is_confidence_calibrated": True,
                },
                "declared_amount": {
                    "field_id": "declared_amount",
                    "field_type": "AMOUNT",
                    "raw_text": "25,000",
                    "confidence": 0.95,
                    "is_confidence_calibrated": True,
                },
            },
        }
        response = client.post("/api/validate", json=payload)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        data = body["data"]
        assert data["total_fields"] == 3
        assert data["valid_fields"] == 3
        assert data["document_requires_review"] is False

    def test_post_validate_versioned_endpoint(self, client):
        payload = {
            "template_id": "devanagari_synthetic_v1",
            "fields": {
                "declared_amount": {
                    "field_id": "declared_amount",
                    "field_type": "AMOUNT",
                    "raw_text": "0.00",
                    "confidence": 0.95,
                    "is_confidence_calibrated": True,
                }
            },
        }
        response = client.post("/api/v1/validate", json=payload)
        assert response.status_code == 200
        assert response.json()["data"]["fields"]["declared_amount"]["normalized_text"] == "0.00"

    def test_post_validate_field_isolated(self, client):
        field_payload = {
            "field_id": "declared_amount",
            "field_type": "AMOUNT",
            "raw_text": "25O00",  # 'O' instead of 0
            "confidence": 0.90,
            "is_confidence_calibrated": True,
        }
        response = client.post("/api/validate/field", json=field_payload)
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["validation_status"] == "INVALID"
        assert data["requires_review"] is True
        assert "ALPHABETIC_IN_NUMERIC" in data["warning_codes"]
        assert data["raw_text"] == "25O00"
        assert data["normalized_text"] is None
