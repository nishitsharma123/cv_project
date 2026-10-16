"""Abstract base class for all OCR engine adapters."""

import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

from app.schemas.recognition import EngineCapabilityData, OCRResultData

logger = logging.getLogger("app.recognition.base")


class BaseOCREngine(ABC):
    """Contract every OCR adapter must fulfill.

    Adapters are responsible for:
    - Reporting their identity (engine_id, supported_scripts).
    - Self-diagnosing availability without raising exceptions.
    - Performing inference and returning a fully-populated OCRResultData.
    - Never exposing internal stack traces to callers.

    Adapters MUST NOT:
    - Fabricate recognition results.
    - Hardcode expected text as the model prediction.
    - Report SUCCESS status when inference did not actually run.
    """

    # Subclasses must set these class-level attributes.
    engine_id: str = ""
    display_name: str = ""
    supported_scripts: List[str] = []

    def __init__(self) -> None:
        self._initialized: bool = False
        self._unavailability_reason: str = ""
        self._setup_instructions: str = ""

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialize(self) -> None:
        """Perform one-time initialization (load model, check binary).

        Implementations must set ``self._initialized`` and
        ``self._unavailability_reason`` / ``self._setup_instructions``
        as appropriate.  Must not raise.
        """
        self._do_initialize()

    @abstractmethod
    def _do_initialize(self) -> None:
        """Internal initialization hook.  Override in subclasses."""

    # ------------------------------------------------------------------
    # Capability reporting
    # ------------------------------------------------------------------

    @abstractmethod
    def is_available(self) -> bool:
        """Return True iff the engine can currently produce predictions."""

    def capability(self) -> EngineCapabilityData:
        """Return a structured description of this engine's current state."""
        available = self.is_available()
        return EngineCapabilityData(
            engine_id=self.engine_id,
            display_name=self.display_name,
            supported_scripts=self.supported_scripts,
            is_available=available,
            unavailability_reason=self._unavailability_reason if not available else None,
            setup_instructions=self._setup_instructions if not available else None,
        )

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    @abstractmethod
    def recognize(self, crop: np.ndarray, field_id: str, field_type: str) -> OCRResultData:
        """Run inference on a single field crop.

        Parameters
        ----------
        crop:
            A BGR uint8 NumPy array of shape (H, W, 3) or greyscale (H, W).
            Callers guarantee the array is non-empty and contains at least one
            non-zero pixel row.
        field_id:
            Stable field identifier from the template (e.g. "applicant_name").
        field_type:
            Semantic type string: "NAME", "DATE", or "AMOUNT".

        Returns
        -------
        OCRResultData
            Fully populated.  Must never raise; capture exceptions internally
            and return status=FAILED with a descriptive warning instead.
        """
