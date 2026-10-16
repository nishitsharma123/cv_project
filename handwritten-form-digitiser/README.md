# Handwritten Indic-Script Form Digitiser

An end-to-end computer vision and optical character recognition (OCR) platform designed to convert physical, handwritten Devanagari/Hindi form fields into validated, structured digital data.

---

## 1. Project Objective

In many administrative and public sector workflows across India, official forms are completed by hand in regional Indic scripts. Manually transcribing these documents is error-prone, labor-intensive, and slow.

This project delivers an automated, high-precision digitization system specifically engineered for Indic handwriting:
- **Primary Script Focus:** Devanagari (Hindi language).
- **Core Form Fields:** Handwritten **Applicant Name**, **Date**, and **Declared Amount** fields on fixed printed form templates.
- **Human-in-the-Loop (HITL):** Real-time confidence scoring and interactive bounding-box review interface for human verification and corrections.
- **Architectural Extensibility:** Modular design facilitating future expansion to other Indic scripts (Bengali, Tamil, Gujarati) and dynamic/variable form layouts.

---

## 2. Architecture Overview

The system is designed with a clean, decoupled architecture:

```
                            +--------------------------+
                            |       React + Vite       |
                            |   Tailwind CSS Frontend  |
                            +------------+-------------+
                                         |  REST API / Multipart
                                         v
                            +--------------------------+
                            |     FastAPI Backend      |
                            +------------+-------------+
                                         |
     +-------------------+---------------+-------------------+-------------------+
     |                   |                                   |                   |
     v                   v                                   v                   v
+----+---------+   +-----+--------+                    +-----+--------+    +-----+--------+
| Preprocess   |   | Segmentation |                    | Recognition  |    |  Validation  |
| OpenCV/NumPy |   | Anchor & ROI |                    | Devanagari   |    | Rules Engine |
| Deskew/Warp  |   | Slicing      |                    | OCR / CRNN   |    | Numerals/Date|
+--------------+   +--------------+                    +--------------+    +--------------+
                                                                                 |
                                                                                 v
                                                                       +---------+----+
                                                                       | Persistence  |
                                                                       | SQLite /     |
                                                                       | SQLAlchemy   |
                                                                       +--------------+
```

- **Frontend**: React 19, Vite, TypeScript, Tailwind CSS, Lucide icons.
- **Backend API**: Python 3, FastAPI, Pydantic V2, Uvicorn.
- **Image Processing**: OpenCV (`opencv-python`) and NumPy for binarization, deskewing, and perspective rectification.
- **OCR Engine**: Sequence recognition model (CRNN / CTC) optimized for Devanagari script and Indic numerals.
- **Persistence**: SQLite with SQLAlchemy ORM.
- **Testing**: `pytest` for backend unit and integration testing; `vitest` for frontend components.

---

## 3. Directory Layout

```
handwritten-form-digitiser/
├── frontend/               # React + Vite + Tailwind CSS web interface
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI REST endpoints and route handlers
│   │   ├── core/           # Configuration, database session, logging, constants
│   │   ├── schemas/        # Pydantic data validation and transfer schemas
│   │   ├── preprocessing/  # OpenCV image filtering, binarization, deskewing
│   │   ├── segmentation/   # Anchor detection, layout analysis, field ROI extraction
│   │   ├── recognition/    # Devanagari character and word OCR inference
│   │   ├── validation/     # Domain validation (dates, Indic numerals, sanitization)
│   │   ├── pipeline/       # Pipeline orchestrator managing execution flow
│   │   └── evaluation/     # CER, WER, and field accuracy benchmark metrics
│   ├── tests/              # Automated unit and integration test suite
│   ├── data/
│   │   ├── samples/        # Form templates and sample inputs (.gitkeep)
│   │   ├── annotations/    # Ground-truth bounding boxes and labels (.gitkeep)
│   │   └── processed/      # Intermediate preprocessed and segmented artifacts (.gitkeep)
│   └── scripts/            # Dataset generation, synthetic forms, and benchmark scripts
├── docs/
│   ├── architecture.md             # In-depth module responsibilities and data flow
│   ├── implementation_checklist.md # Phase-by-phase implementation tracker
│   └── api_contract.md             # REST API specifications and schemas
├── .gitignore              # Multi-tier ignore rules (Python, Node, weights, databases)
└── README.md               # Project documentation
```

---

## 4. Setup & Installation Instructions

> *Note: Setup instructions will be populated and verified as implementation proceeds through subsequent phases.*

### 4.1 Prerequisites
- **Git** (version 2.30+)
- **Python**: Python 3.11 or 3.12 strongly recommended for OpenCV and PyTorch binary wheel compatibility (see [Environment & Compatibility Report](#6-environment--compatibility-report)).
- **Node.js**: v20+ LTS or v24+ with npm.

### 4.2 Backend Setup (Planned for Phase 2+)
```bash
# 1. Navigate to the backend directory
cd handwritten-form-digitiser/backend

# 2. Create a virtual environment using Python 3.11/3.12
py -3.11 -m venv venv

# 3. Activate the virtual environment
# Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# Linux/macOS:
source venv/bin/activate

# 4. Install backend dependencies (requirements.txt to be added in Phase 2)
pip install -r requirements.txt

# 5. Run development server (to be activated in Phase 7)
uvicorn app.api.main:app --reload --port 8000
```

### 4.3 Frontend Setup (Planned for Phase 8)
```bash
# 1. Navigate to the frontend directory
cd handwritten-form-digitiser/frontend

# 2. Install dependencies (package.json to be added in Phase 8)
npm install

# 3. Launch Vite development server
npm run dev
```

### 4.4 Running Tests
```bash
# Backend test suite (pytest)
pytest backend/tests/ -v

# Evaluation suite (benchmark run)
python backend/scripts/run_benchmarks.py
```

---

## 5. Implementation Phases Roadmap

- [x] **Phase 1: Repository Foundation & Architectural Blueprint**
  - Git repository initialization, directory structure, `.gitignore`, architecture documentation, implementation checklist, API contracts, environment audit.
- [ ] **Phase 2: Form Template Design, Ground Truth & Dataset Collection**
  - Canonical printed template design, synthetic form generator, ground-truth annotation format.
- [ ] **Phase 3: Classical Image Preprocessing & Geometric Normalization**
  - Adaptive binarization, Radon/Hough deskewing, four-point perspective warp.
- [ ] **Phase 4: Layout Analysis & Field Segmentation Engine**
  - Anchor detection, Name/Date/Amount ROI extraction, Shirorekha detection.
- [ ] **Phase 5: Handwritten Devanagari Recognition (OCR) Engine**
  - Character dictionary, sequence recognition model (CRNN + CTC), confidence scorer.
- [ ] **Phase 6: Post-OCR Semantic Validation & Normalization**
  - Indic numeral mapping (`०-९` $\rightarrow$ `0-9`), date parsing, amount bounds, unicode cleaning.
- [ ] **Phase 7: Backend FastAPI Service & Persistence Layer**
  - REST endpoints, SQLite/SQLAlchemy schema, background task processing.
- [ ] **Phase 8: Modern React Frontend (HITL Workspace)**
  - Drag-and-drop upload, bounding box canvas overlay, side-by-side verification editor, CSV/JSON export.
- [ ] **Phase 9: Evaluation Suite, Error Analysis & Performance Tuning**
  - CER, WER, and field extraction accuracy benchmarks on test sets.
- [ ] **Phase 10: Multi-Script Extensibility & Variable Layout Generalization**
  - Additional Indic scripts (Bengali, Tamil) and dynamic layout matching.

---

## 6. Environment & Compatibility Report

An inspection of the local workstation environment reveals:
- **Node.js**: `v24.14.0` | **npm**: `11.9.0` (fully compatible with Vite, React, Tailwind CSS).
- **Python**: `Python 3.14.5` (64-bit).
  - *Compatibility Advisory*: Python 3.14 is an ultra-recent release. Pre-compiled binary wheels for packages such as `opencv-python` and `torch` typically lag behind the newest Python minor releases on Windows.
  - *Actionable Mitigation*: When setting up the backend virtual environment in Phase 2, install Python 3.11 or Python 3.12 (via `py -3.11` or `uv`) to guarantee frictionless dependency resolution without requiring manual MSVC C++ compilation.
