"""Evaluation metrics for handwritten OCR output.

Implements:
- Character Error Rate (CER): edit distance at character level / reference length
- Word Error Rate (WER): edit distance at word level / reference word count
- Exact field match rate: binary per-field match ignoring case and whitespace
- BenchmarkReport: structured aggregation of per-sample and overall results

None of these functions fabricate recognition output.  They strictly compare
a predicted string against a provided ground-truth annotation.
"""

import unicodedata
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Edit Distance
# ---------------------------------------------------------------------------

def _levenshtein(seq_a: List, seq_b: List) -> int:
    """Compute Levenshtein edit distance between two sequences.

    Uses the standard Wagner-Fischer DP algorithm.
    Time: O(len(a) * len(b)), Space: O(len(b)).
    """
    len_a, len_b = len(seq_a), len(seq_b)
    if len_a == 0:
        return len_b
    if len_b == 0:
        return len_a

    # Two-row rolling array
    prev = list(range(len_b + 1))
    curr = [0] * (len_b + 1)

    for i in range(1, len_a + 1):
        curr[0] = i
        for j in range(1, len_b + 1):
            cost = 0 if seq_a[i - 1] == seq_b[j - 1] else 1
            curr[j] = min(
                curr[j - 1] + 1,       # insertion
                prev[j] + 1,           # deletion
                prev[j - 1] + cost,    # substitution
            )
        prev, curr = curr, prev

    return prev[len_b]


# ---------------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------------

def _normalize_unicode(text: str) -> str:
    """Apply NFC Unicode normalization to handle composed/decomposed Devanagari."""
    return unicodedata.normalize("NFC", text)


def _normalize_for_comparison(text: str) -> str:
    """Strip surrounding whitespace and collapse internal whitespace for comparison."""
    import re
    text = _normalize_unicode(text)
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


# ---------------------------------------------------------------------------
# Public metric functions
# ---------------------------------------------------------------------------

def compute_cer(hypothesis: str, reference: str) -> float:
    """Compute Character Error Rate (CER).

    CER = edit_distance(hyp_chars, ref_chars) / len(ref_chars)

    Returns 0.0 when both strings are empty.
    Returns 1.0 (capped) when reference is empty but hypothesis is not.

    Parameters
    ----------
    hypothesis: Predicted text string from the OCR engine.
    reference:  Ground-truth transcription.

    Notes
    -----
    Both strings are NFC-normalized before comparison.  Whitespace is included
    as a character in the character sequence (consistent with standard CER
    in handwriting recognition literature).
    """
    hyp = list(_normalize_unicode(hypothesis))
    ref = list(_normalize_unicode(reference))

    if len(ref) == 0:
        return 0.0 if len(hyp) == 0 else 1.0

    distance = _levenshtein(hyp, ref)
    return distance / len(ref)


def compute_wer(hypothesis: str, reference: str) -> float:
    """Compute Word Error Rate (WER).

    WER = edit_distance(hyp_words, ref_words) / len(ref_words)

    Returns 0.0 when both strings are empty.
    Returns 1.0 (capped) when reference has no words but hypothesis does.

    Parameters
    ----------
    hypothesis: Predicted text string from the OCR engine.
    reference:  Ground-truth transcription.
    """
    hyp_words = _normalize_for_comparison(hypothesis).split()
    ref_words = _normalize_for_comparison(reference).split()

    if len(ref_words) == 0:
        return 0.0 if len(hyp_words) == 0 else 1.0

    distance = _levenshtein(hyp_words, ref_words)
    return distance / len(ref_words)


def compute_exact_match(hypothesis: str, reference: str) -> bool:
    """Return True iff hypothesis matches reference after normalization.

    Normalization applied: NFC Unicode, strip leading/trailing whitespace,
    collapse internal whitespace, lowercase.  This intentionally ignores
    punctuation differences in amounts (e.g. '1,000' vs '1000') only when
    both reduce to the same normalized string.

    Parameters
    ----------
    hypothesis: Predicted text string.
    reference:  Ground-truth transcription.
    """
    return (
        _normalize_for_comparison(hypothesis).lower()
        == _normalize_for_comparison(reference).lower()
    )


# ---------------------------------------------------------------------------
# Per-sample result
# ---------------------------------------------------------------------------

@dataclass
class SampleResult:
    """Evaluation result for a single annotated form field sample."""

    sample_id: str
    field_id: str
    field_type: str
    engine_id: str
    hypothesis: str
    reference: str
    cer: float
    wer: float
    exact_match: bool
    inference_time_ms: float
    ocr_status: str
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Benchmark report
# ---------------------------------------------------------------------------

@dataclass
class BenchmarkReport:
    """Aggregated evaluation report across all samples and engines."""

    engine_id: str
    total_samples: int
    evaluated_samples: int          # samples where OCR returned SUCCESS
    skipped_samples: int            # samples where OCR returned non-SUCCESS

    # Aggregate metrics (computed only on evaluated samples)
    mean_cer: float
    mean_wer: float
    exact_match_rate: float         # fraction of evaluated samples with exact match
    mean_inference_time_ms: float

    # Per-field aggregated metrics
    per_field_metrics: Dict[str, Dict[str, float]] = field(default_factory=dict)
    """Keys: field_id; Values: dict with keys cer, wer, exact_match_rate, count."""

    # Individual sample results
    samples: List[SampleResult] = field(default_factory=list)

    # Any collection-level warnings
    warnings: List[str] = field(default_factory=list)

    @classmethod
    def from_samples(
        cls,
        engine_id: str,
        sample_results: List[SampleResult],
        warnings: Optional[List[str]] = None,
    ) -> "BenchmarkReport":
        """Construct a BenchmarkReport from a list of SampleResult records."""
        total = len(sample_results)
        evaluated = [s for s in sample_results if s.ocr_status == "SUCCESS"]
        skipped = total - len(evaluated)

        if evaluated:
            mean_cer = sum(s.cer for s in evaluated) / len(evaluated)
            mean_wer = sum(s.wer for s in evaluated) / len(evaluated)
            exact_rate = sum(1 for s in evaluated if s.exact_match) / len(evaluated)
            mean_time = sum(s.inference_time_ms for s in evaluated) / len(evaluated)
        else:
            mean_cer = mean_wer = exact_rate = mean_time = 0.0

        # Aggregate per field
        field_buckets: Dict[str, List[SampleResult]] = {}
        for s in evaluated:
            field_buckets.setdefault(s.field_id, []).append(s)

        per_field: Dict[str, Dict[str, float]] = {}
        for fid, bucket in field_buckets.items():
            per_field[fid] = {
                "count": float(len(bucket)),
                "cer": sum(s.cer for s in bucket) / len(bucket),
                "wer": sum(s.wer for s in bucket) / len(bucket),
                "exact_match_rate": sum(1 for s in bucket if s.exact_match) / len(bucket),
                "mean_inference_time_ms": sum(s.inference_time_ms for s in bucket) / len(bucket),
            }

        return cls(
            engine_id=engine_id,
            total_samples=total,
            evaluated_samples=len(evaluated),
            skipped_samples=skipped,
            mean_cer=round(mean_cer, 4),
            mean_wer=round(mean_wer, 4),
            exact_match_rate=round(exact_rate, 4),
            mean_inference_time_ms=round(mean_time, 3),
            per_field_metrics=per_field,
            samples=sample_results,
            warnings=warnings or [],
        )
