"""API routes for image upload validation and preprocessing."""

import logging
from fastapi import APIRouter, Depends, File, UploadFile

from app.core.config import Settings, get_settings
from app.core.errors import BadRequestException, PayloadTooLargeException
from app.preprocessing.service import ImagePreprocessingService
from app.schemas.preprocessing import PreprocessResponseEnvelope

logger = logging.getLogger("app.api.preprocessing")

router = APIRouter(tags=["Image Ingestion & Preprocessing"])


@router.post(
    "/preprocess",
    response_model=PreprocessResponseEnvelope,
    summary="Validate and preprocess an uploaded form image",
    description=(
        "Accepts a multipart form image upload (JPEG or PNG), validates decoded image bytes, "
        "applies moderate geometric deskewing, enhances contrast using CLAHE, and performs "
        "stroke-preserving bilateral filtering. Returns metadata and a lightweight preview."
    ),
)
async def preprocess_image(
    file: UploadFile = File(..., description="Uploaded form image (JPEG or PNG format)"),
    settings: Settings = Depends(get_settings),
) -> PreprocessResponseEnvelope:
    """Handle image upload, validation, and preprocessing pipeline execution."""
    if not file or not file.filename:
        raise BadRequestException(
            message="No file uploaded. Please provide an image file in the multipart request.",
            code="MISSING_FILE",
        )

    # Read uploaded bytes with size ceiling check to prevent memory exhaustion
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    chunk_size = 1024 * 64  # 64KB chunks
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

    # Delegate processing entirely to the domain service
    result = ImagePreprocessingService.process_form_image(
        image_bytes=image_bytes,
        filename=file.filename,
        settings=settings,
    )

    return PreprocessResponseEnvelope(data=result.response_data)
