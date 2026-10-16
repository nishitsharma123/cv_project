# High-Level REST API Contract Specification

**Service:** Handwritten Indic-Script Form Digitiser API  
**Base URL:** `/api/v1`  
**Protocol:** HTTP/1.1 or HTTP/2  
**Format:** JSON (`application/json`) / Multipart (`multipart/form-data`)

---

## 1. Global Standards & Conventions

### 1.1 Response Envelope
All API endpoints return predictable, structured JSON envelopes:

```json
{
  "success": true,
  "data": {},
  "timestamp": "2026-10-16T14:40:00Z"
}
```

In the event of an error:
```json
{
  "success": false,
  "error": {
    "code": "INVALID_IMAGE_FORMAT",
    "message": "Uploaded file must be a valid PNG, JPEG, or TIFF image.",
    "details": []
  },
  "timestamp": "2026-10-16T14:40:00Z"
}
```

### 1.2 HTTP Status Codes
- `200 OK`: Request succeeded.
- `201 Created`: Form document uploaded and queued successfully.
- `202 Accepted`: Asynchronous pipeline processing initiated.
- `400 Bad Request`: Payload validation or image corruption failure.
- `404 Not Found`: Form ID or template ID does not exist.
- `422 Unprocessable Entity`: Field validation or segmentation failure.
- `500 Internal Server Error`: Unhandled pipeline exception.

---

## 2. Endpoints Specification

### 2.1 Health & Diagnostics

#### `GET /api/v1/health`
Returns the status of the service, database connectivity, and OCR engine availability.

- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "status": "HEALTHY",
    "version": "0.1.0",
    "environment": "development",
    "supported_scripts": ["DEVANAGARI"],
    "dependencies": {
      "database": "CONNECTED",
      "opencv": "4.10.0",
      "ocr_engine": "READY"
    }
  }
}
```

---

### 2.2 Form Ingestion & Processing

#### `POST /api/v1/forms/upload`
Uploads a scanned or photographed form image for processing.

- **Content-Type:** `multipart/form-data`
- **Form Parameters:**
  - `file` (binary, required): Image file (PNG, JPG, JPEG, TIFF; max 15MB).
  - `template_id` (string, optional): ID of template layout (defaults to `"standard_devanagari_v1"`).
  - `auto_process` (boolean, optional, default: `true`): If true, triggers processing pipeline immediately.

- **Response `201 Created`**:
```json
{
  "success": true,
  "data": {
    "form_id": "f8a1c3e2-9b04-4c81-872f-65df93a401bc",
    "file_name": "sample_form_hindi_01.jpg",
    "file_size_bytes": 2451000,
    "status": "QUEUED",
    "created_at": "2026-10-16T14:40:00Z"
  }
}
```

---

#### `GET /api/v1/forms/{form_id}/status`
Polls the execution status of a form in the digitization pipeline.

- **Path Parameters:**
  - `form_id` (UUID): Unique form identifier.

- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "form_id": "f8a1c3e2-9b04-4c81-872f-65df93a401bc",
    "status": "PROCESSING",
    "current_stage": "SEGMENTATION",
    "progress_percent": 50,
    "stages_completed": [
      {"stage": "INGESTION", "duration_ms": 45},
      {"stage": "PREPROCESSING", "duration_ms": 310}
    ]
  }
}
```

`status` values: `QUEUED`, `PROCESSING`, `COMPLETED`, `FAILED`.

---

#### `GET /api/v1/forms/{form_id}`
Retrieves complete digitized form data, extracted fields, bounding boxes, confidence metrics, and validation flags.

- **Path Parameters:**
  - `form_id` (UUID): Unique form identifier.

- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "form_id": "f8a1c3e2-9b04-4c81-872f-65df93a401bc",
    "status": "COMPLETED",
    "template_id": "standard_devanagari_v1",
    "image_urls": {
      "original": "/api/v1/forms/f8a1c3e2-9b04-4c81-872f-65df93a401bc/image/original",
      "preprocessed": "/api/v1/forms/f8a1c3e2-9b04-4c81-872f-65df93a401bc/image/preprocessed"
    },
    "requires_review": false,
    "fields": {
      "applicant_name": {
        "field_type": "NAME",
        "raw_text": "राकेश कुमार शर्मा",
        "normalized_value": "राकेश कुमार शर्मा",
        "confidence": 0.94,
        "is_valid": true,
        "validation_issues": [],
        "bounding_box": {
          "x": 340,
          "y": 520,
          "width": 860,
          "height": 110
        },
        "is_manually_edited": false
      },
      "submission_date": {
        "field_type": "DATE",
        "raw_text": "१५/०८/२०२४",
        "normalized_value": "2024-08-15",
        "confidence": 0.98,
        "is_valid": true,
        "validation_issues": [],
        "bounding_box": {
          "x": 1420,
          "y": 520,
          "width": 380,
          "height": 110
        },
        "is_manually_edited": false
      },
      "declared_amount": {
        "field_type": "AMOUNT",
        "raw_text": "२५,०००",
        "normalized_value": 25000.0,
        "confidence": 0.91,
        "is_valid": true,
        "validation_issues": [],
        "bounding_box": {
          "x": 340,
          "y": 780,
          "width": 540,
          "height": 110
        },
        "is_manually_edited": false
      }
    },
    "metadata": {
      "processing_time_total_ms": 1120,
      "deskew_angle_degrees": -1.45,
      "created_at": "2026-10-16T14:40:00Z",
      "updated_at": "2026-10-16T14:40:02Z"
    }
  }
}
```

---

### 2.3 Human-in-the-Loop Field Correction

#### `PATCH /api/v1/forms/{form_id}/fields`
Allows a human reviewer to correct any machine-extracted field value.

- **Path Parameters:**
  - `form_id` (UUID): Unique form identifier.
- **Request Body:**
```json
{
  "corrections": [
    {
      "field_key": "applicant_name",
      "corrected_value": "राकेश कुमार वर्मा",
      "reason": "Character recognition misread surname"
    }
  ]
}
```

- **Response `200 OK`**:
```json
{
  "success": true,
  "data": {
    "form_id": "f8a1c3e2-9b04-4c81-872f-65df93a401bc",
    "updated_field": "applicant_name",
    "normalized_value": "राकेश कुमार वर्मा",
    "is_manually_edited": true,
    "updated_at": "2026-10-16T14:42:15Z"
  }
}
```

---

### 2.4 Data Export

#### `GET /api/v1/forms/{form_id}/export?format={json|csv}`
Exports the finalized digitized form record.

- **Query Parameters:**
  - `format` (string, optional, default: `"json"`): Export format (`"json"` or `"csv"`).

- **Response `200 OK`:**
  - If `json`: Returns formatted JSON payload.
  - If `csv`: Returns `text/csv` attachment with headers `form_id,applicant_name,submission_date,declared_amount,status,verified`.
