"""
Flat wall items drawn straight onto the wall: framed art, wall-art sets,
mirrors, clocks, curtains, blinds and wall lights.

Each is drawn inside the item's quad (its real width x height at the wall's
distance, from geometry.wall_panel) in the item's own 2D coordinates and
warped into place, then lit like the room. Style parameters come from the
library item (library_data/*.json): e.g. curtains have style simple /
blackout / sheer / grommet / traditional and how far they are open.
"""
import math
from typing import Dict, Optional

import cv2
import numpy as np

from .materials import hex_to_bgr, texture

FRAME_MATERIALS = ("metal_brass", "metal_black", "metal_steel", "wood_oak", "wood_walnut", "white_wood", "painted")


def _frame_color(obj: Dict, default: str = "metal_black") -> np.ndarray:
    mat = obj["appearance"].get("material") or default
    if mat not in FRAME_MATERIALS:
        mat = default
    color = obj["appearance"].get("color") if mat == "painted" else None
    return texture(mat, np.zeros((1, 1)), np.zeros((1, 1)), color)[0, 0].astype(np.float32)


def _seed(obj: Dict) -> int:
    return sum(map(ord, obj.get("library_item", {}).get("id", obj["id"]))) * 7919


def _art(style: str, color: Optional[str], w: int, h: int, seed: int) -> np.ndarray:
    base = hex_to_bgr(color or "#5b7fa6")
    rng = np.random.default_rng(seed)
    img = np.full((h, w, 3), 238, np.float32)
    if style == "landscape":
        horizon = int(h * rng.uniform(0.45, 0.6))
        sky = np.linspace(0, 1, horizon)[:, None, None]
        img[:horizon] = (np.array([235, 215, 190]) * (1 - sky) + np.clip(base * 1.25, 0, 255) * sky)[::-1]
        for k in range(3):
            pts = [(0, h)]
            for x in np.linspace(0, w, 9):
                pts.append((int(x), int(horizon - h * rng.uniform(0.02, 0.18) * (1 - k * 0.3) + k * h * 0.08)))
            pts.append((w, h))
            c = np.clip(base * (0.45 + 0.18 * k) + [20, 30, 10], 0, 255)
            cv2.fillPoly(img, [np.array(pts, np.int32)], c.tolist(), cv2.LINE_AA)
    elif style == "geometric":
        for _ in range(7):
            c = np.clip(base * rng.uniform(0.4, 1.4) + rng.uniform(-40, 40, 3), 0, 255).tolist()
            p = (rng.uniform(0, 1, (3, 2)) * [w, h]).astype(np.int32)
            cv2.fillPoly(img, [p], c, cv2.LINE_AA)
    elif style == "minimal":
        cv2.circle(img, (int(w * 0.5), int(h * 0.55)), int(min(w, h) * 0.22), np.clip(base * 0.6, 0, 255).tolist(), -1,
                   cv2.LINE_AA)
        cv2.line(img, (int(w * 0.2), int(h * 0.3)), (int(w * 0.8), int(h * 0.75)), (60, 60, 60), max(1, w // 150),
                 cv2.LINE_AA)
    elif style == "botanical":
        img[:] = [224, 232, 236]
        for k in range(9):
            a = rng.uniform(-1.2, 1.2)
            L = h * rng.uniform(0.2, 0.4)
            x0, y0 = w * 0.5, h * 0.85
            x1, y1 = x0 + math.sin(a) * L, y0 - math.cos(a) * L
            cv2.line(img, (int(x0), int(y0)), (int(x1), int(y1)), (60, 90, 50), max(1, w // 120), cv2.LINE_AA)
            cv2.ellipse(img, (int(x1), int(y1)), (int(w * 0.07), int(w * 0.03)), math.degrees(a) + 90, 0, 360,
                        np.clip(base * 0.3 + [30, 110, 40], 0, 255).tolist(), -1, cv2.LINE_AA)
    else:   # abstract
        for i in range(6):
            c = np.clip(base * rng.uniform(0.5, 1.4) + rng.uniform(-30, 30, 3), 0, 255).tolist()
            if i % 2:
                cv2.circle(img, (int(rng.uniform(0.2, 0.8) * w), int(rng.uniform(0.2, 0.8) * h)),
                           int(rng.uniform(0.1, 0.3) * min(w, h)), c, -1, cv2.LINE_AA)
            else:
                x0, y0 = int(rng.uniform(0, 0.6) * w), int(rng.uniform(0, 0.6) * h)
                cv2.rectangle(img, (x0, y0), (x0 + int(rng.uniform(0.2, 0.5) * w), y0 + int(rng.uniform(0.2, 0.5) * h)),
                              c, -1)
    return cv2.GaussianBlur(img, (3, 3), 0)


def _curtain(style: str, color: Optional[str], w: int, h: int, opening: float, seed: int):
    """(colour, alpha) of a curtain pair seen flat, open by `opening` (0-1)."""
    fabric = hex_to_bgr(color or "#d8d2c8")
    col = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)
    rod = max(2, int(h * 0.02))
    xs = np.arange(w, dtype=np.float32)
    if style == "sheer":
        panels = [(0, w)]
        opacity = 0.42
    else:
        side = max(0.14, (1 - opening) / 2)
        panels = [(0, int(w * side)), (int(w * (1 - side)), w)]
        opacity = 0.99 if style == "blackout" else 0.93
    for a, b in panels:
        pw = max(1, b - a)
        folds = max(3, int(pw / max(6, w * 0.035)))
        phase = (xs[a:b] - a) / pw * folds * 2 * math.pi
        shade = 0.84 + 0.16 * np.cos(phase)                     # soft pleats
        if style == "blackout":
            shade = 0.72 + 0.28 * np.cos(phase)
        tone = fabric * (0.78 if style == "blackout" else 1.0)
        col[rod:, a:b] = tone[None, None, :] * shade[None, :, None]
        alpha[rod:, a:b] = opacity
        if style == "traditional":
            # tie-backs: the panel narrows at 60% height
            tie = int(h * 0.6)
            for y in range(rod, h):
                t = 1 - abs(y - tie) / max(1, tie)
                cut = int(pw * 0.35 * max(0, t) ** 1.5)
                if a == 0:
                    alpha[y, b - cut:b] = 0
                else:
                    alpha[y, a:a + cut] = 0
            cv2.rectangle(col, (a, tie - 3), (b, tie + 3), (fabric * 0.6).tolist(), -1)
    if style == "traditional":
        val = int(h * 0.1)
        col[rod:rod + val] = fabric * 0.92
        alpha[rod:rod + val] = 0.98
        for k in range(8):
            cx = int((k + 0.5) * w / 8)
            cv2.ellipse(alpha, (cx, rod + val), (int(w / 16), max(2, val // 3)), 0, 0, 180, 0.98, -1)
            cv2.ellipse(col, (cx, rod + val), (int(w / 16), max(2, val // 3)), 0, 0, 180, (fabric * 0.88).tolist(), -1)
    col[:rod] = [40, 40, 40]
    alpha[:rod] = 1.0
    if style == "grommet":
        for a, b in panels:
            for x in np.linspace(a + 4, b - 4, max(2, (b - a) // max(8, w // 30))):
                cv2.circle(col, (int(x), rod + 2), max(2, rod), (140, 140, 140), -1, cv2.LINE_AA)
    return col, alpha


def _blinds(style: str, color: Optional[str], w: int, h: int, drop: float):
    c = hex_to_bgr(color or "#eeeae2")
    col = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)
    bottom = max(4, int(h * drop))
    col[:bottom] = c
    alpha[:bottom] = 0.97
    if style == "venetian":
        slat = max(3, h // 45)
        for y in range(0, bottom, slat):
            col[y:y + max(1, slat // 3)] *= 0.72
    else:
        col[:bottom] *= np.linspace(1.02, 0.94, bottom)[:, None, None]
        col[max(0, bottom - 4):bottom] = c * 0.55
    col[:max(2, h // 40)] = c * 0.8
    alpha[:max(2, h // 40)] = 1.0
    return col, alpha


def _clock(style: str, color: Optional[str], frame: np.ndarray, w: int, h: int):
    col = np.zeros((h, w, 3), np.float32)
    alpha = np.zeros((h, w), np.float32)
    face = hex_to_bgr(color or "#f4f1ea")
    c = (w // 2, h // 2)
    r = min(w, h) // 2 - 1
    if style == "square":
        cv2.rectangle(col, (1, 1), (w - 2, h - 2), frame.tolist(), -1)
        cv2.rectangle(alpha, (1, 1), (w - 2, h - 2), 1.0, -1)
        cv2.rectangle(col, (int(w * 0.07), int(h * 0.07)), (int(w * 0.93), int(h * 0.93)), face.tolist(), -1)
    else:
        cv2.circle(col, c, r, frame.tolist(), -1, cv2.LINE_AA)
        cv2.circle(alpha, c, r, 1.0, -1, cv2.LINE_AA)
        cv2.circle(col, c, int(r * 0.9), face.tolist(), -1, cv2.LINE_AA)
    for k in range(12):
        a = 2 * math.pi * k / 12
        p0 = (int(c[0] + math.sin(a) * r * 0.72), int(c[1] - math.cos(a) * r * 0.72))
        p1 = (int(c[0] + math.sin(a) * r * 0.82), int(c[1] - math.cos(a) * r * 0.82))
        cv2.line(col, p0, p1, (40, 40, 40), max(1, r // 30), cv2.LINE_AA)
    cv2.line(col, c, (int(c[0] + r * 0.45), int(c[1] - r * 0.2)), (30, 30, 30), max(1, r // 18), cv2.LINE_AA)
    cv2.line(col, c, (int(c[0] - r * 0.1), int(c[1] - r * 0.65)), (30, 30, 30), max(1, r // 25), cv2.LINE_AA)
    return col, alpha


def _mirror_reflection(canvas: np.ndarray, quad: np.ndarray, w: int, h: int) -> np.ndarray:
    H, W = canvas.shape[:2]
    center = quad.mean(0)
    cx = int(np.clip(center[0], 0, W - 1))
    sx0, sx1 = max(0, cx - w), min(W, cx + w)
    sy0, sy1 = max(0, int(center[1]) - h // 2), min(H, int(center[1]) + h)
    src = canvas[sy0:sy1, sx0:sx1][:, ::-1]
    if src.size == 0:
        return np.full((h, w, 3), 200, np.float32)
    pic = cv2.resize(cv2.GaussianBlur(src, (0, 0), 3), (w, h)).astype(np.float32) * 0.88 + 28
    pic[..., 0] += 6
    return pic


def render_item(generator: str, params: Dict, obj: Dict, canvas: np.ndarray, quad: np.ndarray,
                room_light: float, wb: np.ndarray):
    """(colour, alpha) of the item in its own w x h pixel frame."""
    w = max(8, int(np.linalg.norm(quad[1] - quad[0])))
    h = max(8, int(np.linalg.norm(quad[3] - quad[0])))
    color = obj["appearance"].get("color")
    seed = _seed(obj)
    col = np.zeros((h, w, 3), np.float32)
    alpha = np.ones((h, w), np.float32)
    if generator in ("painting", "wall_art", "mirror"):
        frame_style = params.get("frame", "thin")
        fcol = _frame_color(obj, "metal_black" if generator != "mirror" else "metal_brass")
        f = 0 if frame_style == "none" else max(2, int(min(w, h) * (0.03 if frame_style == "thin" else 0.07)))
        panels = int(params.get("panels", 1)) if generator == "wall_art" else 1
        gap = max(3, int(w * 0.03)) if panels > 1 else 0
        pw = (w - gap * (panels - 1)) // panels
        alpha[:] = 0
        shape = params.get("shape", "rect")
        for k in range(panels):
            x0 = k * (pw + gap)
            sub_a = np.zeros((h, pw), np.float32)
            if shape == "round" or shape == "oval":
                cv2.ellipse(sub_a, (pw // 2, h // 2), (pw // 2 - 1, h // 2 - 1), 0, 0, 360, 1.0, -1, cv2.LINE_AA)
            elif shape == "arch":
                cv2.rectangle(sub_a, (0, pw // 2), (pw - 1, h - 1), 1.0, -1)
                cv2.ellipse(sub_a, (pw // 2, pw // 2), (pw // 2 - 1, pw // 2 - 1), 0, 180, 360, 1.0, -1, cv2.LINE_AA)
            else:
                sub_a[:] = 1.0
            inner = cv2.erode(sub_a, np.ones((2 * f + 1, 2 * f + 1), np.uint8)) if f else sub_a
            if generator == "mirror":
                pic = _mirror_reflection(canvas, quad, pw, h)
            else:
                pic = _art(params.get("art", "abstract"), color, pw, h, seed + k * 17)
                if params.get("mat"):
                    m = max(2, int(min(pw, h) * 0.08))
                    pic2 = np.full_like(pic, 242)
                    pic2[m + f:h - m - f, m + f:pw - m - f] = cv2.resize(pic, (max(1, pw - 2 * (m + f)),
                                                                             max(1, h - 2 * (m + f))))
                    pic = pic2
                pic = pic * room_light
            frame_part = (sub_a - inner)[..., None]
            col[:, x0:x0 + pw] = pic * inner[..., None] + fcol * room_light * frame_part
            alpha[:, x0:x0 + pw] = sub_a
    elif generator == "clock":
        c, a = _clock(params.get("style", "round"), color, _frame_color(obj, "metal_black"), w, h)
        col, alpha = c * room_light, a
    elif generator == "curtains":
        c, a = _curtain(params.get("style", "simple"), color, w, h, float(params.get("open", 0.55)), seed)
        light = np.linspace(1.05, 0.88, h)[:, None, None] * room_light
        col, alpha = c * light, a
    elif generator == "blinds":
        c, a = _blinds(params.get("style", "roller"), color, w, h, float(params.get("drop", 0.75)))
        col, alpha = c * room_light, a
    elif generator == "wall_light":
        alpha[:] = 0
        metal = _frame_color(obj, "metal_brass") * room_light
        plate = (int(w * 0.35), int(h * 0.62), int(w * 0.65), int(h * 0.95))
        cv2.rectangle(col, plate[:2], plate[2:], metal.tolist(), -1)
        cv2.rectangle(alpha, plate[:2], plate[2:], 1.0, -1)
        shade = np.array([205, 228, 243], np.float32) if params.get("style") != "globe" else np.array([240, 245, 248])
        if params.get("style") == "globe":
            cv2.circle(col, (w // 2, int(h * 0.35)), int(min(w, h) * 0.3), shade.tolist(), -1, cv2.LINE_AA)
            cv2.circle(alpha, (w // 2, int(h * 0.35)), int(min(w, h) * 0.3), 1.0, -1, cv2.LINE_AA)
        else:
            pts = np.array([[w * 0.1, h * 0.55], [w * 0.9, h * 0.55], [w * 0.75, h * 0.05], [w * 0.25, h * 0.05]], np.int32)
            cv2.fillPoly(col, [pts], shade.tolist(), cv2.LINE_AA)
            cv2.fillPoly(alpha, [pts], 1.0, cv2.LINE_AA)
    return np.clip(col * wb[None, None, :], 0, 255), alpha


def draw(canvas: np.ndarray, obj: Dict, generator: str, params: Dict, quad: np.ndarray,
         room_light: float, wb: np.ndarray) -> None:
    """Draws a wall item into `canvas` (float BGR) inside `quad`."""
    H, W = canvas.shape[:2]
    x0, y0 = np.floor(quad.min(0)).astype(int) - 8
    x1, y1 = np.ceil(quad.max(0)).astype(int) + 8
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x0 >= x1 or y0 >= y1:
        return
    pw = float(np.linalg.norm(quad[1] - quad[0]))
    col, alpha = render_item(generator, params, obj, canvas, quad, room_light, wb)
    h, w = alpha.shape
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]),
                                     (quad - [x0, y0]).astype(np.float32))
    size = (x1 - x0, y1 - y0)
    wc = cv2.warpPerspective(col.astype(np.float32), Hm, size, flags=cv2.INTER_LINEAR)
    wa = cv2.warpPerspective(alpha.astype(np.float32), Hm, size, flags=cv2.INTER_LINEAR)[..., None]
    roi = canvas[y0:y1, x0:x1]
    if generator not in ("curtains", "blinds"):
        # a soft shadow of the item's own shape, a little down and right
        sh = cv2.warpAffine(wa[..., 0], np.float32([[1, 0, pw * 0.02], [0, 1, pw * 0.03]]), size)
        sh = cv2.GaussianBlur(sh, (0, 0), max(1.0, pw * 0.02))
        roi *= (1 - 0.3 * sh)[..., None]
    roi[:] = roi * (1 - wa) + wc * wa
