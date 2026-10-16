"""Automated tests for image upload validation, deskewing, and preprocessing."""

import io
import math
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.preprocessing.service import ImagePreprocessingService


def generate_synthetic_form_image(
    width: int = 600,
    height: int = 800,
    angle_degrees: float = 0.0,
    img_format: str = ".jpg",
) -> bytes:
    """Generate in-memory synthetic form image with printed guide lines and simulated handwriting."""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Draw simulated printed form header and bounding boxes
    cv2.rectangle(canvas, (30, 30), (width - 30, height - 30), (0, 0, 0), 2)
    cv2.line(canvas, (30, 90), (width - 30, 90), (0, 0, 0), 2)
    cv2.putText(
        canvas,
        "APPLICATION FORM",
        (50, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
    )

    # Draw horizontal text guide lines
    for y in range(160, height - 60, 80):
        cv2.line(canvas, (50, y), (width - 50, y), (20, 20, 20), 2)
        # Draw simulated handwriting strokes above each line
        pts = np.array(
            [
                [70, y - 25],
                [90, y - 45],
                [130, y - 20],
                [170, y - 40],
                [220, y - 22],
                [270, y - 35],
                [340, y - 20],
            ],
            np.int32,
        )
        pts = pts.reshape((-1, 1, 2))
        cv2.polylines(canvas, [pts], False, (10, 10, 10), 2)

    # Apply synthetic rotation if specified
    if abs(angle_degrees) > 0.01:
        center = (width / 2.0, height / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, angle_degrees, 1.0)
        cos_val = abs(rot_mat[0, 0])
        sin_val = abs(rot_mat[0, 1])
        new_w = int((height * sin_val) + (width * cos_val))
        new_h = int((height * cos_val) + (width * sin_val))
        rot_mat[0, 2] += (new_w / 2.0) - center[0]
        rot_mat[1, 2] += (new_h / 2.0) - center[1]
        canvas = cv2.warpAffine(
            canvas,
            rot_mat,
            (new_w, new_h),
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=(255, 255, 255),
        )

    success, encoded = cv2.imencode(img_format, canvas)
    assert success, "Failed to encode synthetic test image"
    return encoded.tobytes()


def generate_synthetic_png_alpha() -> bytes:
    """Generate in-memory 4-channel RGBA image with transparent and opaque regions."""
    rgba = np.zeros((300, 300, 4), dtype=np.uint8)
    # Background transparent (alpha = 0)
    # Opaque black box in center (alpha = 255)
    cv2.rectangle(rgba, (50, 50), (250, 250), (0, 0, 0, 255), -1)
    success, encoded = cv2.imencode(".png", rgba)
    assert success
    return encoded.tobytes()


# --- Endpoint Integration Tests ---


def test_preprocess_valid_jpeg_returns_200_and_preview(client: TestClient):
    """Verify uploading a valid JPEG form returns HTTP 200, applied steps, and preview data."""
    img_bytes = generate_synthetic_form_image(width=500, height=700, img_format=".jpg")
    files = {"file": ("sample_form.jpg", io.BytesIO(img_bytes), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert "timestamp" in body

    data = body["data"]
    assert data["status"] == "SUCCESS"
    assert data["filename"] == "sample_form.jpg"
    assert "DECODE_AND_VALIDATE_PAYLOAD" in data["applied_steps"]
    assert "CLAHE_CONTRAST_NORMALIZATION" in data["applied_steps"]
    assert "COMPACT_PREVIEW_GENERATION" in data["applied_steps"]

    metadata = data["metadata"]
    assert metadata["original_dimensions"]["width"] == 500
    assert metadata["original_dimensions"]["height"] == 700
    assert metadata["contrast_enhanced"] is True
    assert metadata["noise_reduced"] is True
    assert metadata["processing_time_ms"] > 0

    preview = data["preview"]
    assert preview["format"] == "image/jpeg"
    assert preview["data_url"].startswith("data:image/jpeg;base64,")
    assert preview["width"] <= 800
    assert preview["height"] <= 800


def test_preprocess_valid_png_with_alpha_channel(client: TestClient):
    """Verify 4-channel PNG with alpha transparency is composited over white."""
    png_bytes = generate_synthetic_png_alpha()
    files = {"file": ("transparent_form.png", io.BytesIO(png_bytes), "image/png")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True
    assert body["data"]["metadata"]["original_dimensions"]["channels"] == 4
    # Processed output normalized to 3 channels BGR
    assert body["data"]["metadata"]["processed_dimensions"]["channels"] == 3


def test_preprocess_versioned_endpoint(client: TestClient):
    """Verify versioned endpoint /api/v1/preprocess functions identically."""
    img_bytes = generate_synthetic_form_image(width=400, height=400, img_format=".png")
    files = {"file": ("form_v1.png", io.BytesIO(img_bytes), "image/png")}

    response = client.post("/api/v1/preprocess", files=files)
    assert response.status_code == 200
    assert response.json()["success"] is True


def test_preprocess_rejects_corrupted_image(client: TestClient):
    """Verify uploading a corrupted byte stream returns HTTP 400 INVALID_IMAGE_DATA."""
    corrupted_bytes = b"\xff\xd8\xff\xe0" + b"\x00" * 50 + b"not-a-valid-jpeg-image"
    files = {"file": ("corrupt.jpg", io.BytesIO(corrupted_bytes), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_IMAGE_DATA"
    assert "Failed to decode image data" in body["error"]["message"]


def test_preprocess_rejects_unsupported_format(client: TestClient):
    """Verify uploading an unsupported extension returns HTTP 400 UNSUPPORTED_FORMAT."""
    dummy_text = b"This is a plain text file, not an image."
    files = {"file": ("notes.txt", io.BytesIO(dummy_text), "text/plain")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNSUPPORTED_FORMAT"
    assert "Unsupported file format" in body["error"]["message"]


def test_preprocess_rejects_empty_file(client: TestClient):
    """Verify uploading 0 bytes returns HTTP 400 EMPTY_FILE."""
    files = {"file": ("empty.jpg", io.BytesIO(b""), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 400

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "EMPTY_FILE"
    assert "empty" in body["error"]["message"].lower()


def test_preprocess_rejects_undersized_dimensions(client: TestClient):
    """Verify image dimensions below minimum allowed (100x100) return HTTP 422 INVALID_DIMENSIONS."""
    tiny_canvas = np.ones((60, 60, 3), dtype=np.uint8) * 200
    _, encoded = cv2.imencode(".jpg", tiny_canvas)
    files = {"file": ("tiny.jpg", io.BytesIO(encoded.tobytes()), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 422

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "INVALID_DIMENSIONS"
    assert "below the minimum allowed requirement" in body["error"]["message"]


def test_preprocess_skewed_image_detects_and_corrects(client: TestClient):
    """Verify synthetic image with 5-degree skew triggers deskew detection and correction."""
    skewed_bytes = generate_synthetic_form_image(
        width=700,
        height=900,
        angle_degrees=5.0,
        img_format=".jpg",
    )
    files = {"file": ("skewed_form.jpg", io.BytesIO(skewed_bytes), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 200

    data = response.json()["data"]
    metadata = data["metadata"]

    assert metadata["skew_correction_applied"] is True
    # Verify detected skew angle is within +/- 1.5 degrees of ground truth 5.0 degrees
    assert 3.5 <= abs(metadata["skew_angle_detected"]) <= 6.5
    assert "GEOMETRIC_DESKEW_APPLIED" in data["applied_steps"]


def test_preprocess_blank_uniform_image_handled_gracefully(client: TestClient):
    """Verify completely uniform image does not crash and skips deskewing gracefully."""
    blank_canvas = np.ones((400, 400, 3), dtype=np.uint8) * 255
    _, encoded = cv2.imencode(".jpg", blank_canvas)
    files = {"file": ("blank.jpg", io.BytesIO(encoded.tobytes()), "image/jpeg")}

    response = client.post("/api/preprocess", files=files)
    assert response.status_code == 200

    data = response.json()["data"]
    # Deskew should be safely skipped for uniform images
    assert data["metadata"]["skew_correction_applied"] is False


def test_stroke_preservation_integrity():
    """Verify fine line strokes retain intensity and continuity through preprocessing."""
    test_img = np.ones((300, 300, 3), dtype=np.uint8) * 255
    # Draw fine 1px and 2px simulated handwriting strokes
    cv2.line(test_img, (50, 150), (250, 150), (30, 30, 30), 1)
    cv2.line(test_img, (150, 50), (150, 250), (40, 40, 40), 2)

    enhanced = ImagePreprocessingService.enhance_contrast_and_preserve_strokes(test_img)

    # Stroke pixels must remain dark and distinguishable from background
    stroke_pixel_1 = enhanced[150, 100]  # On the horizontal 1px line
    bg_pixel = enhanced[50, 50]          # Empty background

    assert np.mean(bg_pixel) > 230, "Background should remain bright"
    assert np.mean(stroke_pixel_1) < 120, "Fine stroke must not be erased or bleached"


def test_service_rejects_oversized_payload():
    """Verify service raises PayloadTooLargeException when payload exceeds configured limit."""
    settings = Settings(MAX_UPLOAD_SIZE_MB=1)  # 1MB limit for testing
    oversized_bytes = b"0" * (1024 * 1024 + 100)

    with pytest.raises(Exception) as exc_info:
        ImagePreprocessingService.validate_and_decode(
            image_bytes=oversized_bytes,
            filename="large.jpg",
            settings=settings,
        )
    assert "PAYLOAD_TOO_LARGE" in str(getattr(exc_info.value, "code", ""))
