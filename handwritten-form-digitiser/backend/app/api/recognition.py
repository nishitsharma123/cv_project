"""Recognition API router — POST /recognize and GET /recognize/engines."""

import logging
import time
from typing import Dict

import numpy as np
from fastapi import APIRouter, File, Form, Request, UploadFile, status

from app.core.config import get_settings
from app.core.errors import BadRequestException, PayloadTooLargeException
from app.recognition.service import RecognitionService
from app.schemas.recognition import (
    EngineListResponseEnvelope,
    RecognitionResponseData,
    RecognitionResponseEnvelope,
)
from app.segmentation.service import SegmentationService

logger = logging.getLogger("app.api.recognition")

router = APIRouter(tags=["Recognition"])

# Module-level singleton (initialized once per process)
_recognition_service: RecognitionService = RecognitionService()


@router.get(
    "/recognize/engines",
    response_model=EngineListResponseEnvelope,
    summary="List all registered OCR engines and their availability status",
    response_description="Registered OCR engine capabilities",
)
async def list_engines() -> EngineListResponseEnvelope:
    """Return a list of all registered OCR engines with their availability status.

    This endpoint does NOT perform any inference.  It checks whether each
    engine binary and model weights are present without loading full models
    into memory.
    """
    engines = _recognition_service.list_engines()
    return EngineListResponseEnvelope(data=engines)


@router.post(
    "/recognize",
    response_model=RecognitionResponseEnvelope,
    summary="Run OCR on all field crops from an uploaded form image",
    response_description="Per-field OCR recognition results",
    status_code=status.HTTP_200_OK,
)
async def recognize_form(
    request: Request,
    file: UploadFile = File(..., description="Form image file (JPEG or PNG)"),
    template_id: str = Form(
        default="devanagari_synthetic_v1",
        description="Form template to use for field segmentation",
    ),
    engine_id: str = Form(
        default="tesseract",
        description="OCR engine: 'tesseract', 'crnn', or 'mock'",
    ),
    strategy: str = Form(
        default="hybrid",
        description="Segmentation strategy: hybrid, fixed, or contour",
    ),
) -> RecognitionResponseEnvelope:
    """Upload a form image and receive per-field OCR recognition results.

    Pipeline:
    1. Read and validate the uploaded image.
    2. Preprocess (deskew, CLAHE, bilateral filter).
    3. Segment fields using the specified template and strategy.
    4. Run the selected OCR engine on each field crop.
    5. Return structured per-field results.

    The ``mock`` engine is permitted here for integration testing but its
    results are clearly labeled as synthetic in the response warnings.
    """
    t0 = time.perf_counter()

    if not file or not file.filename:
        raise BadRequestException(
            message="No file uploaded. Please provide an image file in the multipart request.",
            code="MISSING_FILE",
        )

    # Stream-read payload with memory ceiling
    settings = getattr(request.app.state, "settings", None) or get_settings()
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
    if not image_bytes:
        raise BadRequestException(
            message="Uploaded file is empty (0 bytes). Please upload a valid image.",
            code="EMPTY_FILE",
        )

    # Normalize strategy name
    strat_clean = (strategy or "hybrid").lower().strip()
    if strat_clean in ("fixed_template", "fixed-template"):
        strat_clean = "fixed"

    # Segment document (runs validation, decode, deskew, contrast, stroke preservation, layout matching, and crop extraction)
    seg_result = SegmentationService.process_and_segment(
        image_bytes=image_bytes,
        filename=file.filename or "upload.png",
        template_id=template_id,
        strategy_name=strat_clean,
        settings=settings,
    )

    # Extract crops and field types
    field_crops: Dict[str, np.ndarray] = seg_result.field_crops
    field_types: Dict[str, str] = {
        fid: fdet.field_type
        for fid, fdet in seg_result.response_data.fields.items()
    }
    doc_warnings = list(seg_result.response_data.warnings)

    # Recognize
    rec_response = _recognition_service.recognize_document(
        field_crops=field_crops,
        field_types=field_types,
        engine_id=engine_id,
    )

    # Reconstruct response data with template_id and accumulated warnings
    final_response = RecognitionResponseData(
        template_id=template_id,
        engine_id=rec_response.engine_id,
        fields=rec_response.fields,
        total_inference_time_ms=rec_response.total_inference_time_ms,
        warnings=doc_warnings + rec_response.warnings,
    )

    elapsed_ms = (time.perf_counter() - t0) * 1000
    logger.info(
        "Recognition completed: template=%s engine=%s fields=%d total_ms=%.1f",
        template_id,
        engine_id,
        len(final_response.fields),
        elapsed_ms,
    )

    return RecognitionResponseEnvelope(data=final_response)

