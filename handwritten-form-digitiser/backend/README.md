# Handwritten Indic-Script Form Digitiser - Backend Service

FastAPI-powered backend foundation for handwritten Devanagari form field digitization.

---

## 1. Architectural Highlights

- **Application Factory Pattern**: `create_app(settings)` creates testable, modular application instances with isolated configurations.
- **Pydantic Settings**: Centralized configuration management with automatic `.env` loading, type validation, and production safety guards.
- **Unified Error Responses**: Every error (400, 404, 405, 422, 500) returns a consistent JSON envelope:
  ```json
  {
    "success": false,
    "error": {
      "code": "ERROR_CODE",
      "message": "Human-readable explanation",
      "details": []
    },
    "timestamp": "2026-10-16T14:40:00Z"
  }
  ```
- **Privacy-Preserving Logging**: Custom filters automatically redact raw binary image buffers, base64 strings, and sensitive payload strings.
- **Zero Stack Trace Leaks**: Unhandled 500 exceptions log tracebacks internally while serving safe, sanitized messages to external clients.
- **Strict CORS & Documentation Controls**: CORS is restricted to declared origins; `/docs` and `/openapi.json` are active in development and automatically suppressed in production.

---

## 2. Windows PowerShell Setup Guide

Follow these steps from Windows PowerShell (`pwsh` or `powershell.exe`):

### Step 2.1: Navigate to the Backend Directory
```powershell
cd C:\Users\mindg\cv_project\handwritten-form-digitiser\backend
```

### Step 2.2: Create and Activate Virtual Environment
```powershell
# If script execution is restricted on your machine, allow it for the current process:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process

# Create a virtual environment (named .venv or venv)
python -m venv venv

# Activate the virtual environment
.\venv\Scripts\Activate.ps1
```
*(When activated, your prompt will show `(venv)`).*

### Step 2.3: Upgrade pip and Install Dependencies
```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Step 2.4: Initialize Environment File
```powershell
Copy-Item .env.example .env
```
*(Edit `.env` if you need custom origins, ports, or logging levels).*

---

## 3. Running the Development Server

Start the Uvicorn ASGI server with hot reloading enabled:

```powershell
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Once running, access:
- **Service Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **Interactive Swagger UI**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **ReDoc Documentation**: [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)
- **OpenAPI JSON Spec**: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## 4. Running the Automated Test Suite

Run pytest with verbose output:

```powershell
# Run the entire test suite
python -m pytest tests/ -v

# Run OCR and benchmark tests
python -m pytest tests/test_recognition.py -v

# Run live verification scripts (spawns background uvicorn test instances)
python scripts/verify_preprocess.py
python scripts/verify_segmentation.py
python scripts/verify_recognition.py

# Run benchmark evaluation CLI
python scripts/run_benchmarks.py --engine tesseract
```

---

## 5. Backend Directory Structure

```text
backend/
├── app/
│   ├── api/
│   │   ├── health.py          # GET /api/health and GET /api/v1/health
│   │   ├── preprocessing.py   # POST /api/preprocess
│   │   ├── segmentation.py    # POST /api/segment, GET /api/templates
│   │   └── recognition.py     # POST /api/recognize, GET /api/recognize/engines
│   ├── core/
│   │   ├── config.py          # Pydantic Settings & environment validation
│   │   ├── errors.py          # Domain exceptions & centralized error handlers
│   │   └── logging.py         # Structured logging & PII/buffer redaction filter
│   ├── schemas/
│   │   ├── common.py          # Success and Error response envelopes
│   │   ├── health.py          # Health check response schemas
│   │   ├── preprocessing.py   # Image upload & preprocessing schemas
│   │   ├── segmentation.py    # Field detection & layout schemas
│   │   └── recognition.py     # OCR results & capability schemas
│   ├── main.py                # create_app() application factory & ASGI app
│   ├── evaluation/            # CER, WER, and exact match benchmark metrics
│   ├── pipeline/              # Future pipeline orchestrator
│   ├── preprocessing/         # OpenCV deskew, CLAHE, bilateral filter
│   ├── recognition/           # OCR engine adapters (Mock, Tesseract, CRNN)
│   ├── segmentation/          # TemplateManager & layout strategies
│   └── validation/            # Future numeral & semantic validation
├── data/
│   ├── annotations/           # Ground-truth benchmark annotations
│   ├── templates/             # Form layout JSON specifications
│   └── samples/               # Form image samples
├── scripts/
│   ├── verify_preprocess.py   # Live preprocessing test script
│   ├── verify_segmentation.py # Live layout segmentation test script
│   ├── verify_recognition.py  # Live OCR engine test script
│   └── run_benchmarks.py      # Benchmark evaluation harness CLI
├── tests/
│   ├── conftest.py            # Test fixtures & diagnostic routes
│   ├── test_config.py         # Settings & environment safety tests
│   ├── test_cors.py           # CORS headers & origin restriction tests
│   ├── test_docs.py           # /docs and /openapi.json availability tests
│   ├── test_errors.py         # Error envelope tests
│   ├── test_health.py         # Health check endpoint tests
│   ├── test_preprocessing.py  # Preprocessing unit & API tests
│   ├── test_segmentation.py   # Segmentation unit & API tests
│   └── test_recognition.py    # OCR adapters, evaluation metrics & API tests
├── .env.example               # Documented template for local development
├── pyproject.toml             # Pytest configuration and project metadata
├── README.md                  # Backend guide (this document)
└── requirements.txt           # Pinned and constrained dependencies
```

---

## 6. Production Hardening Checklist

When deploying to production environments:
1. Set `ENVIRONMENT="production"`.
2. Ensure `DEBUG=false` (enforced automatically by settings validator).
3. Specify exact origins in `ALLOWED_ORIGINS` (wildcard `*` will raise a configuration error).
4. Interactive docs (`/docs`, `/openapi.json`) are automatically disabled to prevent schema reconnaissance.
5. All 500 errors log tracebacks server-side without leaking implementation details or filesystem paths to clients.
