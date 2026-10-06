"""
Layer 1 model: semantic segmentation of a room photo.

SegFormer-B2 trained on ADE20K (150 classes, which include wall, floor,
ceiling, windows, doors and most furniture and decor), exported to ONNX and
run on the CPU with onnxruntime -- no GPU, cloud provider, API key or quota
needed: pixel-accurate masks, offline use and no per-request cost; B2 is the
accuracy/latency middle ground (about 2 s per photo on a laptop CPU, ~46
mIoU on ADE20K).

The rest of the module depends only on `segment(img) -> (class id per pixel,
confidence)` with ADE20K labels from `labels`, so the model can be replaced
or upgraded (another SegFormer size, Mask2Former, OneFormer, any ONNX export
with the same labels, or a different backend implementing the same two
members) without touching scene building, editing or rendering.

Model files live in settings.INTERIOR_SEG_MODEL_DIR (model.onnx,
config.json); see README for where to download them. The model weights are
NVIDIA's SegFormer release, licensed for non-commercial/research use.
"""
import json
import logging
import os
import threading
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings

logger = logging.getLogger(__name__)

INPUT_SIZE = 512
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
# Classes kept at full resolution: every class that wins somewhere in the
# low-resolution output, capped to keep memory bounded.
MAX_CLASSES_UPSAMPLED = 40


class SegmentationUnavailable(RuntimeError):
    """The model files or onnxruntime are missing (-> HTTP 503)."""


class Segmenter:
    def __init__(self, model_dir: str):
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise SegmentationUnavailable("onnxruntime is not installed on the server.") from e
        model_path = os.path.join(model_dir, "model.onnx")
        config_path = os.path.join(model_dir, "config.json")
        if not (os.path.isfile(model_path) and os.path.isfile(config_path)):
            raise SegmentationUnavailable(f"Room segmentation model not found in '{model_dir}'.")
        with open(config_path, encoding="utf-8") as f:
            id2label = json.load(f)["id2label"]
        self.labels: Dict[int, str] = {int(k): v.strip() for k, v in id2label.items()}
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name

    def logits(self, img_bgr: np.ndarray) -> np.ndarray:
        rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
        x = cv2.resize(rgb, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_LINEAR).astype(np.float32) / 255.0
        x = ((x - MEAN) / STD).transpose(2, 0, 1)[None]
        return self.session.run(None, {self.input_name: np.ascontiguousarray(x)})[0][0]

    def segment(self, img_bgr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Returns (class id per pixel int16, confidence per pixel float32) at
        the image's resolution. Logits are upsampled bilinearly before the
        argmax, which gives much cleaner outlines than upsampling labels."""
        h, w = img_bgr.shape[:2]
        logits = self.logits(img_bgr)                          # (C, h', w')
        coarse = logits.argmax(0)
        present, counts = np.unique(coarse, return_counts=True)
        keep = present[np.argsort(-counts)][:MAX_CLASSES_UPSAMPLED]
        up = np.stack([cv2.resize(logits[c], (w, h), interpolation=cv2.INTER_LINEAR) for c in keep])
        up -= up.max(0, keepdims=True)
        np.exp(up, out=up)
        up /= up.sum(0, keepdims=True)
        best = up.argmax(0)
        conf = np.take_along_axis(up, best[None], 0)[0].astype(np.float32)
        return keep[best].astype(np.int16), conf


_lock = threading.Lock()
_segmenter: Optional[Segmenter] = None


def get_segmenter() -> Segmenter:
    """Loaded once, on first use, so the rest of the API starts without it."""
    global _segmenter
    with _lock:
        if _segmenter is None:
            _segmenter = Segmenter(settings.INTERIOR_SEG_MODEL_DIR)
            logger.info("Interior segmentation model loaded from %s", settings.INTERIOR_SEG_MODEL_DIR)
        return _segmenter
