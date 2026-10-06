"""
The room's light, estimated from the photo, for lighting inserted 3D models
the way the room itself is lit.

  key light : the brightest large source in view (a window or a lamp),
              placed in the room through the camera model; when none is
              visible, the room's light comes from above, shifted towards
              the brighter side of the room. Its angular size sets how soft
              the shadows are.
  ambient   : light bounced from the ceiling/walls (from above) and the
              floor (from below), coloured like them.
  exposure  : calibrated so that a surface of known albedo (the walls,
              assumed to be off-white paint) renders as bright as the walls
              do in the photo -- inserted objects get the photo's exposure
              and white balance instead of looking pasted in.
  reflections: glossy and metal surfaces reflect the photo itself (blurred
              by roughness), so brass and leather pick up the room's colours.

All values are linear light, BGR, in the renderer's world frame
(x right, y up from the floor, z away from the camera; camera at (0, eye, 0)).
"""
from dataclasses import dataclass
from typing import Dict

import cv2
import numpy as np

from . import geometry
from .camera import Camera

WALL_ALBEDO = 0.72          # typical interior paint
BEHIND_WALL, BEHIND_FLOOR, BEHIND_CEILING = 0, 1, 2


def srgb_to_linear(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4).astype(np.float32)


def linear_to_srgb(x: np.ndarray) -> np.ndarray:
    x = np.clip(x, 0.0, 1.0)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * np.power(x, 1 / 2.4) - 0.055).astype(np.float32)


def lum(c: np.ndarray) -> np.ndarray:
    """Luminance of linear BGR."""
    return c[..., 0] * 0.0722 + c[..., 1] * 0.7152 + c[..., 2] * 0.2126


@dataclass
class RoomLight:
    key_pos: np.ndarray         # (3,) world position of the key light
    key: np.ndarray             # (3,) linear irradiance of the key light
    sky: np.ndarray             # (3,) ambient irradiance from above
    ground: np.ndarray          # (3,) ambient irradiance from below
    radius: float               # angular radius of the key light (radians)
    env: np.ndarray             # linear photo, lightly blurred (reflections)
    env_blur: np.ndarray        # linear photo, strongly blurred (rough reflections)
    env_scale: float            # env pixel -> image pixel
    source: str                 # "window", "lamp" or "overhead"

    def describe(self) -> Dict:
        return {"source": self.source, "key_position_m": [round(float(v), 2) for v in self.key_pos],
                "softness": round(float(self.radius), 3)}


def _behind(scene: Dict, H: int, W: int) -> np.ndarray:
    xs = np.arange(W)
    lay = scene["layout"]
    seam = np.interp(xs / W, lay["columns"], lay["floor_y"]) * H
    rows = np.arange(H)[:, None]
    out = np.full((H, W), BEHIND_WALL, np.uint8)
    out[rows >= seam[None, :]] = BEHIND_FLOOR
    ceil = [(c, v) for c, v in zip(lay["columns"], lay["ceiling_y"]) if v is not None and v >= 0]
    if ceil:
        cy = np.interp(xs / W, [c for c, _ in ceil], [v for _, v in ceil]) * H
        out[(rows <= cy[None, :]) & (out == BEHIND_WALL)] = BEHIND_CEILING
    return out


def estimate(scene: Dict, original: np.ndarray, furniture: np.ndarray, cam: Camera) -> RoomLight:
    """`furniture`: pixels of the photo's furniture/objects (not walls/floor)."""
    H, W = original.shape[:2]
    lin = srgb_to_linear(original.astype(np.float32) / 255.0)
    L = cv2.cvtColor(original, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32) * (100.0 / 255.0)
    behind = _behind(scene, H, W)
    free = ~furniture
    wall = (behind == BEHIND_WALL) & free
    floor = (behind == BEHIND_FLOOR) & free

    def median(mask, fallback):
        return np.median(lin[mask], 0) if mask.sum() > 400 else fallback
    overall = np.median(lin.reshape(-1, 3), 0)
    wall_c = median(wall, overall)
    floor_c = median(floor, wall_c * 0.8)
    # white balance: part of the grey-world estimate (walls may be painted a colour)
    grey = lin.reshape(-1, 3).mean(0)
    tint = (grey / max(float(lum(grey)), 1e-4)) ** 0.5
    tint = tint / max(float(lum(tint)), 1e-4)
    E = float(np.clip(lum(wall_c) / WALL_ALBEDO, 0.03, 1.4))

    # the key light: a window or lamp -- a near-white region clearly brighter
    # than the walls around it (a bright white wall is not a light source)
    Lb = cv2.GaussianBlur(L, (0, 0), max(2.0, W / 150))
    wall_L = float(np.median(L[wall])) if wall.sum() > 400 else float(np.median(L))
    thr = max(96.0, float(np.percentile(Lb, 99.5)), wall_L + 9.0)
    mask = ((Lb >= thr) & (behind != BEHIND_FLOOR)).astype(np.uint8)
    n, lab, stats, cents = cv2.connectedComponentsWithStats(mask, 8)
    best = None
    if n > 1:
        k = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        if stats[k, cv2.CC_STAT_AREA] >= 0.002 * H * W:
            best = (cents[k], float(stats[k, cv2.CC_STAT_AREA]))
    if best is not None:
        (bx, by), area = best
        hc = geometry.ceiling_height(scene, cam)
        if behind[int(by), int(bx)] == BEHIND_CEILING and by < cam.horizon - 2:
            z = float(np.clip(cam.f * (hc - cam.eye_height_m) / (cam.horizon - by), 1.0, 12.0))
        else:
            z = geometry.wall_depth(scene, cam, float(bx))
        X = (bx - cam.vx) * z / cam.f
        # a window's light comes from its middle, rarely below ~1.3 m
        Y = float(np.clip(cam.eye_height_m + (cam.horizon - by) * z / cam.f, 1.3, hc))
        key_pos = np.array([X, Y, z], np.float32)
        radius = float(np.clip(np.sqrt(area) / cam.f, 0.06, 0.45))
        share = 0.6
        source = "window" if area > 0.01 * H * W else "lamp"
    else:
        # no visible source: light from above, towards the brighter side of the room
        thirds = [L[:, :W // 3][wall[:, :W // 3]], L[:, 2 * W // 3:][wall[:, 2 * W // 3:]]]
        side = 0.0
        if all(len(t) > 200 for t in thirds):
            side = float(np.clip((np.median(thirds[1]) - np.median(thirds[0])) / 15.0, -1, 1))
        depth = geometry.wall_depth(scene, cam, W / 2)
        key_pos = np.array([1.6 * side, geometry.ceiling_height(scene, cam), max(1.5, depth * 0.55)], np.float32)
        radius = 0.4
        share = 0.45
        source = "overhead"
    floor_tint = floor_c / max(float(lum(floor_c)), 1e-4)
    ambient = E * (1 - share)
    sky = ambient * tint
    ground = ambient * 0.55 * (0.5 * tint + 0.5 * floor_tint) * float(np.clip(lum(floor_c) / max(lum(wall_c), 1e-4), 0.3, 1.2))
    key = E * share / 0.75 * tint               # 0.75 ~ a typical N.L, so lit faces match the room
    scale = 4
    small = cv2.resize(lin, (max(1, W // scale), max(1, H // scale)), interpolation=cv2.INTER_AREA)
    env = cv2.GaussianBlur(small, (0, 0), 1.5)
    env_blur = cv2.GaussianBlur(small, (0, 0), 8.0)
    return RoomLight(key_pos, key.astype(np.float32), sky.astype(np.float32), ground.astype(np.float32),
                     radius, env, env_blur, float(scale), source)


def studio(cam: Camera, H: int, W: int, backdrop: np.ndarray) -> RoomLight:
    """Soft studio lighting for library previews: key from the upper left
    front, bright ambient, reflections of the plain backdrop."""
    lin = srgb_to_linear(backdrop.astype(np.float32) / 255.0)
    scale = 4
    small = cv2.resize(lin, (max(1, W // scale), max(1, H // scale)), interpolation=cv2.INTER_AREA)
    one = np.ones(3, np.float32)
    return RoomLight(np.array([-2.0, 3.2, 0.6], np.float32), one * 1.05, one * 0.5, one * 0.3, 0.35,
                     small, cv2.GaussianBlur(small, (0, 0), 6.0), float(scale), "studio")
