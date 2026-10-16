"""Pydantic schemas for field detection, bounding boxes, and segmentation results."""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from app.schemas.common import SuccessResponse
from app.schemas.preprocessing import PreviewData
from app.segmentation.template_manager import FormTemplateSummary


class BoundingBox(BaseModel):
    """Cartesian bounding box representation using [x1, y1, x2, y2] convention."""

    x1: int = Field(..., description="Top-left X coordinate in pixels")
    y1: int = Field(..., description="Top-left Y coordinate in pixels")
    x2: int = Field(..., description="Bottom-right X coordinate in pixels")
    y2: int = Field(..., description="Bottom-right Y coordinate in pixels")
    width: int = Field(..., description="Box width in pixels (x2 - x1)")
    height: int = Field(..., description="Box height in pixels (y2 - y1)")


class FieldCropPreview(BaseModel):
    """Base64 preview data URL representation of an individual cropped field region."""

    field_id: str = Field(..., description="Field identifier")
    preview_data_url: str = Field(..., description="Base64 encoded data URL of the cropped region")
    width: int = Field(..., description="Crop width in pixels")
    height: int = Field(..., description="Crop height in pixels")


class FieldDetectionResult(BaseModel):
    """Complete detection, bounding box, and extraction result for a single field."""

    field_id: str = Field(..., description="Stable field identifier (e.g. applicant_name)")
    field_name: str = Field(..., description="Human-readable field label")
    field_type: str = Field(..., description="Semantic type: NAME, DATE, or AMOUNT")
    bounding_box: BoundingBox = Field(..., description="Bounding box in processed image pixel coordinates")
    original_bounding_box: Optional[BoundingBox] = Field(
        default=None,
        description="Bounding box mapped back to raw input image coordinates",
    )
    detection_method: str = Field(
        ...,
        description="Strategy used: FIXED_TEMPLATE, CONTOUR_REFINED, or ALIGNED_TEMPLATE",
    )
    status: str = Field(
        ...,
        description="Detection status: DETECTED, UNCERTAIN, FALLBACK, or NOT_FOUND",
    )
    confidence: float = Field(
        ...,
        description="Detection confidence score between 0.0 and 1.0",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of domain warnings or boundary clamp notices",
    )
    crop_preview: Optional[FieldCropPreview] = Field(
        default=None,
        description="Lightweight preview thumbnail of the cropped ROI",
    )


class SegmentationResponseData(BaseModel):
    """Payload representing document field detection and segmentation results."""

    status: str = Field(default="SUCCESS", description="Overall segmentation status")
    template_id: str = Field(..., description="Identifier of the applied layout template")
    template_name: str = Field(..., description="Human-readable name of the applied template")
    fields: Dict[str, FieldDetectionResult] = Field(
        ...,
        description="Dictionary of detected fields keyed by field_id",
    )
    annotated_preview: PreviewData = Field(
        ...,
        description="Full-document preview with color-coded bounding boxes and field labels",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="Global document-level segmentation warnings",
    )
    processing_time_ms: float = Field(
        ...,
        description="Total duration of the preprocessing and segmentation pipeline in ms",
    )


class SegmentationResponseEnvelope(SuccessResponse[SegmentationResponseData]):
    """Standardized response envelope for segmentation results."""
    pass


class TemplateListResponseEnvelope(SuccessResponse[List[FormTemplateSummary]]):
    """Standardized response envelope for listing available form templates."""
    pass
