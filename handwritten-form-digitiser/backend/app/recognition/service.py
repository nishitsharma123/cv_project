"""OCR recognition service — engine registry, lazy init, and per-field dispatch."""

import logging
from typing import Dict, List, Optional

import numpy as np

from app.recognition.base import BaseOCREngine
from app.recognition.adapters.mock_adapter import MockOCRAdapter
from app.recognition.adapters.tesseract_adapter import TesseractAdapter
from app.recognition.adapters.crnn_adapter import CRNNAdapter
from app.schemas.recognition import (
    EngineCapabilityData,
    OCRResultData,
    RecognitionResponseData,
    RecognitionStatus,
)

logger = logging.getLogger("app.recognition.service")


class RecognitionService:
    """Manages the OCR engine registry and dispatches per-field inference.

    Engines are registered at construction time and initialized lazily on
    first use.  Only the selected engine is initialized; unused engines are
    not loaded into memory.

    Adapter contract (enforced here):
    - ``is_available()`` is always checked before ``recognize()``.
    - If unavailable, ENGINE_UNAVAILABLE is returned without calling ``recognize()``.
    - All exceptions inside ``recognize()`` are captured by the adapter itself
      and returned as FAILED status records.
    """

    def __init__(self) -> None:
        # Registry: engine_id -> (adapter_instance, initialized_flag)
        self._registry: Dict[str, BaseOCREngine] = {}
        self._initialized_ids: set = set()
        self._register_defaults()

    # ------------------------------------------------------------------
    # Registry management
    # ------------------------------------------------------------------

    def _register_defaults(self) -> None:
        """Register all built-in adapters.  Ordering does not affect selection."""
        self.register_engine(MockOCRAdapter())
        self.register_engine(TesseractAdapter())
        self.register_engine(CRNNAdapter())

    def register_engine(self, engine: BaseOCREngine) -> None:
        """Register an OCR engine adapter.  Replaces any existing adapter with same id."""
        if not engine.engine_id:
            raise ValueError("Engine must have a non-empty engine_id")
        self._registry[engine.engine_id] = engine
        logger.debug("Registered OCR engine: %s", engine.engine_id)

    def _ensure_initialized(self, engine_id: str) -> BaseOCREngine:
        """Return the engine, initializing it exactly once."""
        engine = self._registry.get(engine_id)
        if engine is None:
            raise KeyError(f"Unknown OCR engine: '{engine_id}'")
        if engine_id not in self._initialized_ids:
            logger.info("Initializing OCR engine: %s", engine_id)
            engine.initialize()
            self._initialized_ids.add(engine_id)
        return engine

    # ------------------------------------------------------------------
    # Engine capability listing
    # ------------------------------------------------------------------

    def list_engines(self) -> List[EngineCapabilityData]:
        """Return capability info for all registered engines.

        Engines are initialized during this call so availability is accurate.
        """
        result: List[EngineCapabilityData] = []
        for engine_id in self._registry:
            engine = self._ensure_initialized(engine_id)
            result.append(engine.capability())
        return result

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def recognize_field(
        self,
        crop: np.ndarray,
        field_id: str,
        field_type: str,
        engine_id: str = "tesseract",
    ) -> OCRResultData:
        """Run inference on a single field crop using the specified engine.

        Never raises.  Returns OCRResultData with appropriate status on all failure paths.
        """
        if engine_id not in self._registry:
            logger.warning("Requested engine '%s' is not registered", engine_id)
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=engine_id,
                status=RecognitionStatus.ENGINE_UNAVAILABLE,
                warnings=[
                    f"Engine '{engine_id}' is not registered. "
                    f"Available engines: {list(self._registry.keys())}"
                ],
            )

        try:
            engine = self._ensure_initialized(engine_id)
        except Exception as exc:
            logger.exception("Engine initialization error for '%s'", engine_id)
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=engine_id,
                status=RecognitionStatus.FAILED,
                warnings=[f"Engine initialization error: {type(exc).__name__}"],
            )

        if not engine.is_available():
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=engine_id,
                status=RecognitionStatus.ENGINE_UNAVAILABLE,
                warnings=[engine._unavailability_reason],
            )

        return engine.recognize(crop, field_id, field_type)

    def recognize_document(
        self,
        field_crops: Dict[str, np.ndarray],
        field_types: Dict[str, str],
        engine_id: str = "tesseract",
    ) -> RecognitionResponseData:
        """Run inference across all fields and aggregate into a document result.

        Parameters
        ----------
        field_crops:
            Dict mapping field_id -> BGR/greyscale NumPy crop array.
        field_types:
            Dict mapping field_id -> field type string (NAME/DATE/AMOUNT).
        engine_id:
            Which engine to use for all fields.

        Returns
        -------
        RecognitionResponseData
            Fully populated document result.  Never raises.
        """
        results: Dict[str, OCRResultData] = {}
        document_warnings: List[str] = []

        for field_id, crop in field_crops.items():
            ftype = field_types.get(field_id, "UNKNOWN")
            result = self.recognize_field(crop, field_id, ftype, engine_id)
            results[field_id] = result
            if result.status != RecognitionStatus.SUCCESS:
                document_warnings.append(
                    f"Field '{field_id}': {result.status.value}"
                    + (f" — {result.warnings[0]}" if result.warnings else "")
                )

        total_ms = sum(r.inference_time_ms for r in results.values())

        return RecognitionResponseData(
            template_id="",  # caller populates
            engine_id=engine_id,
            fields=results,
            total_inference_time_ms=round(total_ms, 3),
            warnings=document_warnings,
        )
