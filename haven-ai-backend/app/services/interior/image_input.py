"""
Upload checks for room photos.

The type is decided from the file's content (never its name or the browser's
MIME type), the byte size and decoded pixel count are capped, and the photo is
checked for being usable at all (too small, too dark, washed out, too blurry)
before any AI runs. Accepted photos are resized so the long side is at most
WORK_MAX_SIDE; every later stage works at that resolution.
"""
from typing import Dict, List, Tuple

# Importing plan_vision.image_io first sets OpenCV's decoded-pixel cap before
# cv2 is loaded anywhere else.
from app.services.plan_vision.image_io import MAX_PIXELS  # noqa: F401  (side effect)

import cv2  # noqa: E402
import numpy as np  # noqa: E402

MAX_IMAGE_BYTES = 10 * 1024 * 1024
MIN_SIDE_PX = 320
MAX_ASPECT = 3.5
WORK_MAX_SIDE = 1280

# Quality thresholds (0-255 luminance, edge strength on a 512 px copy).
DARK_REJECT, DARK_WARN = 28, 55
BRIGHT_REJECT = 245
BLUR_REJECT, BLUR_WARN = 18.0, 40.0


class RoomImageRejected(ValueError):
    """The upload cannot be used. `code` tells the client which case it is."""

    def __init__(self, message: str, code: str, status: int = 415):
        super().__init__(message)
        self.code = code
        self.status = status


def sniff_image(data: bytes) -> str:
    if not data:
        raise RoomImageRejected("The uploaded file is empty.", "empty")
    if len(data) > MAX_IMAGE_BYTES:
        raise RoomImageRejected(f"The image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.",
                                "too_large", 413)
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise RoomImageRejected("Only JPG, PNG or WebP photos are accepted.", "unsupported_type")


def decode(data: bytes) -> np.ndarray:
    """BGR uint8 image, EXIF orientation applied."""
    sniff_image(data)
    try:
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        img = None
    if img is None or img.ndim != 3:
        raise RoomImageRejected("The image could not be read. It may be damaged or too large "
                                f"(limit {MAX_PIXELS // 1_000_000} megapixels).", "unreadable")
    return img


def to_working_size(img: np.ndarray) -> np.ndarray:
    h, w = img.shape[:2]
    scale = min(1.0, WORK_MAX_SIDE / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, (round(w * scale), round(h * scale)), interpolation=cv2.INTER_AREA)
    return np.ascontiguousarray(img)


def measure_quality(img: np.ndarray) -> Dict[str, float]:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    s = 512 / max(h, w)
    small = cv2.resize(gray, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    lap = np.abs(cv2.Laplacian(small, cv2.CV_32F, ksize=3))
    return {
        "brightness": float(gray.mean()),
        "bright_p95": float(np.percentile(gray, 95)),
        "contrast": float(gray.std()),
        # Strength of the strongest edges: a blurry photo has none.
        "sharpness": float(np.percentile(lap, 99.5)),
    }


def check_quality(img: np.ndarray) -> Tuple[Dict[str, float], List[str]]:
    """Raises RoomImageRejected for unusable photos; returns warnings for poor ones."""
    h, w = img.shape[:2]
    if min(h, w) < MIN_SIDE_PX:
        raise RoomImageRejected(f"The photo is too small ({w}x{h} px). Use one at least "
                                f"{MIN_SIDE_PX} px on each side.", "too_small", 422)
    if max(h, w) / min(h, w) > MAX_ASPECT:
        raise RoomImageRejected("The photo is too narrow or panoramic. Use a normal photo of the room.",
                                "bad_aspect", 422)
    q = measure_quality(img)
    warnings: List[str] = []
    if q["brightness"] < DARK_REJECT and q["bright_p95"] < 90:
        raise RoomImageRejected("The photo is too dark to see the room. Turn on the lights or use "
                                "a photo taken in daylight.", "too_dark", 422)
    if q["brightness"] > BRIGHT_REJECT:
        raise RoomImageRejected("The photo is washed out (over-exposed). Use a photo with less glare.",
                                "too_bright", 422)
    if q["sharpness"] < BLUR_REJECT:
        raise RoomImageRejected("The photo is too blurry to find the furniture. Hold the camera "
                                "steady and try again.", "too_blurry", 422)
    if q["brightness"] < DARK_WARN:
        warnings.append("The photo is quite dark, so some objects may be missed and colours may look off.")
    if q["sharpness"] < BLUR_WARN:
        warnings.append("The photo is a little blurry, so object outlines may be less precise.")
    if q["contrast"] < 18:
        warnings.append("The photo has very low contrast, so some objects may be missed.")
    return {k: round(v, 1) for k, v in q.items()}, warnings


def load_room_photo(data: bytes) -> Tuple[np.ndarray, Dict]:
    """Validates and decodes an upload. Returns (working BGR image, info)."""
    mime = sniff_image(data)
    img = decode(data)
    oh, ow = img.shape[:2]
    quality, warnings = check_quality(img)
    work = to_working_size(img)
    return work, {"mime": mime, "original_width": ow, "original_height": oh,
                  "width": work.shape[1], "height": work.shape[0],
                  "quality": quality, "warnings": warnings}
