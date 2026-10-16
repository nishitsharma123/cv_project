"""Reusable image upload validation and computer vision preprocessing service."""

import base64
import logging
import math
import os
import time
from typing import List, NamedTuple, Optional, Tuple

import cv2
import numpy as np

from app.core.config import Settings, get_settings
from app.core.errors import (
    BadRequestException,
    PayloadTooLargeException,
    ValidationException,
)
from app.schemas.preprocessing import (
    ImageDimensions,
    PreprocessingMetadata,
    PreprocessResponseData,
    PreviewData,
)

logger = logging.getLogger("app.preprocessing")


class PreprocessResult(NamedTuple):
    """Result tuple containing processed NumPy matrix and schema response data."""
    processed_image: np.ndarray
    response_data: PreprocessResponseData


class ImagePreprocessingService:
    """Service encapsulating safe image decoding, validation, deskewing, and stroke enhancement."""

    @classmethod
    def validate_and_decode(
        cls,
        image_bytes: bytes,
        filename: str,
        settings: Optional[Settings] = None,
    ) -> Tuple[np.ndarray, ImageDimensions]:
        """Validate raw bytes and decode into an OpenCV BGR image matrix.

        Raises:
            BadRequestException: Empty file, unsupported format, or corrupt bytes.
            PayloadTooLargeException: File size exceeds configured limits.
            ValidationException: Image dimensions violate bounds.
        """
        if settings is None:
            settings = get_settings()

        # 1. Check for empty payload
        if not image_bytes or len(image_bytes) == 0:
            raise BadRequestException(
                message="Uploaded file is empty (0 bytes). Please upload a valid image.",
                code="EMPTY_FILE",
            )

        # 2. Check file size limits
        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if len(image_bytes) > max_bytes:
            raise PayloadTooLargeException(
                message=f"Uploaded file ({len(image_bytes)} bytes) exceeds the maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB.",
                code="PAYLOAD_TOO_LARGE",
            )

        # 3. Check filename extension against supported formats
        _, ext = os.path.splitext(filename or "")
        ext_clean = ext.lstrip(".").upper()
        if ext_clean and ext_clean not in settings.SUPPORTED_IMAGE_FORMATS:
            raise BadRequestException(
                message=f"Unsupported file format '{ext}'. Supported formats: {', '.join(settings.SUPPORTED_IMAGE_FORMATS)}.",
                code="UNSUPPORTED_FORMAT",
            )

        # 4. Decode bytes using OpenCV
        np_buf = np.frombuffer(image_bytes, dtype=np.uint8)
        decoded = cv2.imdecode(np_buf, cv2.IMREAD_UNCHANGED)

        if decoded is None:
            raise BadRequestException(
                message="Failed to decode image data. The file appears to be corrupted or not a valid image.",
                code="INVALID_IMAGE_DATA",
            )

        # 5. Normalize color channels to 3-channel BGR
        orig_height, orig_width = decoded.shape[:2]
        orig_channels = decoded.shape[2] if len(decoded.shape) > 2 else 1

        if len(decoded.shape) == 2:
            # Grayscale -> 3-channel BGR
            bgr_image = cv2.cvtColor(decoded, cv2.COLOR_GRAY2BGR)
        elif decoded.shape[2] == 4:
            # RGBA with transparency -> Alpha blend over clean white background
            alpha = decoded[:, :, 3].astype(np.float32) / 255.0
            bgr = decoded[:, :, :3].astype(np.float32)
            white_bg = np.ones_like(bgr, dtype=np.float32) * 255.0
            blended = bgr * alpha[:, :, None] + white_bg * (1.0 - alpha[:, :, None])
            bgr_image = np.clip(blended, 0, 255).astype(np.uint8)
        elif decoded.shape[2] == 3:
            bgr_image = decoded
        else:
            raise BadRequestException(
                message=f"Unsupported image channel count: {orig_channels}",
                code="UNSUPPORTED_CHANNEL_COUNT",
            )

        # 6. Validate image dimension limits (prevent decompression bombs & tiny icons)
        if (
            orig_height < settings.MIN_IMAGE_DIMENSION
            or orig_width < settings.MIN_IMAGE_DIMENSION
        ):
            raise ValidationException(
                message=(
                    f"Image dimensions ({orig_width}x{orig_height}px) are below the minimum "
                    f"allowed requirement of {settings.MIN_IMAGE_DIMENSION}x{settings.MIN_IMAGE_DIMENSION}px."
                ),
                code="INVALID_DIMENSIONS",
            )

        if (
            orig_height > settings.MAX_IMAGE_DIMENSION
            or orig_width > settings.MAX_IMAGE_DIMENSION
        ):
            raise ValidationException(
                message=(
                    f"Image dimensions ({orig_width}x{orig_height}px) exceed the maximum "
                    f"allowed limit of {settings.MAX_IMAGE_DIMENSION}x{settings.MAX_IMAGE_DIMENSION}px."
                ),
                code="INVALID_DIMENSIONS",
            )

        dimensions = ImageDimensions(
            width=orig_width,
            height=orig_height,
            channels=orig_channels,
        )
        return bgr_image, dimensions

    @classmethod
    def detect_skew_angle(cls, gray_img: np.ndarray) -> Tuple[float, bool]:
        """Detect moderate skew angle using edge detection and Hough line transform.

        Returns:
            Tuple of (detected_angle_degrees, is_reliable).
            Only moderate angles (|angle| <= 25 degrees) with sufficient line consensus are marked reliable.
        """
        height, width = gray_img.shape[:2]

        # Check for near-blank or uniform images
        if np.std(gray_img) < 5.0:
            return 0.0, False

        # Edge detection with Gaussian pre-smoothing
        blurred = cv2.GaussianBlur(gray_img, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150, apertureSize=3)

        # Probabilistic Hough Line Transform looking for horizontal text/line guides
        min_line_len = max(int(width * 0.15), 40)
        max_line_gap = 20
        lines = cv2.HoughLinesP(
            edges,
            rho=1,
            theta=np.pi / 180,
            threshold=80,
            minLineLength=min_line_len,
            maxLineGap=max_line_gap,
        )

        if lines is None or len(lines) < 3:
            return 0.0, False

        angles: List[float] = []
        for line in lines:
            coords = line.flatten()
            if len(coords) < 4:
                continue
            x1, y1, x2, y2 = coords[:4]
            dx = float(x2 - x1)
            dy = float(y2 - y1)
            if dx == 0:
                continue
            angle = math.degrees(math.atan2(dy, dx))
            # Focus on lines near horizontal (within +/- 30 degrees)
            if -30.0 <= angle <= 30.0:
                angles.append(angle)

        if len(angles) < 3:
            return 0.0, False

        # Calculate median angle and interquartile consistency
        median_angle = float(np.median(angles))
        std_dev = float(np.std(angles))

        # Reliable only if angle spread is tight and within moderate bounds
        if std_dev <= 4.0 and abs(median_angle) <= 25.0:
            return round(median_angle, 2), True

        return 0.0, False

    @classmethod
    def rotate_image(cls, img: np.ndarray, angle_degrees: float) -> np.ndarray:
        """Rotate image around its center by angle_degrees, filling borders with white."""
        if abs(angle_degrees) < 0.2:
            return img

        height, width = img.shape[:2]
        center = (width / 2.0, height / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)

        # Calculate bounding dimensions to avoid clipping
        cos_val = abs(rot_mat[0, 0])
        sin_val = abs(rot_mat[0, 1])
        new_w = int((height * sin_val) + (width * cos_val))
        new_h = int((height * cos_val) + (width * sin_val))

        rot_mat[0, 2] += (new_w / 2.0) - center[0]
        rot_mat[1, 2] += (new_h / 2.0) - center[1]

        border_val = (255, 255, 255) if len(img.shape) == 3 else 255
        rotated = cv2.warpAffine(
            img,
            rot_mat,
            (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=border_val,
        )
        return rotated

    @classmethod
    def detect_cardinal_rotation(cls, gray_img: np.ndarray) -> Tuple[int, bool]:
        """Detect if document orientation is rotated by 90/180/270 degrees when determinable.

        Returns:
            Tuple of (rotation_degrees, is_confident).
        """
        # If image is predominantly blank, do not attempt cardinal rotation
        if np.std(gray_img) < 5.0:
            return 0, False

        # Check aspect ratio: Standard Indic forms are almost universally portrait (H > W).
        # A landscape form with W/H > 1.3 in an expected portrait template strongly hints at 90-degree rotation.
        height, width = gray_img.shape[:2]
        aspect_ratio = width / float(height)

        # Evaluate text projection profile variance
        # Horizontal lines create high variance in row sums (alternating text & space)
        row_sums = np.sum(gray_img < 200, axis=1)
        col_sums = np.sum(gray_img < 200, axis=0)

        row_var = np.var(row_sums)
        col_var = np.var(col_sums)

        # If vertical variance dominates horizontal variance by a large margin on landscape forms,
        # document is likely rotated 90 degrees clockwise or counter-clockwise
        if aspect_ratio > 1.35 and col_var > row_var * 2.5:
            # Landscape orientation with vertical stripes -> rotated 90 degrees
            return 90, True

        return 0, False

    @classmethod
    def enhance_contrast_and_preserve_strokes(
        cls,
        img: np.ndarray,
    ) -> np.ndarray:
        """Improve contrast and suppress background noise without aggressive binarization.

        Preserves subtle handwriting strokes and matras via:
        1. LAB lightness channel CLAHE for uniform illumination normalization.
        2. Bilateral filtering for edge-preserving smoothing.
        """
        # 1. Convert to LAB color space to isolate illumination from chrominance
        lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        l_channel, a_channel, b_channel = cv2.split(lab)

        # 2. Apply gentle CLAHE (Contrast Limited Adaptive Histogram Equalization)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        l_enhanced = clahe.apply(l_channel)

        # 3. Merge back and convert to BGR
        lab_enhanced = cv2.merge((l_enhanced, a_channel, b_channel))
        contrast_boosted = cv2.cvtColor(lab_enhanced, cv2.COLOR_LAB2BGR)

        # 4. Bilateral filter preserves sharp ink edges while smoothing sensor grain
        smoothed = cv2.bilateralFilter(contrast_boosted, d=5, sigmaColor=35, sigmaSpace=35)
        return smoothed

    @classmethod
    def generate_preview(
        cls,
        img: np.ndarray,
        max_dim: int = 800,
    ) -> PreviewData:
        """Generate a compact downscaled JPEG preview encoded as a base64 data URL."""
        height, width = img.shape[:2]
        scaling_factor = min(1.0, float(max_dim) / max(height, width))

        if scaling_factor < 1.0:
            preview_w = max(int(width * scaling_factor), 1)
            preview_h = max(int(height * scaling_factor), 1)
            preview_img = cv2.resize(
                img,
                (preview_w, preview_h),
                interpolation=cv2.INTER_AREA,
            )
        else:
            preview_w, preview_h = width, height
            preview_img = img

        success, encoded = cv2.imencode(
            ".jpg",
            preview_img,
            [int(cv2.IMWRITE_JPEG_QUALITY), 80],
        )

        if not success:
            raise ValidationException(
                message="Failed to encode preview image.",
                code="PREVIEW_GENERATION_FAILED",
            )

        b64_str = base64.b64encode(encoded.tobytes()).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_str}"

        return PreviewData(
            format="image/jpeg",
            width=preview_w,
            height=preview_h,
            data_url=data_url,
        )

    @classmethod
    def process_form_image(
        cls,
        image_bytes: bytes,
        filename: str,
        settings: Optional[Settings] = None,
    ) -> PreprocessResult:
        """Execute end-to-end image validation, deskewing, and stroke enhancement pipeline."""
        if settings is None:
            settings = get_settings()

        start_time = time.perf_counter()
        applied_steps: List[str] = []

        # Step 1: Validate and decode
        img, orig_dims = cls.validate_and_decode(image_bytes, filename, settings)
        applied_steps.append("DECODE_AND_VALIDATE_PAYLOAD")

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Step 2: Cardinal 90-degree rotation check
        rotation_90, rotation_confident = cls.detect_cardinal_rotation(gray)
        rotation_applied = False
        if rotation_confident and rotation_90 != 0:
            if rotation_90 == 90:
                img = cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
            elif rotation_90 == 180:
                img = cv2.rotate(img, cv2.ROTATE_180)
            elif rotation_90 == 270:
                img = cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            rotation_applied = True
            applied_steps.append(f"CARDINAL_ROTATION_{rotation_90}_APPLIED")

        # Step 3: Skew detection & deskew rotation
        skew_angle, skew_reliable = cls.detect_skew_angle(gray)
        deskew_applied = False
        if skew_reliable and abs(skew_angle) >= 0.5:
            # Positive angle indicates clockwise tilt; rotate counter-clockwise
            img = cls.rotate_image(img, -skew_angle)
            deskew_applied = True
            applied_steps.append("GEOMETRIC_DESKEW_APPLIED")

        # Step 4: Contrast enhancement & edge-preserving smoothing
        enhanced_img = cls.enhance_contrast_and_preserve_strokes(img)
        applied_steps.append("CLAHE_CONTRAST_NORMALIZATION")
        applied_steps.append("BILATERAL_STROKE_PRESERVATION_FILTER")

        # Step 5: Generate downscaled preview
        preview = cls.generate_preview(enhanced_img, max_dim=settings.MAX_PREVIEW_DIMENSION)
        applied_steps.append("COMPACT_PREVIEW_GENERATION")

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        proc_h, proc_w = enhanced_img.shape[:2]
        proc_channels = enhanced_img.shape[2] if len(enhanced_img.shape) > 2 else 1

        metadata = PreprocessingMetadata(
            original_dimensions=orig_dims,
            processed_dimensions=ImageDimensions(
                width=proc_w,
                height=proc_h,
                channels=proc_channels,
            ),
            skew_angle_detected=skew_angle,
            skew_correction_applied=deskew_applied,
            rotation_90_detected=rotation_90,
            rotation_applied=rotation_applied,
            contrast_enhanced=True,
            noise_reduced=True,
            processing_time_ms=duration_ms,
        )

        response_data = PreprocessResponseData(
            status="SUCCESS",
            filename=filename,
            applied_steps=applied_steps,
            metadata=metadata,
            preview=preview,
        )

        logger.info(
            f"Preprocessed '{filename}' ({orig_dims.width}x{orig_dims.height} -> "
            f"{proc_w}x{proc_h}) in {duration_ms}ms [skew={skew_angle}°, deskew={deskew_applied}]"
        )

        return PreprocessResult(
            processed_image=enhanced_img,
            response_data=response_data,
        )
