#!/usr/bin/env python3
"""Benchmark script for handwritten Devanagari OCR engines.

Usage
-----
  # From the backend/ directory with the virtual environment active:
  python scripts/run_benchmarks.py --engine tesseract
  python scripts/run_benchmarks.py --engine crnn
  python scripts/run_benchmarks.py --engine all
  python scripts/run_benchmarks.py --engine tesseract --ground-truth data/annotations/benchmark_ground_truth.json

What this script does
---------------------
1. Loads ground-truth annotations from a JSON file.
2. Loads corresponding form images from a configurable image directory.
3. Runs the full preprocessing and segmentation pipeline on each image.
4. Passes the extracted field crops to the selected OCR engine.
5. Computes CER, WER, exact match rate, and per-field breakdowns.
6. Prints a structured benchmark report and optionally saves JSON output.

What this script does NOT do
-----------------------------
- It does NOT fabricate recognition results.
- It does NOT hardcode expected text as the model prediction.
- It does NOT run inference with the mock adapter (mock is excluded from benchmarks).
- If no real images or annotations are present it exits cleanly with a clear message.

Report format
-------------
The report is printed to stdout in a human-readable table format.
A machine-readable JSON report is optionally saved with --output.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

# Ensure the backend/ root is on sys.path regardless of invocation directory
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

import numpy as np

from app.evaluation.metrics import (
    BenchmarkReport,
    SampleResult,
    compute_cer,
    compute_exact_match,
    compute_wer,
)
from app.preprocessing.service import ImagePreprocessingService
from app.recognition.service import RecognitionService
from app.segmentation.service import SegmentationService
from app.segmentation.template_manager import TemplateManager
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("benchmark")

_EXCLUDABLE_ENGINES = {"mock"}   # Never benchmark the mock adapter


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="OCR benchmark for handwritten Devanagari form fields",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--engine",
        default="tesseract",
        help="Engine id to benchmark: 'tesseract', 'crnn', or 'all' (default: tesseract)",
    )
    parser.add_argument(
        "--ground-truth",
        default="data/annotations/benchmark_ground_truth.json",
        help="Path to benchmark ground-truth JSON (default: data/annotations/benchmark_ground_truth.json)",
    )
    parser.add_argument(
        "--images-dir",
        default="data/benchmark_images",
        help="Directory containing source form images (one per sample_id, e.g. syn_001.jpg)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to save machine-readable JSON benchmark report",
    )
    parser.add_argument(
        "--template-id",
        default="devanagari_synthetic_v1",
        help="Template id to use for segmentation (default: devanagari_synthetic_v1)",
    )
    parser.add_argument(
        "--strategy",
        default="fixed_template",
        help="Segmentation strategy: fixed_template, contour, or hybrid (default: fixed_template)",
    )
    return parser.parse_args()


def load_ground_truth(path: str) -> dict:
    """Load and return the ground-truth annotation file."""
    gt_path = Path(path)
    if not gt_path.exists():
        logger.error("Ground-truth file not found: %s", gt_path.resolve())
        sys.exit(1)
    with open(gt_path, encoding="utf-8-sig") as fh:
        return json.load(fh)


def find_image(images_dir: str, sample_id: str) -> Optional[Path]:
    """Return the path of an image file matching sample_id in images_dir."""
    images_path = Path(images_dir)
    if not images_path.exists():
        return None
    for ext in (".jpg", ".jpeg", ".png", ".tiff", ".tif"):
        candidate = images_path / f"{sample_id}{ext}"
        if candidate.exists():
            return candidate
    return None


def run_benchmark(
    engine_id: str,
    annotations: List[dict],
    images_dir: str,
    template_id: str,
    strategy: str,
) -> BenchmarkReport:
    """Execute the benchmark pipeline for one engine."""
    settings = get_settings()
    rec_service = RecognitionService()

    strat_clean = (strategy or "hybrid").lower().strip()
    if strat_clean in ("fixed_template", "fixed-template"):
        strat_clean = "fixed"

    sample_results: List[SampleResult] = []
    warnings: List[str] = []

    for ann in annotations:
        sample_id = ann["sample_id"]
        field_id = ann["field_id"]
        field_type = ann["field_type"]
        reference = ann["reference_text"]
        source = ann.get("source", "unknown")

        if source == "synthetic_fixture":
            msg = (
                f"Sample '{sample_id}' is a synthetic fixture annotation; "
                f"skipping — no real image to benchmark against."
            )
            logger.warning(msg)
            warnings.append(msg)
            continue

        image_path = find_image(images_dir, sample_id)
        if image_path is None:
            msg = (
                f"Image for sample '{sample_id}' not found in '{images_dir}'. "
                "Skipping."
            )
            logger.warning(msg)
            warnings.append(msg)
            continue

        logger.info("Benchmarking sample '%s' field '%s' with engine '%s'",
                    sample_id, field_id, engine_id)

        try:
            image_bytes = image_path.read_bytes()

            # Run segmentation to obtain field crops
            seg_result = SegmentationService.process_and_segment(
                image_bytes=image_bytes,
                filename=image_path.name,
                template_id=template_id,
                strategy_name=strat_clean,
                settings=settings,
            )

            crop = seg_result.field_crops.get(field_id)
            if crop is None or crop.size == 0:
                msg = f"Empty crop or field '{field_id}' not found in segmentation output for sample '{sample_id}'"
                logger.warning(msg)
                warnings.append(msg)
                sample_results.append(SampleResult(
                    sample_id=sample_id,
                    field_id=field_id,
                    field_type=field_type,
                    engine_id=engine_id,
                    hypothesis="",
                    reference=reference,
                    cer=1.0,
                    wer=1.0,
                    exact_match=False,
                    inference_time_ms=0.0,
                    ocr_status="EMPTY_INPUT",
                    warnings=[msg],
                ))
                continue

            ocr_result = rec_service.recognize_field(crop, field_id, field_type, engine_id)

            cer = compute_cer(ocr_result.text, reference)
            wer = compute_wer(ocr_result.text, reference)
            exact = compute_exact_match(ocr_result.text, reference)

            sample_results.append(SampleResult(
                sample_id=sample_id,
                field_id=field_id,
                field_type=field_type,
                engine_id=engine_id,
                hypothesis=ocr_result.text,
                reference=reference,
                cer=round(cer, 4),
                wer=round(wer, 4),
                exact_match=exact,
                inference_time_ms=ocr_result.inference_time_ms,
                ocr_status=ocr_result.status.value,
                warnings=ocr_result.warnings,
            ))

        except Exception as exc:
            logger.exception("Unexpected error for sample '%s': %s", sample_id, exc)
            warnings.append(f"Sample '{sample_id}' failed with unexpected error: {type(exc).__name__}")

    return BenchmarkReport.from_samples(engine_id, sample_results, warnings=warnings)


def print_report(report: BenchmarkReport) -> None:
    """Print a human-readable benchmark report to stdout."""
    print()
    print("=" * 70)
    print(f"  BENCHMARK REPORT — Engine: {report.engine_id}")
    print("=" * 70)
    print(f"  Total samples:       {report.total_samples}")
    print(f"  Evaluated:           {report.evaluated_samples}")
    print(f"  Skipped:             {report.skipped_samples}")
    print()
    if report.evaluated_samples > 0:
        print(f"  Mean CER:            {report.mean_cer:.4f}")
        print(f"  Mean WER:            {report.mean_wer:.4f}")
        print(f"  Exact match rate:    {report.exact_match_rate:.4f}")
        print(f"  Mean inference (ms): {report.mean_inference_time_ms:.1f}")
        print()
        if report.per_field_metrics:
            print("  Per-field breakdown:")
            print(f"    {'Field':<22} {'Count':>5} {'CER':>7} {'WER':>7} {'Exact%':>8} {'ms':>7}")
            print("    " + "-" * 58)
            for fid, m in sorted(report.per_field_metrics.items()):
                print(
                    f"    {fid:<22} {int(m['count']):>5} "
                    f"{m['cer']:>7.4f} {m['wer']:>7.4f} "
                    f"{m['exact_match_rate']*100:>7.1f}% "
                    f"{m['mean_inference_time_ms']:>7.1f}"
                )
    else:
        print("  No samples were evaluated.")
        print()
        print("  This is expected if:")
        print("    - All annotations reference synthetic fixtures (no real images)")
        print("    - Real images have not yet been placed in the images directory")
        print()
        print("  To run a real benchmark:")
        print("    1. Collect handwritten Devanagari form images")
        print("    2. Add ground-truth text annotations to:")
        print("       data/annotations/benchmark_ground_truth.json")
        print("       (set 'source' to a value other than 'synthetic_fixture')")
        print("    3. Place the images in: data/benchmark_images/<sample_id>.jpg")
        print("    4. Re-run this script")

    if report.warnings:
        print()
        print("  Warnings:")
        for w in report.warnings:
            print(f"    - {w}")

    print("=" * 70)
    print()


def main() -> None:
    args = parse_args()

    gt = load_ground_truth(args.ground_truth)
    annotations: List[dict] = gt.get("annotations", [])

    if not annotations:
        logger.error("No annotations found in ground-truth file.")
        sys.exit(1)

    engine_ids: List[str] = []
    if args.engine.lower() == "all":
        rec_service = RecognitionService()
        engine_ids = [
            e.engine_id
            for e in rec_service.list_engines()
            if e.engine_id not in _EXCLUDABLE_ENGINES
        ]
    else:
        engine_ids = [args.engine]

    reports: List[BenchmarkReport] = []

    for engine_id in engine_ids:
        logger.info("Running benchmark for engine: %s", engine_id)
        report = run_benchmark(
            engine_id=engine_id,
            annotations=annotations,
            images_dir=args.images_dir,
            template_id=args.template_id,
            strategy=args.strategy,
        )
        print_report(report)
        reports.append(report)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        serialized = []
        for r in reports:
            d = {
                "engine_id": r.engine_id,
                "total_samples": r.total_samples,
                "evaluated_samples": r.evaluated_samples,
                "skipped_samples": r.skipped_samples,
                "mean_cer": r.mean_cer,
                "mean_wer": r.mean_wer,
                "exact_match_rate": r.exact_match_rate,
                "mean_inference_time_ms": r.mean_inference_time_ms,
                "per_field_metrics": r.per_field_metrics,
                "warnings": r.warnings,
                "samples": [
                    {
                        "sample_id": s.sample_id,
                        "field_id": s.field_id,
                        "field_type": s.field_type,
                        "hypothesis": s.hypothesis,
                        "reference": s.reference,
                        "cer": s.cer,
                        "wer": s.wer,
                        "exact_match": s.exact_match,
                        "inference_time_ms": s.inference_time_ms,
                        "ocr_status": s.ocr_status,
                        "warnings": s.warnings,
                    }
                    for s in r.samples
                ],
            }
            serialized.append(d)

        with open(output_path, "w", encoding="utf-8") as fh:
            json.dump(serialized, fh, ensure_ascii=False, indent=2)

        logger.info("Benchmark report saved to: %s", output_path.resolve())


if __name__ == "__main__":
    main()
