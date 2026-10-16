# Implementation Checklist Across All Project Phases

This document tracks implementation progress across all phases of the **Handwritten Indic-Script Form Digitiser** project.

---

## Phase 1: Repository Foundation & Architectural Blueprint (Current Phase)
- [x] Inspect workspace and initialize Git repository safely.
- [x] Establish modular directory tree (`frontend/`, `backend/app/*`, `docs/`, `data/*`).
- [x] Configure comprehensive multi-stack `.gitignore` (Python, Node.js, ML weights, local SQLite, uploads, secrets).
- [x] Author system architecture document defining module responsibilities and data flow (`docs/architecture.md`).
- [x] Author future-phase implementation checklist (`docs/implementation_checklist.md`).
- [x] Document high-level REST API contracts (`docs/api_contract.md`).
- [x] Inspect local runtime environments (Python 3.14.5, Node.js v24.14.0) and document compatibility analysis and mitigation steps.
- [x] Author comprehensive root and project `README.md`.

---

## Phase 2: Form Template Design, Ground Truth & Dataset Collection
- [ ] Define standardized single-page printed form template (A4 standard: 210mm x 297mm) with clear fiducial registration markers at the corners.
- [ ] Designate fixed regions of interest (ROIs) for three primary fields:
  - `applicant_name` (Handwritten Devanagari text)
  - `submission_date` (Handwritten date in Devanagari or Arabic digits)
  - `declared_amount` (Handwritten monetary figure in Devanagari or Arabic numerals)
- [ ] Implement synthetic data generator script (`backend/scripts/generate_synthetic_forms.py`) to produce diverse test forms with varying fonts, handwriting styles, skew angles, and artificial sensor noise.
- [ ] Establish standardized JSON annotation schema (`backend/data/annotations/`) linking form images to bounding box coordinates and ground truth transcriptions.
- [ ] Collect a validation dataset of real scanned/photographed Devanagari handwritten forms.

---

## Phase 3: Classical Image Preprocessing & Geometric Normalization
- [ ] Implement robust image ingestion supporting PNG, JPEG, TIFF buffers via OpenCV (`cv2.imdecode`).
- [ ] Implement adaptive binarization algorithms (Otsu's thresholding, Sauvola adaptive binarization) to mitigate shadows, folds, and ink bleeding.
- [ ] Implement document skew detection (Hough line accumulation / Radon transform) and affine rotation correction.
- [ ] Implement corner fiducial marker detection and four-point perspective transformation to register uploaded documents against the canonical reference template.
- [ ] Build visual debugging export utility to inspect intermediate preprocessing stages in `backend/data/processed/`.
- [ ] Author unit tests in `backend/tests/test_preprocessing.py` verifying deskewing and perspective warp fidelity.

---

## Phase 4: Layout Analysis & Field Segmentation Engine
- [ ] Build anchor-based field segmenter referencing canonical template coordinates.
- [ ] Implement sub-image ROI extraction for `Name`, `Date`, and `Amount` fields.
- [ ] Implement Devanagari Shirorekha (headline) detection using horizontal projection profiling.
- [ ] Implement word/character-level segmentation heuristics where discrete character inputs are required.
- [ ] Add ROI boundary padding and aspect-ratio normalization for downstream model inference.
- [ ] Author unit tests in `backend/tests/test_segmentation.py` testing bounding-box precision and IoU on benchmark forms.

---

## Phase 5: Handwritten Devanagari Recognition (OCR) Engine
- [ ] Define `BaseOCREngine` abstract base class for pluggable OCR backends.
- [ ] Establish Devanagari character mapping dictionary:
  - Vowels (*Swar*) and Consonants (*Vyanjan*)
  - Dependent vowel signs (*Matras*) and Halant
  - Conjunct characters (*Samyuktaksar*)
  - Devanagari numerals (`०, १, २, ३, ४, ५, ६, ७, ८, ९`)
- [ ] Integrate deep learning sequence model (CRNN + CTC loss / PyTorch OCR model) optimized for Devanagari handwriting.
- [ ] Implement inference wrapper returning recognized Unicode string and token-level / character-level confidence scores.
- [ ] Author unit tests in `backend/tests/test_recognition.py` verifying transcription output on known cropped field samples.

---

## Phase 6: Post-OCR Semantic Validation & Normalization
- [ ] Implement Devanagari numeral normalizer converting Indic digits (`०-९`) to standard ASCII digits (`0-9`).
- [ ] Implement date parsing and validation engine (`backend/app/validation/date_validator.py`):
  - Support DD/MM/YYYY, DD-MM-YYYY, and regional variants.
  - Verify calendar logic (days per month, leap year, date bounds).
- [ ] Implement amount parsing and validation engine (`backend/app/validation/amount_validator.py`):
  - Strip currency symbols (`₹`, `रु`).
  - Validate numeric boundaries, decimal points, and cross-check against written words if present.
- [ ] Implement name sanitization engine (`backend/app/validation/name_validator.py`):
  - Unicode block filtering for Devanagari range (`U+0900` - `U+097F`).
  - Strip punctuation and stray noise strokes.
- [ ] Implement composite confidence scorer determining if human-in-the-loop review is mandatory (`confidence < 0.85` or validation rule failure).
- [ ] Author unit tests in `backend/tests/test_validation.py` testing all normalization and boundary conditions.

---

## Phase 7: Backend FastAPI Service & Persistence Layer
- [ ] Configure FastAPI application factory with CORS middleware, exception handlers, and structured logging.
- [ ] Implement SQLAlchemy ORM models (`FormDocument`, `FormField`, `ProcessingLog`) targeting SQLite.
- [ ] Implement Alembic database migrations or declarative metadata creation.
- [ ] Implement API endpoints (`/api/v1/forms/upload`, `/api/v1/forms/{id}`, `/api/v1/forms/{id}/fields`, `/api/v1/health`).
- [ ] Implement background processing pipeline trigger (FastAPI `BackgroundTasks` or async job queue).
- [ ] Author end-to-end integration tests using `pytest` and FastAPI `TestClient`.

---

## Phase 8: Modern React Frontend (Human-in-the-Loop Workspace)
- [ ] Initialize React 19 + TypeScript + Vite frontend inside `frontend/`.
- [ ] Configure Tailwind CSS and design system primitives.
- [ ] Implement drag-and-drop document upload interface with client-side file validation and progress feedback.
- [ ] Implement interactive canvas viewer displaying:
  - Preprocessed document preview.
  - Visual bounding boxes for `Name`, `Date`, and `Amount` fields.
  - Color-coded confidence highlights (Green: high confidence, Yellow: warning, Red: error/low confidence).
- [ ] Implement structured verification sidebar allowing operators to review, edit, and approve extracted values.
- [ ] Implement export functionality (download as JSON or CSV).
- [ ] Add unit and component tests (Vitest / React Testing Library).

---

## Phase 9: Evaluation Suite, Error Analysis & Performance Tuning
- [ ] Implement automated evaluation metrics in `backend/app/evaluation/`:
  - Character Error Rate (CER) using Levenshtein distance.
  - Word Error Rate (WER).
  - Field Extraction Accuracy (FEA).
  - Segmentation IoU.
- [ ] Implement benchmark runner script (`backend/scripts/run_benchmarks.py`) testing against annotated validation datasets.
- [ ] Profile pipeline latency (preprocessing vs. segmentation vs. OCR vs. validation) and optimize bottlenecks.
- [ ] Generate comprehensive evaluation report and error confusion matrix.

---

## Phase 10: Multi-Script Extensibility & Variable Layout Generalization
- [ ] Abstract template registration to load external JSON schema layouts.
- [ ] Implement key-value anchor matching for semi-structured / variable form layouts.
- [ ] Add character dictionary and recognition models for additional Indic scripts (Bengali, Gujarati, Tamil).
- [ ] Package system for deployment (Docker containerization, environment profiles).
