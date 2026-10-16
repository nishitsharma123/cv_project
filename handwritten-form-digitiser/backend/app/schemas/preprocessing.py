"""Pydantic schemas for image upload validation and preprocessing."""

from typing import List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import SuccessResponse


class ImageDimensions(BaseModel):
    """Image spatial and channel dimensions."""

    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    channels: int = Field(..., description="Number of color channels (e.g. 1 for grayscale, 3 for BGR)")


class PreprocessingMetadata(BaseModel):
    """Detailed telemetry and parameters of the preprocessing pipeline."""

    original_dimensions: ImageDimensions = Field(
        ...,
        description="Dimensions of the decoded input image before transformations",
    )
    processed_dimensions: ImageDimensions = Field(
        ...,
        description="Dimensions of the normalized output image after transformations",
    )
    skew_angle_detected: float = Field(
        ...,
        description="Estimated skew angle in degrees (positive = counter-clockwise, negative = clockwise)",
    )
    skew_correction_applied: bool = Field(
        ...,
        description="Whether geometric deskew rotation was applied",
    )
    rotation_90_detected: int = Field(
        default=0,
        description="Detected cardinal page rotation in degrees (0, 90, 180, 270)",
    )
    rotation_applied: bool = Field(
        default=False,
        description="Whether cardinal 90-degree re-orientation was applied",
    )
    contrast_enhanced: bool = Field(
        ...,
        description="Whether CLAHE contrast normalization was applied",
    )
    noise_reduced: bool = Field(
        ...,
        description="Whether bilateral edge-preserving smoothing was applied",
    )
    processing_time_ms: float = Field(
        ...,
        description="Total duration of the preprocessing pipeline in milliseconds",
    )


class PreviewData(BaseModel):
    """Downscaled preview representation suitable for UI demo without large payloads."""

    format: str = Field(
        default="image/jpeg",
        description="MIME type of the preview image",
    )
    width: int = Field(..., description="Preview image width in pixels")
    height: int = Field(..., description="Preview image height in pixels")
    data_url: str = Field(
        ...,
        description="Base64 encoded data URL representation of the preview image",
    )


class PreprocessResponseData(BaseModel):
    """Business payload for image preprocessing endpoint."""

    status: str = Field(
        default="SUCCESS",
        description="Operational status of the preprocessing run",
    )
    filename: str = Field(
        ...,
        description="Original name of the uploaded image file",
    )
    applied_steps: List[str] = Field(
        ...,
        description="Ordered list of transformation operations applied to the image",
    )
    metadata: PreprocessingMetadata = Field(
        ...,
        description="Mathematical and telemetry parameters of the transformations",
    )
    preview: PreviewData = Field(
        ...,
        description="Lightweight preview thumbnail for UI inspection",
    )


class PreprocessResponseEnvelope(SuccessResponse[PreprocessResponseData]):
    """Standardized response envelope enclosing preprocessing results."""
    pass
