"""Segmentation service coordinating preprocessing, template resolution, and field cropping."""

import logging
import time
from typing import Dict, NamedTuple, Optional, Tuple

import numpy as np

from app.core.config import Settings, get_settings
from app.core.errors import ValidationException
from app.preprocessing.service import ImagePreprocessingService
from app.schemas.segmentation import (
    FieldCropPreview,
    FieldDetectionResult,
    SegmentationResponseData,
)
from app.segmentation.strategies import (
    BaseSegmentationStrategy,
    ContourBasedStrategy,
    FixedTemplateStrategy,
    HybridSegmentationStrategy,
)
from app.segmentation.template_manager import FormTemplate, TemplateManager
from app.segmentation.visualizer import SegmentationVisualizer

logger = logging.getLogger("app.segmentation")


class SegmentationExecutionResult(NamedTuple):
    """Internal execution result returning image crops and schema response data."""
    annotated_image: np.ndarray
    field_crops: Dict[str, np.ndarray]
    response_data: SegmentationResponseData


class SegmentationService:
    """Orchestrates image preprocessing, layout template matching, and field cropping."""

    STRATEGIES: Dict[str, BaseSegmentationStrategy] = {
        "hybrid": HybridSegmentationStrategy(),
        "fixed": FixedTemplateStrategy(),
        "contour": ContourBasedStrategy(),
    }

    @classmethod
    def get_strategy(cls, name: str = "hybrid") -> BaseSegmentationStrategy:
        """Retrieve strategy instance by name (defaults to hybrid)."""
        normalized = (name or "hybrid").lower().strip()
        strategy = cls.STRATEGIES.get(normalized)
        if strategy is None:
            raise ValidationException(
                message=f"Unknown segmentation strategy '{name}'. Available: {', '.join(cls.STRATEGIES.keys())}",
                code="UNKNOWN_STRATEGY",
            )
        return strategy

    @classmethod
    def crop_field(cls, img: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
        """Safely crop rectangular region from image matrix."""
        height, width = img.shape[:2]
        cx1 = max(0, min(x1, width - 1))
        cy1 = max(0, min(y1, height - 1))
        cx2 = max(cx1 + 1, min(x2, width))
        cy2 = max(cy1 + 1, min(y2, height))

        cropped = img[cy1:cy2, cx1:cx2]
        if cropped.size == 0:
            raise ValidationException(
                message=f"Crop geometry [{x1}, {y1}, {x2}, {y2}] produced zero-sized matrix from image {width}x{height}",
                code="EMPTY_CROP",
            )
        return cropped

    @classmethod
    def process_and_segment(
        cls,
        image_bytes: bytes,
        filename: str,
        template_id: str = "devanagari_synthetic_v1",
        strategy_name: str = "hybrid",
        settings: Optional[Settings] = None,
    ) -> SegmentationExecutionResult:
        """Run preprocessing and segment all defined fields according to the layout template."""
        if settings is None:
            settings = get_settings()

        start_time = time.perf_counter()

        # 1. Resolve template specification
        template: FormTemplate = TemplateManager.get_template(template_id)

        # 2. Preprocess uploaded document (safe decode, deskew, contrast boost, stroke preservation)
        preprocess_res = ImagePreprocessingService.process_form_image(
            image_bytes=image_bytes,
            filename=filename,
            settings=settings,
        )
        processed_img = preprocess_res.processed_image
        prep_metadata = preprocess_res.response_data.metadata

        proc_h, proc_w = processed_img.shape[:2]
        orig_dims = (
            prep_metadata.original_dimensions.width,
            prep_metadata.original_dimensions.height,
        )
        deskew_angle = prep_metadata.skew_angle_detected if prep_metadata.skew_correction_applied else 0.0

        # 3. Execute field segmentation strategy
        strategy = cls.get_strategy(strategy_name)
        field_outputs, global_warnings = strategy.segment(
            img=processed_img,
            template=template,
            orig_dims=orig_dims,
            deskew_angle=deskew_angle,
        )

        # 4. Perform actual image cropping and generate crop previews
        field_crops: Dict[str, np.ndarray] = {}
        fields_dict: Dict[str, FieldDetectionResult] = {}

        for field_id, out in field_outputs.items():
            crop = cls.crop_field(
                img=processed_img,
                x1=out.bounding_box.x1,
                y1=out.bounding_box.y1,
                x2=out.bounding_box.x2,
                y2=out.bounding_box.y2,
            )
            field_crops[field_id] = crop

            crop_preview = SegmentationVisualizer.generate_crop_preview(
                crop_img=crop,
                field_id=field_id,
            )

            fields_dict[field_id] = FieldDetectionResult(
                field_id=out.field_id,
                field_name=out.field_name,
                field_type=out.field_type,
                bounding_box=out.bounding_box,
                original_bounding_box=out.original_bounding_box,
                detection_method=out.detection_method,
                status=out.status,
                confidence=out.confidence,
                warnings=out.warnings,
                crop_preview=crop_preview,
            )

        # 5. Generate annotated full document visualization (zero mutation of original)
        annotated_canvas = SegmentationVisualizer.draw_annotations(
            img=processed_img,
            fields=fields_dict,
        )
        full_preview = SegmentationVisualizer.generate_full_preview(
            annotated_img=annotated_canvas,
            max_dim=settings.MAX_PREVIEW_DIMENSION,
        )

        total_duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response_data = SegmentationResponseData(
            status="SUCCESS",
            template_id=template.template_id,
            template_name=template.name,
            fields=fields_dict,
            annotated_preview=full_preview,
            warnings=global_warnings,
            processing_time_ms=total_duration_ms,
        )

        logger.info(
            f"Segmented {len(fields_dict)} fields on '{filename}' using template '{template_id}' "
            f"in {total_duration_ms}ms"
        )

        return SegmentationExecutionResult(
            annotated_image=annotated_canvas,
            field_crops=field_crops,
            response_data=response_data,
        )
