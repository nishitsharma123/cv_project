"""API routing for document field detection, segmentation, and template discovery."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.core.config import Settings, get_settings
from app.core.errors import BadRequestException, PayloadTooLargeException
from app.schemas.segmentation import (
    SegmentationResponseEnvelope,
    TemplateListResponseEnvelope,
)
from app.segmentation.service import SegmentationService
from app.segmentation.template_manager import FormTemplate, TemplateManager

logger = logging.getLogger("app.api.segmentation")

router = APIRouter(tags=["Document Layout & Field Segmentation"])


@router.post(
    "/segment",
    response_model=SegmentationResponseEnvelope,
    summary="Preprocess and segment form fields",
    description=(
        "Accepts a form image upload and an optional template_id. Runs preprocessing "
        "(deskew, contrast enhancement, stroke preservation) and executes layout segmentation. "
        "Returns field bounding boxes, detection methods, status, warnings, and compact preview crops."
    ),
)
async def segment_form_fields(
    file: UploadFile = File(..., description="Uploaded form image (JPEG or PNG)"),
    template_id: str = Form("devanagari_synthetic_v1", description="Identifier of layout template"),
    strategy: str = Form("hybrid", description="Segmentation strategy: hybrid, fixed, or contour"),
    settings: Settings = Depends(get_settings),
) -> SegmentationResponseEnvelope:
    """Handle document upload, preprocessing, and field segmentation."""
    if not file or not file.filename:
        raise BadRequestException(
            message="No file uploaded. Please provide an image file in the multipart request.",
            code="MISSING_FILE",
        )

    # Stream-read payload with memory ceiling
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    chunk_size = 1024 * 64
    total_bytes = bytearray()

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes.extend(chunk)
        if len(total_bytes) > max_bytes:
            raise PayloadTooLargeException(
                message=f"Uploaded file exceeds maximum limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                code="PAYLOAD_TOO_LARGE",
            )

    image_bytes = bytes(total_bytes)

    # Delegate processing to the domain service
    result = SegmentationService.process_and_segment(
        image_bytes=image_bytes,
        filename=file.filename,
        template_id=template_id,
        strategy_name=strategy,
        settings=settings,
    )

    return SegmentationResponseEnvelope(data=result.response_data)


@router.get(
    "/templates",
    response_model=TemplateListResponseEnvelope,
    summary="List registered form layout templates",
    description="Returns all discovered form layout templates and their defined field configurations.",
)
async def list_form_templates() -> TemplateListResponseEnvelope:
    """Return all discovered form templates."""
    templates = TemplateManager.list_templates()
    return TemplateListResponseEnvelope(data=templates)


@router.get(
    "/templates/{template_id}",
    summary="Get detailed form template specification",
    description="Returns full geometry, normalized coordinates, and field parameters for a specific template.",
)
async def get_form_template(template_id: str) -> FormTemplate:
    """Return specific form template by identifier."""
    return TemplateManager.get_template(template_id)
