"""Automated test suite for document layout analysis, field detection, and segmentation."""

import io
import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.preprocessing.service import ImagePreprocessingService
from app.schemas.segmentation import BoundingBox
from app.segmentation.service import SegmentationService
from app.segmentation.strategies import (
    ContourBasedStrategy,
    FixedTemplateStrategy,
    clamp_and_validate_box,
)
from app.segmentation.template_manager import (
    FieldDefinition,
    FormTemplate,
    TemplateManager,
)
from app.segmentation.visualizer import SegmentationVisualizer


def make_synthetic_form_with_field_boxes(
    width: int = 800,
    height: int = 1000,
    angle: float = 0.0,
    draw_contours: bool = True,
) -> bytes:
    """Generate synthetic form with printed rectangular field boxes matching devanagari_synthetic_v1."""
    canvas = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Document border
    cv2.rectangle(canvas, (20, 20), (width - 20, height - 20), (0, 0, 0), 2)
    cv2.putText(
        canvas,
        "DEVANAGARI FORM TEST FIXTURE",
        (50, 70),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (0, 0, 0),
        2,
    )

    if draw_contours:
        # Draw physical printed boxes matching template normalized boxes:
        # Field 1: applicant_name [0.10, 0.22, 0.85, 0.32] -> (80, 220) to (680, 320)
        cv2.rectangle(canvas, (80, 220), (680, 320), (0, 0, 0), 2)
        cv2.putText(canvas, "Name:", (85, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)

        # Field 2: submission_date [0.55, 0.38, 0.90, 0.48] -> (440, 380) to (720, 480)
        cv2.rectangle(canvas, (440, 380), (720, 480), (0, 0, 0), 2)
        cv2.putText(canvas, "Date:", (445, 370), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)

        # Field 3: declared_amount [0.10, 0.54, 0.60, 0.64] -> (80, 540) to (480, 640)
        cv2.rectangle(canvas, (80, 540), (480, 640), (0, 0, 0), 2)
        cv2.putText(canvas, "Amount:", (85, 530), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)

    # Simulated handwriting inside boxes
    cv2.putText(canvas, "Rakesh Sharma", (100, 280), cv2.FONT_HERSHEY_SCRIPT_SIMPLEX, 0.9, (20, 20, 20), 2)
    cv2.putText(canvas, "15/08/2026", (460, 440), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)
    cv2.putText(canvas, "25,000", (100, 600), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (20, 20, 20), 2)

    if abs(angle) > 0.01:
        center = (width / 2.0, height / 2.0)
        rot_mat = cv2.getRotationMatrix2D(center, angle, 1.0)
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
            borderValue=(255, 255, 255),
        )

    success, encoded = cv2.imencode(".jpg", canvas)
    assert success
    return encoded.tobytes()


# --- Unit & Strategy Tests ---


def test_known_template_coordinates():
    """Verify that normalized template coordinates compute exact pixel bounds on standard 800x1000 form."""
    template = TemplateManager.get_template("devanagari_synthetic_v1")
    strategy = FixedTemplateStrategy()

    img = np.ones((1000, 800, 3), dtype=np.uint8) * 255
    results, warnings = strategy.segment(img, template)

    assert "applicant_name" in results
    assert "submission_date" in results
    assert "declared_amount" in results

    # applicant_name: [0.10, 0.22, 0.85, 0.32] with 6px padding
    # expected: x1 = 80 - 6 = 74, y1 = 220 - 6 = 214, x2 = 680 + 6 = 686, y2 = 320 + 6 = 326
    name_box = results["applicant_name"].bounding_box
    assert name_box.x1 == 74
    assert name_box.y1 == 214
    assert name_box.x2 == 686
    assert name_box.y2 == 326
    assert name_box.width == 686 - 74
    assert name_box.height == 326 - 214

    # submission_date: [0.55, 0.38, 0.90, 0.48] with 6px padding
    # expected: x1 = 440 - 6 = 434, y1 = 380 - 6 = 374, x2 = 720 + 6 = 726, y2 = 480 + 6 = 486
    date_box = results["submission_date"].bounding_box
    assert date_box.x1 == 434
    assert date_box.y1 == 374
    assert date_box.x2 == 726
    assert date_box.y2 == 486

    # declared_amount: [0.10, 0.54, 0.60, 0.64] with 6px padding
    # expected: x1 = 80 - 6 = 74, y1 = 540 - 6 = 534, x2 = 480 + 6 = 486, y2 = 640 + 6 = 646
    amt_box = results["declared_amount"].bounding_box
    assert amt_box.x1 == 74
    assert amt_box.y1 == 534
    assert amt_box.x2 == 486
    assert amt_box.y2 == 646


def test_translated_and_resized_inputs():
    """Verify that bounding box pixel coordinates scale proportionally when input is resized."""
    template = TemplateManager.get_template("devanagari_synthetic_v1")
    strategy = FixedTemplateStrategy()

    # Form with 1200x1500 resolution (1.5x scaling factor)
    img = np.ones((1500, 1200, 3), dtype=np.uint8) * 255
    results, _ = strategy.segment(img, template)

    name_box = results["applicant_name"].bounding_box
    # expected: x1 = round(0.10 * 1200) - 6 = 120 - 6 = 114
    # x2 = round(0.85 * 1200) + 6 = 1020 + 6 = 1026
    assert name_box.x1 == 114
    assert name_box.x2 == 1026
    assert name_box.width == 1026 - 114


def test_moderately_skewed_image_segmentation():
    """Verify that moderately skewed input undergoes deskewing and returns original bounding box mapping."""
    skewed_bytes = make_synthetic_form_with_field_boxes(width=800, height=1000, angle=3.5)

    result = SegmentationService.process_and_segment(
        image_bytes=skewed_bytes,
        filename="skewed_test.jpg",
        template_id="devanagari_synthetic_v1",
    )

    data = result.response_data
    assert data.status == "SUCCESS"
    assert "applicant_name" in data.fields

    field = data.fields["applicant_name"]
    assert field.bounding_box.width > 0
    assert field.original_bounding_box is not None
    assert field.original_bounding_box.width > 0


def test_missing_template_raises_not_found(client: TestClient):
    """Verify requesting an unconfigured template returns HTTP 404 TEMPLATE_NOT_FOUND."""
    img_bytes = make_synthetic_form_with_field_boxes()
    files = {"file": ("form.jpg", io.BytesIO(img_bytes), "image/jpeg")}
    data = {"template_id": "nonexistent_custom_template"}

    response = client.post("/api/segment", files=files, data=data)
    assert response.status_code == 404

    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "TEMPLATE_NOT_FOUND"


def test_misconfigured_template_validation_error():
    """Verify template with inverted or out-of-bounds normalized box fails validation."""
    with pytest.raises(Exception) as exc_info:
        FieldDefinition(
            field_id="broken_field",
            field_name="Broken",
            field_type="NAME",
            normalized_box=[0.80, 0.50, 0.20, 0.90],  # x1 > x2 is invalid!
        )
    assert "Invalid horizontal coordinates" in str(exc_info.value)


def test_bounding_boxes_outside_image_are_clamped():
    """Verify that field coordinates extending outside image boundaries are strictly clamped."""
    # Register an in-memory template with box extending past canvas edge
    oversized_template = FormTemplate(
        template_id="oversized_test_tmpl",
        name="Oversized Box Template",
        fields=[
            FieldDefinition(
                field_id="edge_field",
                field_name="Edge Field",
                field_type="NAME",
                normalized_box=[0.85, 0.85, 0.99, 0.99],
                padding_px=100,  # Huge padding will extend past image border
            )
        ],
    )
    TemplateManager.register_in_memory(oversized_template)

    strategy = FixedTemplateStrategy()
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    results, _ = strategy.segment(img, oversized_template)

    box = results["edge_field"].bounding_box
    assert box.x2 <= 500
    assert box.y2 <= 500
    assert box.x1 >= 0
    assert box.y1 >= 0
    assert len(results["edge_field"].warnings) > 0
    assert "clamped" in results["edge_field"].warnings[0].lower()


def test_empty_crop_prevention():
    """Verify clamp_and_validate_box prevents 0-width or 0-height boxes."""
    box, warnings = clamp_and_validate_box(
        x1=100, y1=100, x2=100, y2=100, max_w=500, max_h=500, field_id="zero_field"
    )
    assert box.width >= 1
    assert box.height >= 1
    assert box.x2 > box.x1
    assert box.y2 > box.y1


def test_overlapping_fields_handling():
    """Verify multiple overlapping fields are both processed without interference."""
    overlapping_template = FormTemplate(
        template_id="overlapping_test_tmpl",
        name="Overlapping Fields Template",
        fields=[
            FieldDefinition(
                field_id="field_a",
                field_name="Field A",
                field_type="NAME",
                normalized_box=[0.10, 0.10, 0.60, 0.40],
            ),
            FieldDefinition(
                field_id="field_b",
                field_name="Field B",
                field_type="NAME",
                normalized_box=[0.40, 0.20, 0.80, 0.50],
            ),
        ],
    )
    TemplateManager.register_in_memory(overlapping_template)

    strategy = FixedTemplateStrategy()
    img = np.ones((500, 500, 3), dtype=np.uint8) * 255
    results, _ = strategy.segment(img, overlapping_template)

    assert "field_a" in results
    assert "field_b" in results
    assert results["field_a"].bounding_box.width > 0
    assert results["field_b"].bounding_box.width > 0


def test_contour_strategy_unreliable_fallback_warning():
    """Verify that when contour detection cannot locate field boxes, it records warning and falls back to template."""
    # Generate form WITHOUT drawn rectangular boxes (borderless text on canvas)
    borderless_form_bytes = make_synthetic_form_with_field_boxes(
        width=800,
        height=1000,
        draw_contours=False,
    )

    result = SegmentationService.process_and_segment(
        image_bytes=borderless_form_bytes,
        filename="borderless_form.jpg",
        template_id="devanagari_synthetic_v1",
        strategy_name="contour",
    )

    data = result.response_data
    assert data.status == "SUCCESS"

    # Crucial check: Must NOT fabricate false contour detections!
    # Should produce FALLBACK status and warning explaining contour ambiguity
    for field_id, field in data.fields.items():
        assert field.status == "FALLBACK"
        assert field.detection_method == "FIXED_TEMPLATE"
        assert any("contour detection could not reliably locate" in w.lower() for w in field.warnings)


def test_visualizer_does_not_modify_original_image():
    """Verify that SegmentationVisualizer.draw_annotations leaves input array completely unmodified."""
    canvas = np.ones((300, 300, 3), dtype=np.uint8) * 255
    original_checksum = np.sum(canvas)

    dummy_box = BoundingBox(x1=50, y1=50, x2=200, y2=150, width=150, height=100)
    from app.schemas.segmentation import FieldDetectionResult

    field = FieldDetectionResult(
        field_id="name",
        field_name="Applicant Name",
        field_type="NAME",
        bounding_box=dummy_box,
        detection_method="FIXED_TEMPLATE",
        status="DETECTED",
        confidence=0.9,
    )

    annotated = SegmentationVisualizer.draw_annotations(canvas, {"name": field})

    # Original canvas must remain bit-for-bit identical
    assert np.sum(canvas) == original_checksum
    # Annotated canvas must contain drawn annotations
    assert not np.array_equal(canvas, annotated)


# --- Endpoint Integration Tests ---


def test_api_segment_endpoint_success(client: TestClient):
    """Verify POST /api/segment processes valid form, segments fields, and returns preview crops."""
    form_bytes = make_synthetic_form_with_field_boxes()
    files = {"file": ("form.jpg", io.BytesIO(form_bytes), "image/jpeg")}
    data = {"template_id": "devanagari_synthetic_v1", "strategy": "hybrid"}

    response = client.post("/api/segment", files=files, data=data)
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True

    data_payload = body["data"]
    assert data_payload["status"] == "SUCCESS"
    assert data_payload["template_id"] == "devanagari_synthetic_v1"

    # Check all three fields are present and extracted
    fields = data_payload["fields"]
    assert "applicant_name" in fields
    assert "submission_date" in fields
    assert "declared_amount" in fields

    for fid in ["applicant_name", "submission_date", "declared_amount"]:
        f = fields[fid]
        assert f["bounding_box"]["width"] > 0
        assert f["bounding_box"]["height"] > 0
        assert f["crop_preview"] is not None
        assert f["crop_preview"]["preview_data_url"].startswith("data:image/jpeg;base64,")

    # Check full document annotated preview is provided
    assert data_payload["annotated_preview"]["data_url"].startswith("data:image/jpeg;base64,")
    assert data_payload["annotated_preview"]["width"] <= 800


def test_api_list_templates_endpoint(client: TestClient):
    """Verify GET /api/templates returns discovered templates including devanagari_synthetic_v1."""
    response = client.get("/api/templates")
    assert response.status_code == 200

    body = response.json()
    assert body["success"] is True

    templates = body["data"]
    assert len(templates) >= 1
    template_ids = [t["template_id"] for t in templates]
    assert "devanagari_synthetic_v1" in template_ids
