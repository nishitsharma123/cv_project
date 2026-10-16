"""Tesseract OCR adapter for Hindi / Devanagari handwriting.

Availability contract
---------------------
- Checks for the ``tesseract`` binary in PATH using ``shutil.which``.
- When not installed: returns ENGINE_UNAVAILABLE with setup instructions.
- When installed: runs PSM 7 (single line) with language data ``hin``.
- Explicitly documents that Tesseract was trained on printed/typeset text
  and degrades significantly on cursive or handwritten Devanagari.

Confidence reporting
--------------------
Tesseract outputs a per-word confidence via ``--print-results`` but the
standard ``-c tessedit_char_blacklist`` / ``outputbase stdout`` pipeline
does not expose per-character confidence directly.  We use the mean of the
word-level ``conf`` values from the TSV output when available; otherwise we
report 0.0 and mark ``is_confidence_calibrated=False``.

These confidence values are raw Tesseract internal scores (0-100 integer
scale internally), mapped to [0.0, 1.0] for schema consistency.  They are
NOT calibrated posterior probabilities.
"""

import logging
import shutil
import subprocess
import time
from typing import List, Optional

import numpy as np

from app.recognition.base import BaseOCREngine
from app.schemas.recognition import OCRResultData, RecognitionStatus

logger = logging.getLogger("app.recognition.adapters.tesseract")

_TESSERACT_BINARY = "tesseract"
_TESSERACT_LANG = "hin"
_PSM = "7"   # Treat image as a single text line


class TesseractAdapter(BaseOCREngine):
    """OCR adapter wrapping the Tesseract 5 CLI with Hindi language data.

    IMPORTANT: Tesseract was trained primarily on printed/typeset fonts.
    Accuracy on handwritten Devanagari will be substantially lower than on
    printed text.  Results from this adapter should be treated as a baseline
    reference, not a performance target.
    """

    engine_id = "tesseract"
    display_name = "Tesseract 5 (Hindi/Devanagari — printed baseline)"
    supported_scripts: List[str] = ["Devanagari"]

    _SETUP = (
        "Install Tesseract 5+: https://tesseract-ocr.github.io/tessdoc/Installation.html\n"
        "Then install Hindi language data:\n"
        "  Linux/macOS: sudo apt install tesseract-ocr-hin  /  brew install tesseract-lang\n"
        "  Windows: download hin.traineddata from https://github.com/tesseract-ocr/tessdata\n"
        "           and place it in Tesseract's tessdata folder."
    )

    def _do_initialize(self) -> None:
        binary = shutil.which(_TESSERACT_BINARY)
        if binary is None:
            self._initialized = False
            self._unavailability_reason = (
                "The 'tesseract' binary was not found in PATH."
            )
            self._setup_instructions = self._SETUP
            logger.warning("Tesseract not found in PATH; adapter unavailable")
        else:
            self._initialized = True
            self._binary_path: Optional[str] = binary
            # Check hin lang data is present by running a no-op command
            try:
                result = subprocess.run(
                    [binary, "--list-langs"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if _TESSERACT_LANG not in result.stdout and _TESSERACT_LANG not in result.stderr:
                    self._initialized = False
                    self._unavailability_reason = (
                        f"Tesseract found at {binary} but Hindi language data "
                        f"('{_TESSERACT_LANG}') is not installed."
                    )
                    self._setup_instructions = self._SETUP
                    logger.warning(
                        "Tesseract Hindi language data missing; adapter unavailable"
                    )
                else:
                    logger.info(f"Tesseract adapter initialized: binary={binary}")
            except Exception as exc:  # pragma: no cover
                self._initialized = False
                self._unavailability_reason = f"Tesseract availability check failed: {exc}"
                logger.warning("Tesseract availability check error: %s", exc)

    def is_available(self) -> bool:
        return self._initialized

    def recognize(self, crop: np.ndarray, field_id: str, field_type: str) -> OCRResultData:
        """Run Tesseract on a single field crop image."""
        if not self.is_available():
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.ENGINE_UNAVAILABLE,
                warnings=[self._unavailability_reason],
            )

        if crop is None or crop.size == 0:
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.EMPTY_INPUT,
                warnings=["Crop array was empty; cannot run Tesseract"],
            )

        import cv2
        import tempfile
        import os

        t0 = time.perf_counter()

        try:
            # Write crop to a temp PNG file; Tesseract reads from disk
            with tempfile.TemporaryDirectory() as tmpdir:
                input_path = os.path.join(tmpdir, "crop.png")
                output_base = os.path.join(tmpdir, "result")

                # Tesseract works better on greyscale with a white background
                if len(crop.shape) == 3:
                    grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
                else:
                    grey = crop

                # Binarize with Otsu for cleaner Tesseract input
                _, binarized = cv2.threshold(
                    grey, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )

                cv2.imwrite(input_path, binarized)

                cmd = [
                    self._binary_path,           # type: ignore[attr-defined]
                    input_path,
                    output_base,
                    "-l", _TESSERACT_LANG,
                    "--psm", _PSM,
                    "tsv",                        # request TSV output for confidence
                ]

                proc = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    timeout=30,
                )

                elapsed_ms = (time.perf_counter() - t0) * 1000

                if proc.returncode != 0:
                    err_snippet = (proc.stderr or "").strip()[:200]
                    logger.error(
                        "Tesseract exited with code %d for field %s: %s",
                        proc.returncode, field_id, err_snippet,
                    )
                    return OCRResultData(
                        field_id=field_id,
                        field_type=field_type,
                        model_id=self.engine_id,
                        status=RecognitionStatus.FAILED,
                        inference_time_ms=round(elapsed_ms, 3),
                        warnings=[f"Tesseract process failed (exit {proc.returncode})"],
                    )

                # Parse TSV output for text and confidence
                tsv_path = output_base + ".tsv"
                raw_text, confidence = _parse_tesseract_tsv(tsv_path)
                text = _normalize_field_text(raw_text, field_type)

                return OCRResultData(
                    field_id=field_id,
                    field_type=field_type,
                    model_id=self.engine_id,
                    status=RecognitionStatus.SUCCESS,
                    text=text,
                    raw_text=raw_text,
                    confidence=confidence,
                    is_confidence_calibrated=False,
                    inference_time_ms=round(elapsed_ms, 3),
                    warnings=[
                        "Tesseract was trained on printed text; handwriting accuracy may be low."
                    ],
                )

        except subprocess.TimeoutExpired:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.error("Tesseract timed out for field %s", field_id)
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.FAILED,
                inference_time_ms=round(elapsed_ms, 3),
                warnings=["Tesseract inference timed out (30s limit exceeded)"],
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception("Unexpected error in Tesseract adapter for field %s", field_id)
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.FAILED,
                inference_time_ms=round(elapsed_ms, 3),
                warnings=[f"Unexpected Tesseract adapter error: {type(exc).__name__}"],
            )


def _parse_tesseract_tsv(tsv_path: str):
    """Parse Tesseract TSV output; return (text, mean_confidence).

    TSV columns: level page_num block_num par_num line_num word_num
                 left top width height conf text
    Confidence is -1 for non-word rows.
    """
    import csv
    import os

    if not os.path.exists(tsv_path):
        return "", 0.0

    words: List[str] = []
    confidences: List[float] = []

    try:
        with open(tsv_path, encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                conf_str = row.get("conf", "-1").strip()
                try:
                    conf_val = float(conf_str)
                except ValueError:
                    conf_val = -1.0
                word = row.get("text", "").strip()
                if conf_val >= 0 and word:
                    words.append(word)
                    confidences.append(conf_val)
    except Exception as exc:
        logger.warning("Could not parse Tesseract TSV: %s", exc)
        return "", 0.0

    raw_text = " ".join(words).strip()
    mean_conf = (sum(confidences) / len(confidences) / 100.0) if confidences else 0.0
    # Clamp to [0.0, 1.0] in case Tesseract ever emits out-of-range values
    mean_conf = max(0.0, min(1.0, mean_conf))
    return raw_text, mean_conf


def _normalize_field_text(raw: str, field_type: str) -> str:
    """Apply lightweight field-type-aware normalization to raw OCR text.

    This normalizes obvious OCR artifacts without rewriting the prediction.
    """
    text = raw.strip()
    if field_type.upper() == "AMOUNT":
        # Remove stray spaces inside numbers; keep digits, dots, commas
        import re
        text = re.sub(r"\s+", "", text)
    elif field_type.upper() == "DATE":
        # Collapse multiple spaces to single
        import re
        text = re.sub(r"\s+", " ", text)
    return text
