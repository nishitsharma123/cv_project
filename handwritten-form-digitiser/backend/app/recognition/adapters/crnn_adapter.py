"""CRNN-CTC adapter for handwritten Devanagari recognition.

Architecture rationale
-----------------------
CNN + Bidirectional LSTM + CTC-loss is the dominant architecture for
handwritten text recognition at low compute budgets.  The encoder (CNN)
extracts visual features from the image; the BiLSTM sequence model produces
per-time-step character distributions; CTC decoding collapses repeated
characters and blank tokens to yield the final text string.

Model source
------------
This adapter accepts an ONNX checkpoint (.onnx) for CPU-only inference via
``onnxruntime``.  A PyTorch checkpoint (.pt) is also supported as a fallback
when the ``torch`` package is available.

If neither onnxruntime nor torch is installed, the adapter reports
ENGINE_UNAVAILABLE.  If the runtime is present but the weights file is
missing, the adapter reports WEIGHTS_NOT_FOUND.

Character set
-------------
The adapter loads a companion character vocabulary file (vocab.txt) expected
alongside the weights file.  Each line of vocab.txt is one UTF-8 Devanagari
character or symbol.  Line N corresponds to CTC label N (0 is reserved for
the blank label).

Absence of a suitable pre-trained public checkpoint
----------------------------------------------------
As of this implementation, no publicly-released ONNX or PyTorch CRNN
checkpoint with verified handwritten Devanagari support has been confirmed
available for automated download.  This adapter provides the full inference
pipeline; supply weights at CRNN_WEIGHTS_PATH to activate it.

CPU compatibility
-----------------
onnxruntime (CPU provider) has been verified compatible with Python 3.12+.
torch inference on CPU is also supported for Python 3.11 and below.
"""

import logging
import os
import time
from typing import List, Optional

import numpy as np

from app.recognition.base import BaseOCREngine
from app.schemas.recognition import OCRResultData, RecognitionStatus

logger = logging.getLogger("app.recognition.adapters.crnn")

_DEFAULT_WEIGHTS_PATH = os.environ.get(
    "CRNN_WEIGHTS_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "models", "crnn_devanagari.onnx"),
)
_DEFAULT_VOCAB_PATH = os.environ.get(
    "CRNN_VOCAB_PATH",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "models", "crnn_vocab.txt"),
)

# Expected input image height for the CRNN encoder (resize to this before inference)
_INPUT_HEIGHT = 32


class CRNNAdapter(BaseOCREngine):
    """CRNN-CTC OCR adapter for handwritten Devanagari.

    Inference requires either:
      1. onnxruntime (preferred, CPU-only) + an ONNX checkpoint, OR
      2. torch + a PyTorch .pt checkpoint.

    Weights must be placed at ``CRNN_WEIGHTS_PATH`` (env var or default path).
    """

    engine_id = "crnn"
    display_name = "CRNN-CTC (Handwritten Devanagari)"
    supported_scripts: List[str] = ["Devanagari"]

    def __init__(
        self,
        weights_path: Optional[str] = None,
        vocab_path: Optional[str] = None,
    ) -> None:
        super().__init__()
        self._weights_path = os.path.abspath(weights_path or _DEFAULT_WEIGHTS_PATH)
        self._vocab_path = os.path.abspath(vocab_path or _DEFAULT_VOCAB_PATH)
        self._session = None   # onnxruntime.InferenceSession when initialized
        self._vocab: List[str] = []
        self._backend: str = ""   # "onnx" or "torch"

    def _do_initialize(self) -> None:
        """Check runtime availability and load model weights."""
        # 1. Check onnxruntime
        ort_available = _check_import("onnxruntime")
        torch_available = _check_import("torch")

        if not ort_available and not torch_available:
            self._initialized = False
            self._unavailability_reason = (
                "Neither 'onnxruntime' nor 'torch' is installed. "
                "Install one to enable the CRNN adapter."
            )
            self._setup_instructions = (
                "pip install onnxruntime        # CPU-only, recommended\n"
                "# or\n"
                "pip install torch --index-url https://download.pytorch.org/whl/cpu"
            )
            logger.warning("CRNN adapter: no inference runtime available")
            return

        # 2. Check weights file
        if not os.path.isfile(self._weights_path):
            self._initialized = False
            self._unavailability_reason = (
                f"CRNN weights not found at: {self._weights_path}"
            )
            self._setup_instructions = (
                "Place a compatible CRNN-CTC ONNX checkpoint at:\n"
                f"  {self._weights_path}\n\n"
                "The model must accept inputs of shape (1, 1, 32, W) "
                "(batch, channel, height, width) with greyscale normalized pixels.\n"
                "A companion vocab.txt file listing one Devanagari character per line "
                f"must be placed at:\n  {self._vocab_path}"
            )
            logger.warning("CRNN adapter: weights file not found at %s", self._weights_path)
            return

        # 3. Load vocab
        if not os.path.isfile(self._vocab_path):
            self._initialized = False
            self._unavailability_reason = (
                f"CRNN vocabulary file not found at: {self._vocab_path}"
            )
            self._setup_instructions = (
                f"Place the character vocabulary file at:\n  {self._vocab_path}\n"
                "Each line should contain one Devanagari character; "
                "line 0 is the blank/CTC label."
            )
            logger.warning("CRNN adapter: vocab file not found at %s", self._vocab_path)
            return

        with open(self._vocab_path, encoding="utf-8") as fh:
            self._vocab = [line.rstrip("\n") for line in fh]

        # 4. Load session (prefer ONNX)
        if ort_available and self._weights_path.endswith(".onnx"):
            try:
                import onnxruntime as ort  # type: ignore
                self._session = ort.InferenceSession(
                    self._weights_path,
                    providers=["CPUExecutionProvider"],
                )
                self._backend = "onnx"
                self._initialized = True
                logger.info("CRNN adapter initialized via onnxruntime (CPU)")
            except Exception as exc:
                self._initialized = False
                self._unavailability_reason = f"Failed to load ONNX model: {exc}"
                logger.error("CRNN onnxruntime load error: %s", exc)
        elif torch_available:
            try:
                import torch  # type: ignore
                self._torch_model = torch.load(  # type: ignore
                    self._weights_path, map_location="cpu"
                )
                self._torch_model.eval()
                self._backend = "torch"
                self._initialized = True
                logger.info("CRNN adapter initialized via PyTorch (CPU)")
            except Exception as exc:
                self._initialized = False
                self._unavailability_reason = f"Failed to load PyTorch model: {exc}"
                logger.error("CRNN torch load error: %s", exc)
        else:
            self._initialized = False
            self._unavailability_reason = (
                "CRNN weights are ONNX format but onnxruntime is not installed."
            )

    def is_available(self) -> bool:
        return self._initialized

    def recognize(self, crop: np.ndarray, field_id: str, field_type: str) -> OCRResultData:
        """Run CRNN-CTC inference on a single field crop."""
        if not self.is_available():
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.WEIGHTS_NOT_FOUND
                if "weights" in self._unavailability_reason.lower()
                else RecognitionStatus.ENGINE_UNAVAILABLE,
                warnings=[self._unavailability_reason],
            )

        if crop is None or crop.size == 0:
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.EMPTY_INPUT,
                warnings=["Crop array was empty; cannot run CRNN inference"],
            )

        t0 = time.perf_counter()

        try:
            tensor = _preprocess_crop(crop)

            if self._backend == "onnx":
                text, confidence = self._infer_onnx(tensor)
            else:
                text, confidence = self._infer_torch(tensor)

            elapsed_ms = (time.perf_counter() - t0) * 1000

            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.SUCCESS,
                text=text,
                raw_text=text,
                confidence=confidence,
                is_confidence_calibrated=False,
                inference_time_ms=round(elapsed_ms, 3),
            )

        except Exception as exc:
            elapsed_ms = (time.perf_counter() - t0) * 1000
            logger.exception("CRNN inference error for field %s", field_id)
            return OCRResultData(
                field_id=field_id,
                field_type=field_type,
                model_id=self.engine_id,
                status=RecognitionStatus.FAILED,
                inference_time_ms=round(elapsed_ms, 3),
                warnings=[f"CRNN inference failed: {type(exc).__name__}"],
            )

    # ------------------------------------------------------------------
    # Internal inference helpers
    # ------------------------------------------------------------------

    def _infer_onnx(self, tensor: np.ndarray):
        """Run ONNX inference and CTC-decode the output."""
        import onnxruntime as ort  # type: ignore

        input_name = self._session.get_inputs()[0].name
        outputs = self._session.run(None, {input_name: tensor})
        # Expected output shape: (T, batch, num_classes) or (batch, T, num_classes)
        logits = outputs[0]
        return _ctc_greedy_decode(logits, self._vocab)

    def _infer_torch(self, tensor: np.ndarray):
        """Run PyTorch inference and CTC-decode the output."""
        import torch  # type: ignore

        t = torch.tensor(tensor, dtype=torch.float32)
        with torch.no_grad():
            logits = self._torch_model(t)
        return _ctc_greedy_decode(logits.numpy(), self._vocab)


# ------------------------------------------------------------------
# Preprocessing and decoding utilities
# ------------------------------------------------------------------

def _preprocess_crop(crop: np.ndarray) -> np.ndarray:
    """Convert a BGR crop to a normalized greyscale tensor (1, 1, H_target, W).

    The width is scaled proportionally to maintain aspect ratio.
    """
    import cv2  # type: ignore

    if len(crop.shape) == 3:
        grey = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        grey = crop.copy()

    h, w = grey.shape
    if h == 0 or w == 0:
        raise ValueError("Crop has zero-size dimension after conversion")

    target_h = _INPUT_HEIGHT
    scale = target_h / h
    target_w = max(1, int(w * scale))
    resized = cv2.resize(grey, (target_w, target_h), interpolation=cv2.INTER_AREA)

    # Normalize to [0.0, 1.0]
    normalized = resized.astype(np.float32) / 255.0

    # Shape: (1, 1, H, W) — batch=1, channels=1
    return normalized[np.newaxis, np.newaxis, :, :]


def _ctc_greedy_decode(logits: np.ndarray, vocab: List[str]):
    """Greedy CTC decoding: argmax at each timestep then collapse.

    Parameters
    ----------
    logits: Array of shape (T, batch, C) or (batch, T, C).
    vocab:  List of characters indexed by label (index 0 = blank).

    Returns
    -------
    (text, confidence): Tuple of decoded string and mean token probability.
    """
    # Normalize to (T, C) — take first batch item
    if logits.ndim == 3:
        if logits.shape[0] == 1:
            seq = logits[0]          # (T, C) if shape was (batch, T, C)
        else:
            seq = logits[:, 0, :]    # (T, C) if shape was (T, batch, C)
    elif logits.ndim == 2:
        seq = logits
    else:
        raise ValueError(f"Unexpected logits shape: {logits.shape}")

    # Softmax to probabilities
    exp_s = np.exp(seq - seq.max(axis=-1, keepdims=True))
    probs = exp_s / exp_s.sum(axis=-1, keepdims=True)

    # Greedy argmax
    labels = np.argmax(probs, axis=-1)   # shape (T,)
    token_probs = probs[np.arange(len(labels)), labels]

    # CTC collapse: remove blanks (label 0) and repeated consecutive labels
    blank = 0
    decoded_labels: List[int] = []
    prev: Optional[int] = None
    for lbl in labels:
        lbl = int(lbl)
        if lbl != blank and lbl != prev:
            decoded_labels.append(lbl)
        prev = lbl

    text_chars: List[str] = []
    for lbl in decoded_labels:
        if 0 <= lbl < len(vocab):
            char = vocab[lbl]
            if char:  # skip empty/blank vocab entries
                text_chars.append(char)

    text = "".join(text_chars)
    mean_conf = float(token_probs.mean()) if len(token_probs) > 0 else 0.0
    mean_conf = max(0.0, min(1.0, mean_conf))

    return text, mean_conf


def _check_import(module_name: str) -> bool:
    """Return True if a module can be imported."""
    import importlib.util
    return importlib.util.find_spec(module_name) is not None
