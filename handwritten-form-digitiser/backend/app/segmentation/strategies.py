"""Pluggable strategies for form field bounding box detection and segmentation."""

from abc import ABC, abstractmethod
import math
from typing import Dict, List, NamedTuple, Optional, Tuple

import cv2
import numpy as np

from app.schemas.segmentation import BoundingBox
from app.segmentation.template_manager import FieldDefinition, FormTemplate


class StrategyFieldOutput(NamedTuple):
    """Internal result of a field detection strategy."""
    field_id: str
    field_name: str
    field_type: str
    bounding_box: BoundingBox
    original_bounding_box: Optional[BoundingBox]
    detection_method: str
    status: str
    confidence: float
    warnings: List[str]


def clamp_and_validate_box(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    max_w: int,
    max_h: int,
    field_id: str,
) -> Tuple[BoundingBox, List[str]]:
    """Clamp box coordinates strictly to image bounds and validate geometry.

    Ensures 0 <= x1 < x2 <= max_w and 0 <= y1 < y2 <= max_h.
    """
    warnings: List[str] = []

    clamped_x1 = max(0, min(x1, max_w - 2))
    clamped_y1 = max(0, min(y1, max_h - 2))
    clamped_x2 = max(clamped_x1 + 1, min(x2, max_w))
    clamped_y2 = max(clamped_y1 + 1, min(y2, max_h))

    if clamped_x1 != x1 or clamped_y1 != y1 or clamped_x2 != x2 or clamped_y2 != y2:
        warnings.append(
            f"Field '{field_id}' box [{x1}, {y1}, {x2}, {y2}] was clamped to "
            f"[{clamped_x1}, {clamped_y1}, {clamped_x2}, {clamped_y2}] to fit within image bounds ({max_w}x{max_h})."
        )

    width = clamped_x2 - clamped_x1
    height = clamped_y2 - clamped_y1

    return (
        BoundingBox(
            x1=clamped_x1,
            y1=clamped_y1,
            x2=clamped_x2,
            y2=clamped_y2,
            width=width,
            height=height,
        ),
        warnings,
    )


def map_box_to_original(
    box: BoundingBox,
    deskew_angle: float,
    proc_w: int,
    proc_h: int,
    orig_w: int,
    orig_h: int,
) -> BoundingBox:
    """Map a bounding box from deskewed coordinates back to original raw image coordinates."""
    if abs(deskew_angle) < 0.2:
        # No significant deskew rotation was applied; scale directly to original dimensions
        scale_x = orig_w / float(proc_w)
        scale_y = orig_h / float(proc_h)
        return BoundingBox(
            x1=int(round(box.x1 * scale_x)),
            y1=int(round(box.y1 * scale_y)),
            x2=int(round(box.x2 * scale_x)),
            y2=int(round(box.y2 * scale_y)),
            width=int(round(box.width * scale_x)),
            height=int(round(box.height * scale_y)),
        )

    # When deskew occurred, rotate the 4 corners inversely around center
    center = (proc_w / 2.0, proc_h / 2.0)
    # The deskew applied was -deskew_angle, so inverse rotation is +deskew_angle
    inv_mat = cv2.getRotationMatrix2D(center, deskew_angle, 1.0)

    corners = np.array(
        [
            [box.x1, box.y1, 1.0],
            [box.x2, box.y1, 1.0],
            [box.x2, box.y2, 1.0],
            [box.x1, box.y2, 1.0],
        ]
    ).T

    transformed_corners = np.dot(inv_mat, corners)
    xs = transformed_corners[0, :]
    ys = transformed_corners[1, :]

    orig_x1 = max(0, min(int(round(np.min(xs))), orig_w - 2))
    orig_y1 = max(0, min(int(round(np.min(ys))), orig_h - 2))
    orig_x2 = max(orig_x1 + 1, min(int(round(np.max(xs))), orig_w))
    orig_y2 = max(orig_y1 + 1, min(int(round(np.max(ys))), orig_h))

    return BoundingBox(
        x1=orig_x1,
        y1=orig_y1,
        x2=orig_x2,
        y2=orig_y2,
        width=orig_x2 - orig_x1,
        height=orig_y2 - orig_y1,
    )


class BaseSegmentationStrategy(ABC):
    """Abstract base class for field detection and segmentation strategies."""

    @abstractmethod
    def segment(
        self,
        img: np.ndarray,
        template: FormTemplate,
        orig_dims: Optional[Tuple[int, int]] = None,
        deskew_angle: float = 0.0,
    ) -> Tuple[Dict[str, StrategyFieldOutput], List[str]]:
        """Detect and segment fields on the preprocessed image.

        Returns:
            Tuple of (detected_fields_dict, global_warnings_list).
        """
        pass


class FixedTemplateStrategy(BaseSegmentationStrategy):
    """Segments fields by scaling normalized template coordinates to image dimensions."""

    def segment(
        self,
        img: np.ndarray,
        template: FormTemplate,
        orig_dims: Optional[Tuple[int, int]] = None,
        deskew_angle: float = 0.0,
    ) -> Tuple[Dict[str, StrategyFieldOutput], List[str]]:
        height, width = img.shape[:2]
        orig_w, orig_h = orig_dims if orig_dims else (width, height)
        results: Dict[str, StrategyFieldOutput] = {}
        global_warnings: List[str] = []

        for field in template.fields:
            nx1, ny1, nx2, ny2 = field.normalized_box

            raw_x1 = int(round(nx1 * width)) - field.padding_px
            raw_y1 = int(round(ny1 * height)) - field.padding_px
            raw_x2 = int(round(nx2 * width)) + field.padding_px
            raw_y2 = int(round(ny2 * height)) + field.padding_px

            box, warnings = clamp_and_validate_box(
                raw_x1, raw_y1, raw_x2, raw_y2, width, height, field.field_id
            )

            orig_box = map_box_to_original(box, deskew_angle, width, height, orig_w, orig_h)

            status = "DETECTED" if len(warnings) == 0 else "FALLBACK"
            confidence = 0.90 if len(warnings) == 0 else 0.70

            results[field.field_id] = StrategyFieldOutput(
                field_id=field.field_id,
                field_name=field.field_name,
                field_type=field.field_type,
                bounding_box=box,
                original_bounding_box=orig_box,
                detection_method="FIXED_TEMPLATE",
                status=status,
                confidence=confidence,
                warnings=warnings,
            )

        return results, global_warnings


class ContourBasedStrategy(BaseSegmentationStrategy):
    """Detects rectangular form field outlines via morphological filtering, with controlled fallback."""

    def segment(
        self,
        img: np.ndarray,
        template: FormTemplate,
        orig_dims: Optional[Tuple[int, int]] = None,
        deskew_angle: float = 0.0,
    ) -> Tuple[Dict[str, StrategyFieldOutput], List[str]]:
        height, width = img.shape[:2]
        orig_w, orig_h = orig_dims if orig_dims else (width, height)
        results: Dict[str, StrategyFieldOutput] = {}
        global_warnings: List[str] = []

        # Convert to grayscale
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img.copy()

        # Check for uniform or blank image where contours cannot be found
        if np.std(gray) < 6.0:
            global_warnings.append("Image has near-zero contrast; contour detection cannot locate field boundaries.")
            # Fall back to template coordinates with explicit warning
            fixed_strat = FixedTemplateStrategy()
            return fixed_strat.segment(img, template, orig_dims, deskew_angle)

        # Morphological line detection to isolate rectangular form boxes
        bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY_INV, 15, -2)

        h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(int(width * 0.04), 15), 1))
        h_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, h_kernel)

        v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(int(height * 0.02), 10)))
        v_lines = cv2.morphologyEx(bw, cv2.MORPH_OPEN, v_kernel)

        table_mask = cv2.add(h_lines, v_lines)
        contours, _ = cv2.findContours(table_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        candidate_boxes: List[Tuple[int, int, int, int]] = []
        total_area = float(width * height)

        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            area = float(w * h)
            # Retain rectangular regions between 1% and 40% of document area
            if (0.008 * total_area) <= area <= (0.45 * total_area):
                aspect_ratio = float(w) / max(h, 1)
                if aspect_ratio >= 1.2:  # Form fields are predominantly wide
                    candidate_boxes.append((x, y, x + w, y + h))

        # Match each template field against candidate contours
        for field in template.fields:
            nx1, ny1, nx2, ny2 = field.normalized_box
            expected_x1 = int(round(nx1 * width))
            expected_y1 = int(round(ny1 * height))
            expected_x2 = int(round(nx2 * width))
            expected_y2 = int(round(ny2 * height))

            best_iou = 0.0
            best_candidate: Optional[Tuple[int, int, int, int]] = None

            for cx1, cy1, cx2, cy2 in candidate_boxes:
                # Compute Intersection-over-Union (IoU) with expected template location
                inter_x1 = max(expected_x1, cx1)
                inter_y1 = max(expected_y1, cy1)
                inter_x2 = min(expected_x2, cx2)
                inter_y2 = min(expected_y2, cy2)

                inter_w = max(0, inter_x2 - inter_x1)
                inter_h = max(0, inter_y2 - inter_y1)
                inter_area = inter_w * inter_h

                expected_area = (expected_x2 - expected_x1) * (expected_y2 - expected_y1)
                cand_area = (cx2 - cx1) * (cy2 - cy1)
                union_area = expected_area + cand_area - inter_area

                iou = inter_area / float(union_area) if union_area > 0 else 0.0
                if iou > best_iou:
                    best_iou = iou
                    best_candidate = (cx1, cy1, cx2, cy2)

            field_warnings: List[str] = []

            # If contour match has high IoU (>= 0.45), use refined contour box
            if best_candidate and best_iou >= 0.45:
                bx1, by1, bx2, by2 = best_candidate
                box, clamp_warn = clamp_and_validate_box(
                    bx1, by1, bx2, by2, width, height, field.field_id
                )
                field_warnings.extend(clamp_warn)
                orig_box = map_box_to_original(box, deskew_angle, width, height, orig_w, orig_h)
                detection_method = "CONTOUR_REFINED"
                status = "DETECTED"
                confidence = round(min(0.95, 0.70 + (best_iou * 0.3)), 2)
            else:
                # Fall back to template coordinates with an explicit warning
                bx1 = expected_x1 - field.padding_px
                by1 = expected_y1 - field.padding_px
                bx2 = expected_x2 + field.padding_px
                by2 = expected_y2 + field.padding_px

                box, clamp_warn = clamp_and_validate_box(
                    bx1, by1, bx2, by2, width, height, field.field_id
                )
                field_warnings.extend(clamp_warn)
                orig_box = map_box_to_original(box, deskew_angle, width, height, orig_w, orig_h)

                field_warnings.append(
                    f"Contour detection could not reliably locate field '{field.field_id}' "
                    f"(best IoU={round(best_iou, 2)}); fell back to normalized template coordinates."
                )
                detection_method = "FIXED_TEMPLATE"
                status = "FALLBACK"
                confidence = 0.75

            results[field.field_id] = StrategyFieldOutput(
                field_id=field.field_id,
                field_name=field.field_name,
                field_type=field.field_type,
                bounding_box=box,
                original_bounding_box=orig_box,
                detection_method=detection_method,
                status=status,
                confidence=confidence,
                warnings=field_warnings,
            )

        return results, global_warnings


class HybridSegmentationStrategy(BaseSegmentationStrategy):
    """Default strategy that attempts contour refinement with seamless template fallback."""

    def __init__(self):
        self._contour_strategy = ContourBasedStrategy()
        self._fixed_strategy = FixedTemplateStrategy()

    def segment(
        self,
        img: np.ndarray,
        template: FormTemplate,
        orig_dims: Optional[Tuple[int, int]] = None,
        deskew_angle: float = 0.0,
    ) -> Tuple[Dict[str, StrategyFieldOutput], List[str]]:
        try:
            return self._contour_strategy.segment(img, template, orig_dims, deskew_angle)
        except Exception as e:
            # Safe failover to fixed template if contour analysis fails
            results, warnings = self._fixed_strategy.segment(img, template, orig_dims, deskew_angle)
            warnings.append(f"Contour segmentation encountered exception ({str(e)}); reverted to fixed template.")
            return results, warnings
