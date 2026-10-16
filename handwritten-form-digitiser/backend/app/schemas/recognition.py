"""Pydantic schemas for OCR recognition results and engine metadata."""

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.common import SuccessResponse


class RecognitionStatus(str, Enum):
    """Possible outcomes of a recognition attempt.

    SUCCESS            -- Inference ran and returned text (may be empty string if field blank).
    ENGINE_UNAVAILABLE -- The selected engine binary/runtime is not installed.
    WEIGHTS_NOT_FOUND  -- Engine runtime present but model weights file missing.
    EMPTY_INPUT        -- The crop image had zero usable pixels after preprocessing.
    UNSUPPORTED_SCRIPT -- Engine does not support Devanagari/the requested script.
    FAILED             -- Engine raised an unexpected error during inference.
    """

    SUCCESS = "SUCCESS"
    ENGINE_UNAVAILABLE = "ENGINE_UNAVAILABLE"
    WEIGHTS_NOT_FOUND = "WEIGHTS_NOT_FOUND"
    EMPTY_INPUT = "EMPTY_INPUT"
    UNSUPPORTED_SCRIPT = "UNSUPPORTED_SCRIPT"
    FAILED = "FAILED"


class OCRResultData(BaseModel):
    """Result produced by a single OCR engine for a single field crop."""

    field_id: str = Field(..., description="Identifier of the form field this crop came from")
    field_type: str = Field(..., description="Semantic type: NAME, DATE, or AMOUNT")
    model_id: str = Field(..., description="Stable identifier of the OCR engine")
    status: RecognitionStatus = Field(..., description="Outcome of the recognition attempt")
    text: str = Field(
        default="",
        description="Post-processed recognized text. Empty when status != SUCCESS.",
    )
    raw_text: str = Field(
        default="",
        description="Unmodified engine output before field-type normalization. Empty when status != SUCCESS.",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Engine confidence score in [0.0, 1.0]. 0.0 when unavailable.",
    )
    is_confidence_calibrated: bool = Field(
        default=False,
        description="True only when the score has been empirically calibrated to a true posterior.",
    )
    inference_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Wall-clock time inside the engine inference call, in milliseconds.",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Non-fatal conditions encountered during recognition",
    )


class RecognitionRequestData(BaseModel):
    """Parameters accepted by POST /api/recognize."""

    template_id: str = Field(
        default="devanagari_synthetic_v1",
        description="Template to use for field segmentation",
    )
    engine_id: str = Field(
        default="tesseract",
        description="OCR engine to use: 'tesseract', 'crnn', or 'mock'",
    )
    include_crop_previews: bool = Field(
        default=False,
        description="Whether to include base64 field crop previews in the response",
    )


class EngineCapabilityData(BaseModel):
    """Describes a registered OCR engine identity and runtime capability."""

    engine_id: str = Field(..., description="Stable engine identifier")
    display_name: str = Field(..., description="Human-readable engine name")
    supported_scripts: List[str] = Field(
        ..., description="Scripts the engine supports (e.g. 'Devanagari', 'Latin')"
    )
    is_available: bool = Field(..., description="True if runtime and weights are present")
    unavailability_reason: Optional[str] = Field(
        default=None,
        description="Short reason why the engine is unavailable, if applicable",
    )
    setup_instructions: Optional[str] = Field(
        default=None,
        description="Instructions to install or configure the engine",
    )


class RecognitionResponseData(BaseModel):
    """Full-document recognition result grouping per-field OCR outputs."""

    template_id: str = Field(..., description="Applied form template identifier")
    engine_id: str = Field(..., description="Engine used for all fields")
    fields: Dict[str, OCRResultData] = Field(
        ..., description="Per-field recognition results keyed by field_id"
    )
    total_inference_time_ms: float = Field(
        ..., description="Sum of per-field inference times in milliseconds"
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Document-level recognition warnings",
    )


class RecognitionResponseEnvelope(SuccessResponse[RecognitionResponseData]):
    """Standardized response envelope for full-document recognition results."""
    pass


class EngineListResponseEnvelope(SuccessResponse[List[EngineCapabilityData]]):
    """Standardized response envelope for listing available OCR engines."""
    pass
