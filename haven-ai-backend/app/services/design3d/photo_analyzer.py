"""
Built-in (non-AI) analysis of a property photo.

The browser shrinks the photo to a small RGB grid (at most 128 x 128) and
sends the raw pixels; everything here is plain Python, so no image library,
model download or external AI service is involved.

What a pixel-level analyser can measure reliably is limited, and the output
says so: photo quality (size, exposure, contrast, sharpness) and the colour
palette of the building. Floors, doors and windows are NOT detected here;
they come from the user (form fields) and are reported as user-provided.
"""
import base64
from typing import Dict, List, Optional, Tuple

MAX_SIDE = 128
Pixel = Tuple[int, int, int]


class PixelsRejected(ValueError):
    """The pixel grid sent by the browser is malformed."""


def decode_pixels(b64: str, width: int, height: int) -> List[Pixel]:
    if not (8 <= width <= MAX_SIDE and 8 <= height <= MAX_SIDE):
        raise PixelsRejected(f"Pixel grid must be between 8 and {MAX_SIDE} px on each side.")
    try:
        raw = base64.b64decode(b64 or "", validate=True)
    except ValueError:
        raise PixelsRejected("Pixel data is not valid base64.")
    if len(raw) != width * height * 3:
        raise PixelsRejected("Pixel data does not match the stated grid size.")
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]


def _lum(p: Pixel) -> float:
    return 0.299 * p[0] + 0.587 * p[1] + 0.114 * p[2]


def _hex(p) -> str:
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, int(round(c)))) for c in p))


def _is_sky(p: Pixel) -> bool:
    r, g, b = p
    return (b > r + 18 and b > 140) or (_lum(p) > 235 and max(p) - min(p) < 20)


def _kmeans(points: List[Pixel], k: int, rounds: int = 8) -> List[Tuple[Tuple[float, float, float], int]]:
    """Deterministic k-means (farthest-point seeding). Returns (centre, size)
    pairs, largest cluster first."""
    if not points:
        return []
    centres = [tuple(float(c) for c in points[0])]
    while len(centres) < k:
        far = max(points, key=lambda p: min(sum((p[i] - c[i]) ** 2 for i in range(3)) for c in centres))
        if far in centres:
            break
        centres.append(tuple(float(c) for c in far))
    for _ in range(rounds):
        groups: List[List[Pixel]] = [[] for _ in centres]
        for p in points:
            j = min(range(len(centres)), key=lambda j: sum((p[i] - centres[j][i]) ** 2 for i in range(3)))
            groups[j].append(p)
        centres = [tuple(sum(p[i] for p in g) / len(g) for i in range(3)) if g else centres[j]
                   for j, g in enumerate(groups)]
    sizes = [0] * len(centres)
    for p in points:
        sizes[min(range(len(centres)), key=lambda j: sum((p[i] - centres[j][i]) ** 2 for i in range(3)))] += 1
    return sorted(zip(centres, sizes), key=lambda cs: -cs[1])


def analyze_pixels(pixels: List[Pixel], width: int, height: int) -> Dict:
    lum = [_lum(p) for p in pixels]
    n = len(lum)
    mean = sum(lum) / n
    std = (sum((v - mean) ** 2 for v in lum) / n) ** 0.5
    # Sharpness: mean absolute Laplacian of the luminance grid.
    lap = []
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            i = y * width + x
            lap.append(abs(4 * lum[i] - lum[i - 1] - lum[i + 1] - lum[i - width] - lum[i + width]))
    sharpness = sum(lap) / len(lap) if lap else 0.0

    issues: List[str] = []
    if mean < 40:
        issues.append("The photo is very dark.")
    elif mean > 225:
        issues.append("The photo is overexposed (almost white).")
    if std < 15:
        issues.append("The photo has almost no contrast, so no building details can be read.")
    if sharpness < 2.0:
        issues.append("The photo is very blurry.")

    # Palette from the central part of the frame, where the facade usually is,
    # ignoring sky-like pixels.
    central = [pixels[y * width + x]
               for y in range(int(height * 0.2), int(height * 0.9))
               for x in range(int(width * 0.12), int(width * 0.88))]
    building = [p for p in central if not _is_sky(p)] or central
    clusters = _kmeans(building, 5)
    wall = clusters[0][0] if clusters else (220, 210, 190)
    others = [c for c, size in clusters[1:] if size >= len(building) * 0.03]
    darkest = min(others, key=_lum, default=wall)
    trim = next((c for c in others if c is not darkest), darkest)
    sky_share = sum(1 for p in pixels[: width * max(1, height // 4)] if _is_sky(p)) / (width * max(1, height // 4))

    return {
        "quality": {
            "usable": not issues,
            "issues": issues,
            "brightness": round(mean, 1), "contrast": round(std, 1), "sharpness": round(sharpness, 2),
            "grid": f"{width}x{height}",
        },
        "palette": [{"color": _hex(c), "share": round(s / max(len(building), 1), 3)} for c, s in clusters],
        "colors": {"walls": _hex(wall), "trim": _hex(trim), "window_frames": _hex(darkest),
                   "door": _hex(darkest), "roof": _hex(trim)},
        "sky_visible": sky_share > 0.25,
    }


def describe_color(hex_color: str) -> str:
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    lum = _lum((r, g, b))
    spread = max(r, g, b) - min(r, g, b)
    if spread < 22:
        return "white" if lum > 215 else "light grey" if lum > 160 else "grey" if lum > 90 else "dark grey"
    if r >= g >= b:
        return "cream/beige" if lum > 170 else "brown" if lum < 110 else "tan"
    if b > r and b > g:
        return "blue"
    if g > r and g > b:
        return "green"
    return "coloured"


def palette_summary(colors: Dict[str, str]) -> Optional[str]:
    wall = colors.get("walls")
    return f"Main wall colour appears {describe_color(wall)} ({wall})" if wall else None
