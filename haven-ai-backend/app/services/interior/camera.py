"""
Layer 2: the camera and the floor plane.

A single photo has no scale, so the camera is modelled as a level pinhole
camera with an assumed field of view and eye height. The horizon (eye level)
and the central vanishing point are measured from the photo: straight edges
that recede into the room (floor boards, tile joints, the wall/floor seam)
meet there. With those, every floor pixel maps to a floor position in metres:

    depth Z = f * eye_height / (y - horizon)      lateral X = (x - vx) * Z / f

which is what lets objects shrink as they move away, textures follow the
floor's perspective, and added 3D furniture stand on the floor. Distances are
estimates (the eye height is assumed), relative sizes are consistent.
"""
import math
import random
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

FOV_DEG = 65.0            # typical phone main camera, horizontal
EYE_HEIGHT_M = 1.4        # photo taken standing, at chest/eye height
MIN_DEPTH_M = 0.5
MAX_DEPTH_M = 20.0


@dataclass
class Camera:
    width: int
    height: int
    horizon: float        # px row of the horizon (may be above the image)
    vx: float             # px column of the central vanishing point
    source: str = "default"
    fov_deg: float = FOV_DEG
    eye_height_m: float = EYE_HEIGHT_M

    @property
    def f(self) -> float:
        return (self.width / 2) / math.tan(math.radians(self.fov_deg) / 2)

    def depth_at_row(self, y: float) -> float:
        dy = y - self.horizon
        if dy <= 0:
            return MAX_DEPTH_M
        return float(min(MAX_DEPTH_M, max(MIN_DEPTH_M, self.f * self.eye_height_m / dy)))

    def row_at_depth(self, z: float) -> float:
        return self.horizon + self.f * self.eye_height_m / max(z, 1e-6)

    def floor_point(self, x: float, y: float) -> Tuple[float, float]:
        """Image point on the floor -> (X, Z) metres on the floor."""
        z = self.depth_at_row(y)
        return (x - self.vx) * z / self.f, z

    def project(self, X: float, height: float, Z: float) -> Tuple[float, float]:
        """Point `height` metres above the floor at (X, Z) -> image (x, y)."""
        Z = max(Z, 1e-3)
        return self.vx + self.f * X / Z, self.horizon + self.f * (self.eye_height_m - height) / Z

    def metres_per_px(self, y: float) -> float:
        return self.depth_at_row(y) / self.f

    def to_dict(self) -> Dict:
        return {"horizon": round(self.horizon / self.height, 4), "vanishing_x": round(self.vx / self.width, 4),
                "fov_deg": self.fov_deg, "eye_height_m": self.eye_height_m, "source": self.source}

    @classmethod
    def from_dict(cls, d: Dict, width: int, height: int) -> "Camera":
        return cls(width=width, height=height, horizon=float(d["horizon"]) * height,
                   vx=float(d["vanishing_x"]) * width, source=d.get("source", "default"),
                   fov_deg=float(d.get("fov_deg", FOV_DEG)), eye_height_m=float(d.get("eye_height_m", EYE_HEIGHT_M)))


def floor_top(floor_mask: np.ndarray) -> Optional[float]:
    """Highest row the floor reaches (robust to a few stray pixels)."""
    cols = np.where(floor_mask.any(0))[0]
    if len(cols) < floor_mask.shape[1] * 0.05:
        return None
    tops = floor_mask[:, cols].argmax(0)
    return float(np.percentile(tops, 3))


def _intersection(l1, l2) -> Optional[Tuple[float, float]]:
    x1, y1, x2, y2 = l1
    x3, y3, x4, y4 = l2
    d = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(d) < 1e-6:
        return None
    a, b = x1 * y2 - y1 * x2, x3 * y4 - y3 * x4
    return (a * (x3 - x4) - (x1 - x2) * b) / d, (a * (y3 - y4) - (y1 - y2) * b) / d


def _supports(line, p, tol_deg=2.0) -> bool:
    x1, y1, x2, y2 = line
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    a1 = math.atan2(y2 - y1, x2 - x1)
    a2 = math.atan2(p[1] - my, p[0] - mx)
    diff = abs((a1 - a2 + math.pi / 2) % math.pi - math.pi / 2)
    return math.degrees(diff) < tol_deg


def estimate_camera(img: np.ndarray, floor_mask: np.ndarray, room_mask: np.ndarray, seed: int = 7) -> Camera:
    """Finds the vanishing point of the lines receding into the room; falls
    back to a typical eye level just above the floor when there are too few."""
    h, w = img.shape[:2]
    top = floor_top(floor_mask)
    default_h = 0.45 * h if top is None else min(0.45 * h, top - 0.08 * h)
    cam = Camera(w, h, horizon=default_h, vx=w / 2, source="default")

    gray = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    region = cv2.dilate(room_mask.astype(np.uint8), np.ones((9, 9), np.uint8))
    diag = math.hypot(w, h)
    # Faint floor-board joints need gentler edge thresholds than walls.
    for lo, hi in ((50, 150), (25, 75)):
        found = _vanishing_point(gray, region, lo, hi, diag, top, h, w, seed)
        if found is not None:
            return Camera(w, h, horizon=found[1], vx=found[0], source="estimated")
    return cam


def _vanishing_point(gray, region, lo, hi, diag, top, h, w, seed) -> Optional[Tuple[float, float]]:
    edges = cv2.Canny(gray, lo, hi)
    edges[region == 0] = 0
    raw = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=50, minLineLength=int(0.06 * diag), maxLineGap=6)
    if raw is None:
        return None
    lines = []
    for x1, y1, x2, y2 in raw.reshape(-1, 4):
        ang = abs(math.degrees(math.atan2(y2 - y1, x2 - x1))) % 180
        ang = min(ang, 180 - ang)
        if 12 < ang < 86:
            lines.append((float(x1), float(y1), float(x2), float(y2)))
    if len(lines) < 3:
        return None

    lengths = [math.hypot(l[2] - l[0], l[3] - l[1]) for l in lines]
    rng = random.Random(seed)
    limit_y = (top if top is not None else h) - 5
    best, best_score = None, 0.0
    for _ in range(min(400, len(lines) * (len(lines) - 1) // 2)):
        a, b = rng.sample(range(len(lines)), 2)
        p = _intersection(lines[a], lines[b])
        if p is None or not (-0.4 * h < p[1] < limit_y) or not (-w < p[0] < 2 * w):
            continue
        support = [i for i, l in enumerate(lines) if _supports(l, p)]
        score = sum(lengths[i] for i in support)
        if len(support) >= 3 and score > best_score:
            best, best_score = support, score
    if best is None:
        return None

    # Least-squares point closest to all supporting lines.
    A, bvec = [], []
    for i in best:
        x1, y1, x2, y2 = lines[i]
        n = np.array([y2 - y1, x1 - x2], dtype=float)
        n /= np.linalg.norm(n)
        A.append(n)
        bvec.append(n @ np.array([x1, y1]))
    (px, py), *_ = np.linalg.lstsq(np.array(A), np.array(bvec), rcond=None)
    if not (-0.4 * h < py < limit_y):
        return None
    return float(np.clip(px, -w, 2 * w)), float(py)
