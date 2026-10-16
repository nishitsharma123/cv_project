"""Tests for the Phase 04 recognition engine.

All tests use ONLY the MockOCRAdapter.  No test asserts real OCR accuracy.
No test claims Tesseract or CRNN produce correct Devanagari text.
The mock adapter is used exclusively to verify:
  - Schema correctness
  - Service routing and engine dispatch
  - Status enum handling
  - API endpoint integration
  - Metric calculation correctness (independent of real OCR output)
"""

import io
import json
import struct
import zlib
from typing import Dict

import numpy as np
import pytest

from app.evaluation.metrics import (
    BenchmarkReport,
    SampleResult,
    compute_cer,
    compute_exact_match,
    compute_wer,
)
from app.recognition.adapters.mock_adapter import MockOCRAdapter
from app.recognition.service import RecognitionService
from app.schemas.recognition import RecognitionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_grey_crop(h: int = 32, w: int = 128, fill: int = 200) -> np.ndarray:
    """Return a solid greyscale crop (H, W) suitable for adapter input."""
    return np.full((h, w), fill, dtype=np.uint8)


def _make_bgr_crop(h: int = 32, w: int = 128) -> np.ndarray:
    """Return a solid BGR crop (H, W, 3) with a mid-grey fill."""
    return np.full((h, w, 3), 180, dtype=np.uint8)


def _minimal_png(w: int = 60, h: int = 30) -> bytes:
    """Construct a minimal valid PNG bytes object programmatically."""
    def _chunk(chunk_type: bytes, data: bytes) -> bytes:
        length = struct.pack(">I", len(data))
        crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
        return length + chunk_type + data + crc

    # IHDR: width, height, bit_depth=8, color_type=2 (RGB), compression=0, filter=0, interlace=0
    ihdr_data = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    # IDAT: raw pixel data (one filter byte per row + RGB pixels)
    raw_rows = b"".join(b"\x00" + bytes([180, 180, 180] * w) for _ in range(h))
    compressed = zlib.compress(raw_rows)
    # IEND
    signature = b"\x89PNG\r\n\x1a\n"
    return (
        signature
        + _chunk(b"IHDR", ihdr_data)
        + _chunk(b"IDAT", compressed)
        + _chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------------------
# MockOCRAdapter unit tests
# ---------------------------------------------------------------------------

class TestMockOCRAdapter:
    """Structural and contract tests for the mock adapter."""

    def setup_method(self):
        self.adapter = MockOCRAdapter()
        self.adapter.initialize()

    def test_always_available(self):
        assert self.adapter.is_available() is True

    def test_engine_id(self):
        assert self.adapter.engine_id == "mock"

    def test_supported_scripts_include_devanagari(self):
        assert "Devanagari" in self.adapter.supported_scripts

    def test_recognize_name_field_returns_success(self):
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="applicant_name", field_type="NAME")
        assert result.status == RecognitionStatus.SUCCESS
        assert result.field_id == "applicant_name"
        assert result.field_type == "NAME"
        assert result.model_id == "mock"
        assert isinstance(result.text, str) and len(result.text) > 0
        assert result.raw_text == result.text

    def test_recognize_date_field_returns_success(self):
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="submission_date", field_type="DATE")
        assert result.status == RecognitionStatus.SUCCESS
        assert "/" in result.text  # date format check

    def test_recognize_amount_field_returns_success(self):
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="amount_due", field_type="AMOUNT")
        assert result.status == RecognitionStatus.SUCCESS

    def test_recognize_empty_crop_returns_empty_input(self):
        empty_crop = np.array([], dtype=np.uint8).reshape(0, 0)
        result = self.adapter.recognize(empty_crop, field_id="f1", field_type="NAME")
        assert result.status == RecognitionStatus.EMPTY_INPUT
        assert result.text == ""

    def test_confidence_in_valid_range(self):
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="f1", field_type="NAME")
        assert 0.0 <= result.confidence <= 1.0

    def test_is_confidence_calibrated_is_false(self):
        """Mock adapter must never claim calibrated confidence."""
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="f1", field_type="NAME")
        assert result.is_confidence_calibrated is False

    def test_warns_about_synthetic_output(self):
        """Mock must always include a warning indicating synthetic output."""
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="f1", field_type="NAME")
        assert any("MOCK" in w.upper() or "synthetic" in w.lower() for w in result.warnings)

    def test_inference_time_ms_non_negative(self):
        crop = _make_bgr_crop()
        result = self.adapter.recognize(crop, field_id="f1", field_type="NAME")
        assert result.inference_time_ms >= 0.0

    def test_capability_returns_correct_engine_id(self):
        cap = self.adapter.capability()
        assert cap.engine_id == "mock"
        assert cap.is_available is True
        assert cap.unavailability_reason is None


# ---------------------------------------------------------------------------
# RecognitionService unit tests (using mock engine only)
# ---------------------------------------------------------------------------

class TestRecognitionService:
    """Tests for the RecognitionService engine registry and dispatch."""

    def setup_method(self):
        self.service = RecognitionService()

    def test_mock_engine_registered(self):
        engine_ids = [e.engine_id for e in self.service.list_engines()]
        assert "mock" in engine_ids

    def test_tesseract_engine_registered(self):
        engine_ids = [e.engine_id for e in self.service.list_engines()]
        assert "tesseract" in engine_ids

    def test_crnn_engine_registered(self):
        engine_ids = [e.engine_id for e in self.service.list_engines()]
        assert "crnn" in engine_ids

    def test_list_engines_returns_engine_capability_data(self):
        from app.schemas.recognition import EngineCapabilityData
        engines = self.service.list_engines()
        assert all(isinstance(e, EngineCapabilityData) for e in engines)

    def test_recognize_field_with_mock_returns_success(self):
        crop = _make_bgr_crop()
        result = self.service.recognize_field(crop, "f1", "NAME", engine_id="mock")
        assert result.status == RecognitionStatus.SUCCESS
        assert result.model_id == "mock"

    def test_recognize_field_unknown_engine_returns_engine_unavailable(self):
        crop = _make_bgr_crop()
        result = self.service.recognize_field(crop, "f1", "NAME", engine_id="nonexistent_engine")
        assert result.status == RecognitionStatus.ENGINE_UNAVAILABLE
        assert "nonexistent_engine" in result.warnings[0]

    def test_recognize_document_aggregates_all_fields(self):
        crops = {
            "applicant_name": _make_bgr_crop(),
            "submission_date": _make_bgr_crop(),
            "amount_due": _make_bgr_crop(),
        }
        types = {
            "applicant_name": "NAME",
            "submission_date": "DATE",
            "amount_due": "AMOUNT",
        }
        response = self.service.recognize_document(crops, types, engine_id="mock")
        assert set(response.fields.keys()) == {"applicant_name", "submission_date", "amount_due"}
        assert response.total_inference_time_ms >= 0.0

    def test_recognize_document_sets_total_inference_time(self):
        crops = {"f1": _make_bgr_crop(), "f2": _make_bgr_crop()}
        types = {"f1": "NAME", "f2": "DATE"}
        response = self.service.recognize_document(crops, types, engine_id="mock")
        individual_sum = sum(r.inference_time_ms for r in response.fields.values())
        assert abs(response.total_inference_time_ms - individual_sum) < 0.01

    def test_tesseract_unavailable_returns_engine_unavailable_not_exception(self):
        """Tesseract is not installed in the test environment — must return structured status."""
        crop = _make_bgr_crop()
        result = self.service.recognize_field(crop, "f1", "NAME", engine_id="tesseract")
        # Status must be ENGINE_UNAVAILABLE (Tesseract not installed) — never an unhandled exception
        assert result.status in (
            RecognitionStatus.ENGINE_UNAVAILABLE,
            RecognitionStatus.SUCCESS,  # if Tesseract somehow is installed
        )

    def test_crnn_returns_weights_not_found_or_engine_unavailable(self):
        """CRNN has no weights in test environment — must return structured status."""
        crop = _make_bgr_crop()
        result = self.service.recognize_field(crop, "f1", "NAME", engine_id="crnn")
        assert result.status in (
            RecognitionStatus.ENGINE_UNAVAILABLE,
            RecognitionStatus.WEIGHTS_NOT_FOUND,
            RecognitionStatus.SUCCESS,
        )


# ---------------------------------------------------------------------------
# Evaluation metrics unit tests (independent of OCR engines)
# ---------------------------------------------------------------------------

class TestCER:
    """Unit tests for compute_cer."""

    def test_identical_strings_cer_zero(self):
        assert compute_cer("राम", "राम") == 0.0

    def test_empty_reference_and_empty_hypothesis_cer_zero(self):
        assert compute_cer("", "") == 0.0

    def test_empty_hypothesis_non_empty_reference(self):
        cer = compute_cer("", "राम")
        assert cer == 1.0  # 3 deletions / 3 reference chars

    def test_non_empty_hypothesis_empty_reference(self):
        # Reference is empty; any hypothesis is an error
        assert compute_cer("abc", "") == 1.0

    def test_single_substitution(self):
        # "abc" vs "aXc" — 1 substitution / 3 chars
        cer = compute_cer("aXc", "abc")
        assert abs(cer - 1 / 3) < 1e-9

    def test_complete_mismatch(self):
        cer = compute_cer("xyz", "abc")
        assert cer == 1.0

    def test_devanagari_identical(self):
        assert compute_cer("01/01/2024", "01/01/2024") == 0.0

    def test_cer_symmetry_is_not_guaranteed(self):
        # CER is reference-normalized; not symmetric by definition
        cer_ab = compute_cer("ab", "abcd")
        cer_ba = compute_cer("abcd", "ab")
        # Both are valid; just verify they compute without error
        assert cer_ab >= 0.0
        assert cer_ba >= 0.0


class TestWER:
    """Unit tests for compute_wer."""

    def test_identical_sentences_wer_zero(self):
        assert compute_wer("राम कुमार", "राम कुमार") == 0.0

    def test_empty_both_wer_zero(self):
        assert compute_wer("", "") == 0.0

    def test_one_word_substitution(self):
        wer = compute_wer("राम सिंह", "राम कुमार")
        assert abs(wer - 0.5) < 1e-9

    def test_extra_word_in_hypothesis(self):
        wer = compute_wer("राम कुमार सिंह", "राम कुमार")
        # 1 insertion / 2 ref words
        assert abs(wer - 0.5) < 1e-9

    def test_non_empty_hypothesis_empty_reference(self):
        assert compute_wer("hello", "") == 1.0


class TestExactMatch:
    """Unit tests for compute_exact_match."""

    def test_identical_strings_match(self):
        assert compute_exact_match("राम", "राम") is True

    def test_case_insensitive(self):
        assert compute_exact_match("AMOUNT", "amount") is True

    def test_leading_trailing_whitespace_ignored(self):
        assert compute_exact_match("  राम  ", "राम") is True

    def test_internal_whitespace_normalized(self):
        assert compute_exact_match("राम  कुमार", "राम कुमार") is True

    def test_different_strings_no_match(self):
        assert compute_exact_match("राम", "श्याम") is False

    def test_empty_strings_match(self):
        assert compute_exact_match("", "") is True

    def test_one_empty_no_match(self):
        assert compute_exact_match("", "राम") is False


class TestBenchmarkReport:
    """Unit tests for BenchmarkReport aggregation."""

    def _make_sample(
        self,
        sample_id: str,
        field_id: str,
        hypothesis: str,
        reference: str,
        ocr_status: str = "SUCCESS",
    ) -> SampleResult:
        cer = compute_cer(hypothesis, reference) if ocr_status == "SUCCESS" else 0.0
        wer = compute_wer(hypothesis, reference) if ocr_status == "SUCCESS" else 0.0
        exact = compute_exact_match(hypothesis, reference) if ocr_status == "SUCCESS" else False
        return SampleResult(
            sample_id=sample_id,
            field_id=field_id,
            field_type="NAME",
            engine_id="mock",
            hypothesis=hypothesis,
            reference=reference,
            cer=cer,
            wer=wer,
            exact_match=exact,
            inference_time_ms=10.0,
            ocr_status=ocr_status,
        )

    def test_empty_samples_produces_zero_metrics(self):
        report = BenchmarkReport.from_samples("mock", [])
        assert report.total_samples == 0
        assert report.evaluated_samples == 0
        assert report.mean_cer == 0.0
        assert report.exact_match_rate == 0.0

    def test_all_exact_matches(self):
        samples = [
            self._make_sample("s1", "f1", "राम", "राम"),
            self._make_sample("s2", "f1", "श्याम", "श्याम"),
        ]
        report = BenchmarkReport.from_samples("mock", samples)
        assert report.exact_match_rate == 1.0
        assert report.mean_cer == 0.0
        assert report.mean_wer == 0.0

    def test_skipped_samples_not_counted_in_metrics(self):
        samples = [
            self._make_sample("s1", "f1", "राम", "राम"),
            self._make_sample("s2", "f1", "", "श्याम", ocr_status="ENGINE_UNAVAILABLE"),
        ]
        report = BenchmarkReport.from_samples("mock", samples)
        assert report.total_samples == 2
        assert report.evaluated_samples == 1
        assert report.skipped_samples == 1
        # Only s1 is evaluated; s1 is exact match
        assert report.exact_match_rate == 1.0

    def test_per_field_metrics_correct(self):
        samples = [
            self._make_sample("s1", "name_field", "राम", "राम"),
            self._make_sample("s2", "name_field", "श्याम", "राम"),
        ]
        report = BenchmarkReport.from_samples("mock", samples)
        assert "name_field" in report.per_field_metrics
        fm = report.per_field_metrics["name_field"]
        assert fm["count"] == 2.0
        assert 0.0 <= fm["exact_match_rate"] <= 1.0

    def test_warnings_passed_through(self):
        report = BenchmarkReport.from_samples("mock", [], warnings=["test warning"])
        assert "test warning" in report.warnings


# ---------------------------------------------------------------------------
# API integration tests (using the full FastAPI test client)
# ---------------------------------------------------------------------------

class TestRecognitionAPI:
    """Integration tests for GET /api/recognize/engines and POST /api/recognize."""

    def test_list_engines_returns_200(self, client):
        response = client.get("/api/recognize/engines")
        assert response.status_code == 200

    def test_list_engines_response_structure(self, client):
        response = client.get("/api/recognize/engines")
        body = response.json()
        assert body["success"] is True
        assert isinstance(body["data"], list)
        assert len(body["data"]) > 0

    def test_list_engines_contains_mock(self, client):
        response = client.get("/api/recognize/engines")
        engine_ids = [e["engine_id"] for e in response.json()["data"]]
        assert "mock" in engine_ids

    def test_list_engines_contains_tesseract(self, client):
        response = client.get("/api/recognize/engines")
        engine_ids = [e["engine_id"] for e in response.json()["data"]]
        assert "tesseract" in engine_ids

    def test_list_engines_each_has_required_fields(self, client):
        response = client.get("/api/recognize/engines")
        for engine in response.json()["data"]:
            assert "engine_id" in engine
            assert "display_name" in engine
            assert "supported_scripts" in engine
            assert "is_available" in engine

    def test_recognize_with_mock_engine_returns_200(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock", "template_id": "devanagari_synthetic_v1"},
            files={"file": ("test_form.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.status_code == 200

    def test_recognize_response_has_success_true(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("form.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.json()["success"] is True

    def test_recognize_response_has_fields_key(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("form.png", io.BytesIO(png_bytes), "image/png")},
        )
        body = response.json()
        assert "fields" in body["data"]

    def test_recognize_response_fields_have_status(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("form.png", io.BytesIO(png_bytes), "image/png")},
        )
        fields = response.json()["data"]["fields"]
        for field_id, field_data in fields.items():
            assert "status" in field_data, f"Field '{field_id}' missing 'status'"

    def test_recognize_empty_file_returns_400(self, client):
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("empty.png", io.BytesIO(b""), "image/png")},
        )
        assert response.status_code == 400

    def test_recognize_corrupted_file_returns_400(self, client):
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("bad.png", io.BytesIO(b"not_an_image_data_xyz"), "image/png")},
        )
        assert response.status_code == 400

    def test_recognize_includes_engine_id_in_response(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("form.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.json()["data"]["engine_id"] == "mock"

    def test_recognize_total_inference_time_non_negative(self, client):
        png_bytes = _minimal_png(w=200, h=100)
        response = client.post(
            "/api/recognize",
            data={"engine_id": "mock"},
            files={"file": ("form.png", io.BytesIO(png_bytes), "image/png")},
        )
        assert response.json()["data"]["total_inference_time_ms"] >= 0.0
