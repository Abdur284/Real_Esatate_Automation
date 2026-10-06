"""
Upload validation and decoding for floor-plan images.

The file type is decided from its content (never the filename or the
browser's MIME type), the byte size is capped, and OpenCV's decoder is capped
by pixel count so a small compressed file cannot expand into gigabytes.
Images are processed in memory only and never written to disk.
"""
import json
import os
import struct
import zlib
from typing import Any, Dict, Optional

# Must be set before cv2 is imported: OpenCV reads it once, at first decode.
MAX_PIXELS = 40_000_000
os.environ.setdefault("OPENCV_IO_MAX_IMAGE_PIXELS", str(MAX_PIXELS))

import cv2  # noqa: E402
import numpy as np  # noqa: E402

MAX_IMAGE_BYTES = 8 * 1024 * 1024
MIN_SIDE_PX = 250
MAX_EMBEDDED_BYTES = 1024 * 1024
EMBEDDED_KEYWORD = b"haven-plan2d"


class ImageRejected(ValueError):
    """The upload is not an acceptable image (-> HTTP 415)."""


def sniff_image(data: bytes) -> str:
    if not data:
        raise ImageRejected("The uploaded file is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRejected(f"The image is larger than {MAX_IMAGE_BYTES // (1024 * 1024)} MB.")
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    raise ImageRejected("Only PNG, JPEG or WebP floor-plan images are accepted.")


def decode_image(data: bytes) -> np.ndarray:
    """Returns a BGR uint8 image or raises ImageRejected."""
    sniff_image(data)
    try:
        img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    except cv2.error:
        img = None
    if img is None or img.ndim != 3:
        raise ImageRejected("The image could not be read. It may be damaged or too large "
                            f"(limit {MAX_PIXELS // 1_000_000} megapixels).")
    return img


def rotate_front_to_bottom(img: np.ndarray, front: str) -> np.ndarray:
    """Plans are analysed with the road (front) at the bottom of the image."""
    front = (front or "bottom").lower()
    if front == "top":
        return cv2.rotate(img, cv2.ROTATE_180)
    if front == "left":
        return cv2.rotate(img, cv2.ROTATE_90_COUNTERCLOCKWISE)
    if front == "right":
        return cv2.rotate(img, cv2.ROTATE_90_CLOCKWISE)
    return img


def extract_embedded_plan(data: bytes) -> Optional[Dict[str, Any]]:
    """A PNG exported by HAVEN's 2D Design module carries the exact plan JSON in
    a tEXt/iTXt chunk. Returns it (untrusted; the caller validates) or None."""
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    pos = 8
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8: pos + 8 + length]
        pos += 12 + length
        if ctype == b"IEND":
            break
        if ctype not in (b"tEXt", b"iTXt") or not body.startswith(EMBEDDED_KEYWORD + b"\x00"):
            continue
        rest = body[len(EMBEDDED_KEYWORD) + 1:]
        try:
            if ctype == b"iTXt":
                compressed, _method = rest[0], rest[1]
                rest = rest[2:]
                _lang, rest = rest.split(b"\x00", 1)
                _translated, text = rest.split(b"\x00", 1)
                if compressed:
                    text = zlib.decompressobj().decompress(text, MAX_EMBEDDED_BYTES)
            else:
                text = rest
            if len(text) > MAX_EMBEDDED_BYTES:
                return None
            plan = json.loads(text.decode("utf-8"))
        except (ValueError, IndexError, zlib.error, UnicodeDecodeError):
            return None
        return plan if isinstance(plan, dict) else None
    return None
