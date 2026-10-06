"""
Layer 3 (server side): colours and materials that keep the photo's light.

A flat colour pasted over a wall looks fake because it throws away the
shading. Every change here keeps the lighting of the original pixels:

  recolour : in CIELAB, the lightness keeps its variation around the region's
             median (shadows, folds, highlights) while the colour moves to the
             target; the old colour's own variation is mostly removed.
  material : a photographed PBR texture (pbr.py; procedural where none
             exists) laid out in real-world metres (floors in
             floor-plane coordinates, so tiles and planks follow the
             perspective) multiplied by the region's low-frequency shading,
             plus some of its fine shading for furniture (creases, edges).

Textures are deterministic (hash-based value noise), so the same scene always
renders the same image.
"""
from typing import Dict, Optional, Tuple

import cv2
import numpy as np

from . import pbr
from .catalog import MATERIALS


def hex_to_bgr(h: str) -> np.ndarray:
    h = h.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], dtype=np.float32)


def bgr_to_lab(bgr: np.ndarray) -> np.ndarray:
    """float BGR 0..255 (..., 3) -> float LAB (L 0..100)."""
    shape = bgr.shape
    lab = cv2.cvtColor((bgr.reshape(-1, 1, 3) / 255.0).astype(np.float32), cv2.COLOR_BGR2LAB)
    return lab.reshape(shape)


def lab_to_bgr(lab: np.ndarray) -> np.ndarray:
    shape = lab.shape
    bgr = cv2.cvtColor(lab.reshape(-1, 1, 3).astype(np.float32), cv2.COLOR_LAB2BGR)
    return np.clip(bgr.reshape(shape) * 255.0, 0, 255)


# ---- noise -----------------------------------------------------------------

def _hash(i: np.ndarray, j: np.ndarray, seed: float = 0.0) -> np.ndarray:
    x = np.sin(i * 127.1 + j * 311.7 + seed * 74.7) * 43758.5453
    return x - np.floor(x)


def value_noise(u: np.ndarray, v: np.ndarray, freq: float, seed: float = 0.0) -> np.ndarray:
    x, y = u * freq, v * freq
    i, j = np.floor(x), np.floor(y)
    fx, fy = x - i, y - j
    fx, fy = fx * fx * (3 - 2 * fx), fy * fy * (3 - 2 * fy)
    a, b = _hash(i, j, seed), _hash(i + 1, j, seed)
    c, d = _hash(i, j + 1, seed), _hash(i + 1, j + 1, seed)
    return (a + (b - a) * fx) * (1 - fy) + (c + (d - c) * fx) * fy


def fbm(u, v, freq, octaves=4, seed=0.0) -> np.ndarray:
    total, amp, norm = 0.0, 1.0, 0.0
    for o in range(octaves):
        total = total + amp * value_noise(u, v, freq * (2 ** o), seed + o * 13.0)
        norm += amp
        amp *= 0.5
    return total / norm


def _lighter(c: np.ndarray, f: float) -> np.ndarray:
    return np.clip(c + (255 - c) * f if f > 0 else c * (1 + f), 0, 255)


# ---- textures --------------------------------------------------------------

def texture(material: str, u: np.ndarray, v: np.ndarray, color: Optional[str]) -> np.ndarray:
    """BGR float texture (h, w, 3) for real-world coordinates in metres."""
    spec = MATERIALS[material]
    base = hex_to_bgr(color) if (color and spec["tintable"]) else hex_to_bgr(spec["color"])
    photo = pbr.photo_albedo(material, np.asarray(u, np.float64), np.asarray(v, np.float64),
                             base if (color and spec["tintable"]) else None)
    if photo is not None:
        if color and not spec["tintable"]:
            tint = hex_to_bgr(color) / np.maximum(hex_to_bgr(spec["color"]), 1)
            photo = np.clip(photo * (0.3 + 0.7 * tint), 0, 255)
        return np.ascontiguousarray(photo, dtype=np.float32)
    u = u.astype(np.float64)
    v = v.astype(np.float64)
    one = np.ones_like(u)[..., None]

    def mod(m):
        return np.clip(base[None, None, :] * m[..., None], 0, 255)

    if material in ("paint", "painted", "glass", "mdf", "plastic"):
        out = mod(1 + 0.012 * (value_noise(u, v, 90) - 0.5))
    elif material == "textured_plaster":
        out = mod(1 + 0.07 * (fbm(u, v, 6) - 0.5) + 0.05 * (value_noise(u, v, 70) - 0.5))
    elif material == "wallpaper_stripes":
        stripe = (np.floor(u / 0.09) % 2)[..., None]
        out = base * one * (1 - stripe) + _lighter(base, 0.22) * stripe
        out = out * (1 + 0.015 * (value_noise(u, v, 60) - 0.5))[..., None]
    elif material == "brick":
        row = np.floor(v / 0.075)
        off = (row % 2) * 0.115
        col = np.floor((u + off) / 0.23)
        fu, fv = (u + off) / 0.23 - col, v / 0.075 - row
        mortar = ((fu * 0.23 < 0.01) | (fv * 0.075 < 0.01))[..., None]
        var = 0.82 + 0.32 * _hash(row, col, 3.0)
        brick = mod(var * (1 + 0.12 * (fbm(u, v, 25) - 0.5)))
        out = np.where(mortar, np.array([168, 178, 186], np.float32), brick)
    elif material in ("wood_panel",):
        board = np.floor(u / 0.14)
        edge = ((u / 0.14 - board) < 0.02)[..., None]
        grain = np.sin((u * 60 + fbm(u * 3, v * 0.4, 2, 3) * 7) * 2 * np.pi)
        out = mod((0.9 + 0.2 * _hash(board, board, 5.0)) * (1 + 0.06 * grain))
        out = np.where(edge, out * 0.6, out)
    elif material == "rattan":
        weave = (np.sin(u * 2 * np.pi * 45) * np.sin(v * 2 * np.pi * 45))
        holes = (np.abs(weave) < 0.12)[..., None]
        out = mod(1 + 0.18 * weave + 0.06 * (value_noise(u, v, 30) - 0.5))
        out = np.where(holes, out * 0.55, out)
    elif material == "slate_tile":
        i, j = np.floor(u / 0.6), np.floor(v / 0.3)
        edge = (((u / 0.6 - i) * 0.6 < 0.004) | ((v / 0.3 - j) * 0.3 < 0.004))[..., None]
        tile = mod((0.85 + 0.3 * _hash(i, j, 19.0)) * (1 + 0.18 * (fbm(u * 3, v * 3, 2, 4, 43.0) - 0.5)))
        out = np.where(edge, tile * 0.6, tile)
    elif material in ("wood_planks", "herringbone", "vinyl_plank", "parquet_walnut"):
        if material == "parquet_walnut":
            material = "herringbone"
        if material in ("wood_planks", "vinyl_plank"):
            board = np.floor(u / 0.19)
            off = _hash(board, board, 7.0) * 1.2
            seg = np.floor((v + off) / 1.2)
            seam = (((u / 0.19 - board) < 0.025) | (((v + off) / 1.2 - seg) < 0.006))[..., None]
            along, across = v, u
        else:
            col = np.floor(u / 0.1)
            sign = np.where(col % 2 == 0, 1.0, -1.0)
            t = v + sign * (u - col * 0.1)
            board, seg = col, np.floor(t / 0.3)
            seam = (((u / 0.1 - col) < 0.03) | ((t / 0.3 - seg) < 0.03))[..., None]
            along, across = t, u
        var = 0.88 + 0.2 * _hash(board, seg, 11.0)
        grain = np.sin((across * 90 + fbm(across * 5, along * 0.7, 2, 3) * 9) * 2 * np.pi)
        soft = 0.5 if spec["label"].startswith("Vinyl") else 1.0
        out = mod((1 + (var - 1) * soft) * (1 + 0.04 * grain * soft + 0.06 * (fbm(u, v, 3) - 0.5)))
        out = np.where(seam, out * (0.72 if soft == 1.0 else 0.86), out)
    elif material in ("ceramic_tile", "large_tile", "terracotta", "porcelain_tile"):
        tw, th, grout = {"ceramic_tile": (0.6, 0.6, 0.004), "large_tile": (1.2, 0.6, 0.003),
                         "terracotta": (0.3, 0.3, 0.006), "porcelain_tile": (0.8, 0.8, 0.002)}[material]
        i, j = np.floor(u / tw), np.floor(v / th)
        edge = (((u / tw - i) * tw < grout) | ((v / th - j) * th < grout))[..., None]
        spread = 0.2 if material == "terracotta" else 0.05
        tile = mod((1 - spread / 2 + spread * _hash(i, j, 17.0)) * (1 + 0.05 * (fbm(u, v, 4) - 0.5)))
        out = np.where(edge, _lighter(base, 0.35 if material != "terracotta" else -0.3) * one, tile)
    elif material in ("marble_white", "marble_black"):
        t = u * 1.3 + v * 0.7 + fbm(u, v, 1.6, 5, 23.0) * 3.0
        vein = np.exp(-np.abs(np.sin(t * 2.2)) / 0.035) * (0.4 + 0.6 * fbm(u, v, 3.0, 3, 41.0))
        soft = fbm(u, v, 2.5, 4, 29.0)
        if material == "marble_white":
            out = mod(1 - 0.06 * soft - 0.22 * vein)
        else:
            out = np.clip(mod(1 + 0.3 * soft) + (170 * vein)[..., None], 0, 255)
        i, j = np.floor(u / 0.8), np.floor(v / 0.8)
        seam = (((u / 0.8 - i) * 0.8 < 0.002) | ((v / 0.8 - j) * 0.8 < 0.002))[..., None]
        out = np.where(seam, out * 0.85, out)
    elif material == "concrete":
        out = mod(1 + 0.14 * (fbm(u, v, 2.5) - 0.5) + 0.05 * (value_noise(u, v, 45) - 0.5))
    elif material == "carpet":
        out = mod(1 + 0.1 * (value_noise(u, v, 160) - 0.5) + 0.06 * (fbm(u, v, 3) - 0.5))
    elif material in ("granite", "stone"):
        out = mod(1 + 0.2 * (fbm(u, v, 9, 3, 51.0) - 0.5) + 0.08 * (value_noise(u, v, 120) - 0.5))
    elif material in ("fabric", "linen", "cotton"):
        slub = value_noise(u * 0.2, v * 6, 40) - 0.5 if material == "linen" else 0
        out = mod(1 + 0.04 * (value_noise(u, v, 60) - 0.5) + 0.04 * (fbm(u, v, 8, 2) - 0.5) + 0.08 * slub)
    elif material in ("velvet", "leather"):
        out = mod(1 + (0.05 if material == "leather" else 0.03) * (value_noise(u, v, 50) - 0.5))
    elif material in ("wood_oak", "wood_walnut", "white_wood"):
        rings = np.sin((v * 1.5 + fbm(u * 0.8, v * 5, 1.5, 3, 31.0) * 3.0) * 2 * np.pi * 9)
        amount = 0.03 if material == "white_wood" else 0.09
        out = mod(1 + amount * rings + 0.05 * (fbm(u, v, 3, 3, 37.0) - 0.5))
    elif material.startswith("metal_") or material == "stainless_steel":
        out = mod(1 + 0.06 * (value_noise(u * 3, v * 0.05, 120) - 0.5))
    else:
        out = base * one
    if color and not spec["tintable"]:
        tint = hex_to_bgr(color) / np.maximum(hex_to_bgr(spec["color"]), 1)
        out = np.clip(out * (0.3 + 0.7 * tint[None, None, :]), 0, 255)
    return out.astype(np.float32)


# ---- applying to photo pixels ------------------------------------------------

def region_stats(crop: np.ndarray, weight: np.ndarray) -> Dict:
    """Lighting of a region: lightness, its low-frequency part (shading) and
    medians, all measured on the ORIGINAL pixels."""
    lab = bgr_to_lab(crop.astype(np.float32))
    L = lab[..., 0]
    w = (weight > 0.5)
    sel = lab[w] if w.any() else lab.reshape(-1, 3)
    med = np.median(sel, 0)
    sigma = max(2.0, 0.03 * max(crop.shape[:2]))
    num = cv2.GaussianBlur(L * weight, (0, 0), sigma)
    den = cv2.GaussianBlur(weight.astype(np.float32), (0, 0), sigma)
    Lblur = np.where(den > 1e-3, num / np.maximum(den, 1e-3), med[0])
    return {"lab": lab, "L": L, "Lblur": Lblur, "L_med": float(med[0]), "a_med": float(med[1]),
            "b_med": float(med[2])}


def recolor(stats: Dict, color: str) -> np.ndarray:
    """Recoloured BGR for the whole crop (caller blends by the mask)."""
    lab = stats["lab"]
    t = bgr_to_lab(hex_to_bgr(color)[None, None, :])[0, 0]
    g = float(np.clip((t[0] + 8) / (stats["L_med"] + 8), 0.35, 1.25))
    out = np.empty_like(lab)
    out[..., 0] = np.clip(t[0] + (lab[..., 0] - stats["L_med"]) * g, 0, 100)
    out[..., 1] = t[1] + (lab[..., 1] - stats["a_med"]) * 0.25
    out[..., 2] = t[2] + (lab[..., 2] - stats["b_med"]) * 0.25
    return lab_to_bgr(out)


def shaded_material(stats: Dict, material: str, color: Optional[str], u: np.ndarray, v: np.ndarray,
                    detail: float, tex: Optional[np.ndarray] = None) -> np.ndarray:
    """Material texture lit like the original region. `detail` (0..1) is how
    much of the original fine shading to keep: high for furniture (creases,
    edges), low for floors (so old tile joints do not show through). `tex`
    may be passed in when it was computed (and cached) already."""
    if tex is None:
        tex = texture(material, u, v, color)
    L, Lb, Lm = stats["L"], stats["Lblur"], max(stats["L_med"], 5.0)
    shade = np.clip(Lb / Lm, 0.15, 2.2) ** 0.9 * np.clip((L + 3) / (Lb + 3), 0.3, 2.5) ** detail
    if material in ("leather", "velvet", "metal_brass", "metal_steel", "metal_black"):
        shade = 1 + (shade - 1) * 1.3            # glossier: stronger light and dark
    out = tex * shade[..., None]
    if material == "glass":
        out = 0.35 * out + 0.65 * lab_to_bgr(stats["lab"])
    return np.clip(out, 0, 255)


def appearance_pixels(crop: np.ndarray, weight: np.ndarray, appearance: Dict,
                      uv: Optional[Tuple[np.ndarray, np.ndarray]], detail: float,
                      stats: Optional[Dict] = None, tex: Optional[np.ndarray] = None) -> Optional[np.ndarray]:
    """New BGR pixels for a crop, or None when the appearance is unchanged."""
    material = appearance.get("material") or "original"
    color = appearance.get("color")
    if material == "original" and not color:
        return None
    stats = stats or region_stats(crop, weight)
    if material == "original":
        return recolor(stats, color)
    if uv is None and tex is None:
        h, w = crop.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        uv = (xx * 0.004, yy * 0.004)
    u, v = uv if uv is not None else (None, None)
    return shaded_material(stats, material, color, u, v, detail, tex)


def texture_fast(material: str, u: np.ndarray, v: np.ndarray, color: Optional[str]) -> np.ndarray:
    """texture() evaluated on every other pixel and upsampled: 4x cheaper,
    visually the same for surfaces."""
    h, w = u.shape
    if h < 64 or w < 64:
        return texture(material, u, v, color)
    small = texture(material, u[::2, ::2], v[::2, ::2], color)
    return cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
