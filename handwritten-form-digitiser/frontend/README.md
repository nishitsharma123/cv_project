# Handwritten Indic-Script Form Digitiser — Frontend

React 18 + Vite + TypeScript + Tailwind CSS workspace for the form digitisation interface.

---

## Prerequisites

| Tool | Minimum version |
|------|----------------|
| Node.js | 20 LTS |
| npm | 9 |
| Python | 3.10 |

The **backend must be running** before you start the frontend.

---

## Quick start

### 1 — Start the backend

```powershell
# From the repository root
cd handwritten-form-digitiser\backend
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The API will be available at `http://127.0.0.1:8000`.  
Interactive docs: `http://127.0.0.1:8000/docs`

---

### 2 — Configure the frontend environment

```powershell
# Windows PowerShell (from the frontend\ directory)
Copy-Item .env.example .env.local
```

The default value (`VITE_API_URL=http://127.0.0.1:8000`) matches the backend started above.  
Edit `.env.local` only when the backend runs on a different host or port.

---

### 3 — Install dependencies and start the dev server

```powershell
# From handwritten-form-digitiser\frontend\
npm install
npm run dev
```

The app is served at **`http://localhost:5173`** with HMR enabled.

---

## Available scripts

| Command | Description |
|---------|-------------|
| `npm run dev` | Start Vite development server |
| `npm run build` | Production build (`dist/`) |
| `npm run preview` | Serve the production build locally |
| `npm test` | Run component tests once (Vitest) |
| `npm run test:watch` | Interactive watch mode |
| `npm run typecheck` | TypeScript type-checking only (no emit) |

---

## Running the tests

```powershell
# From handwritten-form-digitiser\frontend\
npm test
```

Tests use **Vitest** and **Testing Library**.  
The test suite covers:

- `FileUpload` — file validation (size, format, empty), selection callback, remove action
- `ProcessingStatus` — error display with/without code, dismiss button, pipeline step labels, warnings, idle empty state
- `FieldCard` — OCR prediction display, confidence rendering, editable input callback, Edited badge, Confirm/Revert buttons, all review status badge variants
- `EngineSelector` — option listing, unavailable engine "(Not Installed)" suffix, availability hint, onSelectEngine callback, disabled states
- `ReviewSummary` — metric counters, all-confirmed badge, Confirm All button, review-needed badge, export policy notice

No backend is required for the test suite.

---

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `VITE_API_URL` | `http://127.0.0.1:8000` | Backend API base URL (no trailing slash) |

---

## Architecture notes

- **`src/services/api.ts`** — centralised API client; all fetch calls are here.
- **`src/types/api.ts`** — TypeScript interfaces matching the backend JSON contracts.
- **`src/components/`** — presentational components; none contain fetch logic.
- **`src/App.tsx`** — single root state machine orchestrating the digitisation pipeline.
- Object URLs created for file previews are revoked on unmount / file change to avoid memory leaks.
- The frontend never fabricates OCR text; all predictions come from the backend.
- No export button exists — the backend export endpoint (`/api/v1/forms/:id/export`) is planned for Phase 08.

---

## Project phases

| Phase | Status | Description |
|-------|--------|-------------|
| 01 | ✅ Complete | Project scaffold, FastAPI skeleton |
| 02 | ✅ Complete | Image upload validation & preprocessing |
| 03 | ✅ Complete | Field detection & segmentation |
| 04 | ✅ Complete | OCR engine integration |
| 05 | ✅ Complete | Field validation & review flags |
| 06 | — | *(reserved)* |
| 07 | ✅ Complete | React frontend (this package) |
| 08 | 🔜 Planned | Database persistence & export |
