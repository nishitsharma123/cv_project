"""Mock OCR adapter — test double only.

This adapter is EXCLUSIVELY for automated tests.  It must NEVER be registered
as the default engine in production configuration.  It does not perform any
real character recognition and explicitly documents that fact in every result
it returns.

Key design contract:
- status is always SUCCESS so that tests can exercise downstream field-parsing
  and post-processing logic without needing a real model.
- text values are clearly synthetic placeholders (not sampled from real forms).
- confidence is a fixed mid-range constant to avoid accidentally calibrating
  thresholds against mock values.
- is_confidence_calibrated is always False.
"""

import logging
import time
from typing import List

import numpy as np

from app.recognition.base import BaseOCREngine
from app.schemas.recognition import OCRResultData, RecognitionStatus

logger = logging.getLogger("app.recognition.adapters.mock")

# Deterministic synthetic outputs keyed by field_type.
# Values are obviously synthetic to prevent accidental confusion with real data.
_MOCK_OUTPUTS: dict = {
    "NAME": "मॉक नाम",       # "mock name" transliterated
    "DATE": "01/01/2024",
    "AMOUNT": "0.00",
}
_DEFAULT_MOCK_OUTPUT = "मॉक पाठ"  # "mock text"
_MOCK_CONFIDENCE = 0.50           # mid-range; intentionally non-extreme
_MOCK_INFERENCE_MS = 0.1          # near-zero; indicates no real computation


class MockOCRAdapter(BaseOCREngine):
    """Test-only OCR adapter that returns deterministic synthetic outputs.

    Do NOT use this adapter for any evaluation, accuracy benchmarking, or
    production traffic.  All results are fabricated for structural testing only.
    """

    engine_id = "mock"
    display_name = "Mock OCR Adapter (Test Only)"
    supported_scripts: List[str] = ["Devanagari", "Latin"]

    def _do_initialize(self) -> None:
        # Nothing to initialize — mock adapter is always ready.
        self._initialized = True
        logger.debug("MockOCRAdapter initialized (test double, no real inference)")

    def is_available(self) -> bool:
        return True

    def recognize(self, crop: np.ndarray, field_id: str, field_type: str) -> OCRResultData:
        """Return a deterministic synthetic result without performing inference."""
        t0 = time.perf_counter()

        if crop is None or crop.size == 0:
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.EMPTY_INPUT,
                text="",
                raw_text="",
                confidence=0.0,
                is_confidence_calibrated=False,
                inference_time_ms=0.0,
                warnings=["Crop array was empty; cannot produce mock output"],
            )

        raw = _MOCK_OUTPUTS.get(field_type.upper(), _DEFAULT_MOCK_OUTPUT)
        elapsed_ms = (time.perf_counter() - t0) * 1000 + _MOCK_INFERENCE_MS

        return OCRResultData(
            field_id=field_id,
            field_type=field_type,
            model_id=self.engine_id,
            status=RecognitionStatus.SUCCESS,
            text=raw,
            raw_text=raw,
            confidence=_MOCK_CONFIDENCE,
            is_confidence_calibrated=False,
            inference_time_ms=round(elapsed_ms, 3),
            warnings=[
                "MOCK ADAPTER: output is synthetic and does not reflect real OCR accuracy"
            ],
        )
