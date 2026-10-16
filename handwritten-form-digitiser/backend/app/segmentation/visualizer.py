"""Visualization utility for drawing field bounding boxes and generating crop previews."""

import base64
from typing import Dict, Tuple

import cv2
import numpy as np

from app.schemas.preprocessing import PreviewData
from app.schemas.segmentation import FieldCropPreview, FieldDetectionResult


class SegmentationVisualizer:
    """Renders non-destructive visual annotations on images and generates compact previews."""

    STATUS_COLORS: Dict[str, Tuple[int, int, int]] = {
        "DETECTED": (34, 197, 94),     # Vibrant Green (BGR)
        "FALLBACK": (0, 140, 255),     # Amber / Orange (BGR)
        "UNCERTAIN": (0, 140, 255),    # Amber / Orange (BGR)
        "NOT_FOUND": (40, 40, 230),    # Vibrant Red (BGR)
    }

    @classmethod
    def draw_annotations(
        cls,
        img: np.ndarray,
        fields: Dict[str, FieldDetectionResult],
    ) -> np.ndarray:
        """Draw bounding boxes and field label pills on a COPY of the image.

        Ensures the input image buffer is completely unmodified.
        """
        canvas = img.copy()
        height, width = canvas.shape[:2]

        for field_id, field in fields.items():
            box = field.bounding_box
            color = cls.STATUS_COLORS.get(field.status, (200, 200, 200))

            # 1. Draw outer bounding box rectangle
            cv2.rectangle(
                canvas,
                (box.x1, box.y1),
                (box.x2, box.y2),
                color,
                thickness=2,
            )

            # 2. Render label pill text
            label_text = f"{field.field_name} [{field.status}]"
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = max(0.4, min(0.65, width / 1200.0))
            thickness = 1

            (txt_w, txt_h), baseline = cv2.getTextSize(label_text, font, font_scale, thickness)

            # Determine label pill position (above box, or inside top if near top border)
            pill_y1 = box.y1 - txt_h - 8
            pill_y2 = box.y1
            if pill_y1 < 0:
                pill_y1 = box.y1
                pill_y2 = box.y1 + txt_h + 8

            pill_x1 = box.x1
            pill_x2 = min(width - 1, box.x1 + txt_w + 10)

            # Draw filled pill background for high legibility
            cv2.rectangle(
                canvas,
                (pill_x1, pill_y1),
                (pill_x2, pill_y2),
                color,
                thickness=-1,
            )

            # Draw text inside the pill
            text_x = pill_x1 + 5
            text_y = pill_y2 - 4 if pill_y1 < box.y1 else pill_y2 - 4
            cv2.putText(
                canvas,
                label_text,
                (text_x, text_y),
                font,
                font_scale,
                (255, 255, 255),
                thickness=thickness,
                lineType=cv2.LINE_AA,
            )

        return canvas

    @classmethod
    def generate_full_preview(
        cls,
        annotated_img: np.ndarray,
        max_dim: int = 800,
    ) -> PreviewData:
        """Encode downscaled annotated full form as a base64 JPEG data URL."""
        height, width = annotated_img.shape[:2]
        scaling_factor = min(1.0, float(max_dim) / max(height, width))

        if scaling_factor < 1.0:
            preview_w = max(int(width * scaling_factor), 1)
            preview_h = max(int(height * scaling_factor), 1)
            resized = cv2.resize(
                annotated_img,
                (preview_w, preview_h),
                interpolation=cv2.INTER_AREA,
            )
        else:
            preview_w, preview_h = width, height
            resized = annotated_img

        success, encoded = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 80])
        if not success:
            raise RuntimeError("Failed to encode annotated preview image.")

        b64_str = base64.b64encode(encoded.tobytes()).decode("utf-8")
        return PreviewData(
            format="image/jpeg",
            width=preview_w,
            height=preview_h,
            data_url=f"data:image/jpeg;base64,{b64_str}",
        )

    @classmethod
    def generate_crop_preview(
        cls,
        crop_img: np.ndarray,
        field_id: str,
        max_dim: int = 400,
    ) -> FieldCropPreview:
        """Encode individual cropped field ROI as a base64 JPEG data URL."""
        height, width = crop_img.shape[:2]
        scaling_factor = min(1.0, float(max_dim) / max(height, width)) if max(height, width) > max_dim else 1.0

        if scaling_factor < 1.0:
            preview_w = max(int(width * scaling_factor), 1)
            preview_h = max(int(height * scaling_factor), 1)
            resized = cv2.resize(
                crop_img,
                (preview_w, preview_h),
                interpolation=cv2.INTER_AREA,
            )
        else:
            preview_w, preview_h = width, height
            resized = crop_img

        success, encoded = cv2.imencode(".jpg", resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if not success:
            raise RuntimeError(f"Failed to encode crop preview for field '{field_id}'.")

        b64_str = base64.b64encode(encoded.tobytes()).decode("utf-8")
        return FieldCropPreview(
            field_id=field_id,
            preview_data_url=f"data:image/jpeg;base64,{b64_str}",
            width=preview_w,
            height=preview_h,
        )
