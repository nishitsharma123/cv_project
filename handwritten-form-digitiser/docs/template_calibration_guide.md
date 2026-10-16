# Form Template Calibration & Configuration Guide

This guide describes how to measure, normalize, calibrate, and register new form layout templates for the **Handwritten Indic-Script Form Digitiser**.

---

## 1. Template Architecture & JSON Format

Templates are stored as standalone JSON files in:
`backend/app/segmentation/templates/<template_id>.json`

Each template decouples physical document layout geometry from segmentation and recognition algorithms.

### Schema Specification

```json
{
  "template_id": "string (unique identifier, e.g. 'devanagari_tax_challan_v1')",
  "name": "string (human-readable title)",
  "version": "string (semver, e.g. '1.0.0')",
  "description": "string (purpose and context of the template)",
  "canonical_width": 800,
  "canonical_height": 1000,
  "aspect_ratio": 0.8,
  "fields": [
    {
      "field_id": "applicant_name",
      "field_name": "Applicant Name",
      "field_type": "NAME | DATE | AMOUNT",
      "normalized_box": [0.10, 0.22, 0.85, 0.32],
      "required": true,
      "description": "Handwritten applicant full name in Devanagari script",
      "padding_px": 6,
      "expected_aspect_ratio_min": 3.0,
      "expected_aspect_ratio_max": 10.0
    }
  ]
}
```

---

## 2. Bounding Box Normalization Standard

To ensure invariance to scanner resolution (e.g. 150 DPI vs 300 DPI vs smartphone cameras), all field coordinates use **normalized bounding boxes**:

$$\text{normalized\_box} = [norm\_x1, norm\_y1, norm\_x2, norm\_y2]$$

where:
- $norm\_x1 = \frac{x_1}{\text{Canvas Width}}$ (Left edge, $0.0 \le norm\_x1 < 1.0$)
- $norm\_y1 = \frac{y_1}{\text{Canvas Height}}$ (Top edge, $0.0 \le norm\_y1 < 1.0$)
- $norm\_x2 = \frac{x_2}{\text{Canvas Width}}$ (Right edge, $norm\_x1 < norm\_x2 \le 1.0$)
- $norm\_y2 = \frac{y_2}{\text{Canvas Height}}$ (Bottom edge, $norm\_y1 < norm\_y2 \le 1.0$)

---

## 3. Step-by-Step Template Calibration Procedure

Follow this 5-step process when integrating a new physical form layout:

### Step 1: Scan / Capture Reference Blank Form
1. Place a clean, unblemished, blank copy of the printed form on a flatbed scanner or photograph it under uniform, diffuse lighting.
2. Ensure the document is oriented upright in portrait mode.
3. Save as a lossless PNG or high-quality JPEG.

### Step 2: Measure Pixel Coordinates
Using any image inspection tool (Figma, GIMP, Preview, or OpenCV script):
1. Note the total reference image dimensions $(W_{ref}, H_{ref})$.
2. For each field (e.g. `applicant_name`, `submission_date`, `declared_amount`):
   - Locate the top-left corner of the input box or write-in region: $(x_1, y_1)$.
   - Locate the bottom-right corner of the input box or write-in region: $(x_2, y_2)$.

### Step 3: Compute Normalized Coordinates
Calculate normalized ratios rounded to 4 decimal places:
```python
norm_x1 = round(x1 / W_ref, 4)
norm_y1 = round(y1 / H_ref, 4)
norm_x2 = round(x2 / W_ref, 4)
norm_y2 = round(y2 / H_ref, 4)
```

Ensure $norm\_x2 > norm\_x1$ and $norm\_y2 > norm\_y1$.

### Step 4: Author the JSON Template
1. Create a new file in `backend/app/segmentation/templates/<your_template_id>.json`.
2. Populate the metadata and field entries with your computed normalized boxes.
3. Set `padding_px` (typically `4` to `8` pixels) to provide safety margins for descenders or ascenders in handwritten Devanagari (such as lower matras *U-kar* `ु` or upper matras *E-kar* `े`).

### Step 5: Test and Verify Calibration
1. Send the calibration form image to `POST /api/segment`:
   ```bash
   curl -X POST "http://localhost:8000/api/segment" \
     -F "file=@reference_form.jpg" \
     -F "template_id=<your_template_id>"
   ```
2. Inspect the returned `annotated_preview` and individual `field_previews` to verify that bounding boxes encompass the intended handwriting areas without clipping.
