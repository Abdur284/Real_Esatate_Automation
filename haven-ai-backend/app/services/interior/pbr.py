"""
Physically based material data.

Every material has physical properties (roughness, metallic, opacity) in
library_data/pbr_materials.json. Most also have a photographed, tileable
texture set (colour, normal and roughness maps; CC0, Poly Haven) of a known
real size, so wood shows real grain, leather real grain and creases, tiles
real grout, at the correct scale. Materials without one fall back to the
procedural textures in materials.py.

Textures are sampled in real-world metres (u, v), with mip levels chosen
from how many metres one output pixel covers, so distant floors do not
shimmer. A chosen colour on a tintable material replaces the texture's own
colour and keeps its light/dark detail (in CIELAB).
"""
import json
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from typing import Dict, List, Optional

import cv2
import numpy as np

from .meshes import asset_root

DATA = os.path.join(os.path.dirname(__file__), "library_data", "pbr_materials.json")
with open(DATA, encoding="utf-8") as _f:
    PROPS: Dict[str, Dict] = {k: v for k, v in json.load(_f).items() if not k.startswith("_")}


def props(material: str) -> Dict:
    p = PROPS.get(material) or {}
    return {"rough": float(p.get("rough", 0.8)), "metal": float(p.get("metal", 0.0)),
            "opacity": float(p.get("opacity", 1.0))}


@dataclass
class TextureSet:
    material: str
    size_m: float
    albedo: List[np.ndarray]            # mip pyramid, BGR float32 0..255
    normal: Optional[np.ndarray]        # tangent space, float32 -1..1 (x right, y up, z out)
    rough: Optional[np.ndarray]         # float32 0..1


_sets: "OrderedDict[tuple, Optional[TextureSet]]" = OrderedDict()
_tinted: "OrderedDict[tuple, List[np.ndarray]]" = OrderedDict()
_lock = threading.Lock()


def _pyramid(img: np.ndarray) -> List[np.ndarray]:
    levels = [img]
    while min(levels[-1].shape[:2]) > 8:
        levels.append(cv2.pyrDown(levels[-1]))
    return levels


def texture_set(material: str, quality: str = "1k") -> Optional[TextureSet]:
    """The photographed texture set of a material, or None (procedural)."""
    spec = PROPS.get(material)
    if not spec or spec.get("source") != "polyhaven":
        return None
    key = (material, quality)
    with _lock:
        if key in _sets:
            _sets.move_to_end(key)
            return _sets[key]
    folder = None
    for q in ((quality, "1k") if quality != "1k" else ("1k",)):
        f = os.path.join(asset_root(), "textures", spec["asset"], q)
        if os.path.isfile(os.path.join(f, "diff.jpg")):
            folder = f
            break
    ts = None
    if folder:
        diff = cv2.imread(os.path.join(folder, "diff.jpg"), cv2.IMREAD_COLOR)
        if diff is not None:
            nrm = cv2.imread(os.path.join(folder, "nor_gl.jpg"), cv2.IMREAD_COLOR)
            rough = cv2.imread(os.path.join(folder, "rough.jpg"), cv2.IMREAD_GRAYSCALE)
            ts = TextureSet(
                material, float(spec["size_m"]), _pyramid(diff.astype(np.float32)),
                None if nrm is None else nrm[..., ::-1].astype(np.float32) / 127.5 - 1.0,
                None if rough is None else rough.astype(np.float32) / 255.0)
    with _lock:
        _sets[key] = ts
        while len(_sets) > 24:
            _sets.popitem(last=False)
    return ts


def available(material: str) -> bool:
    return texture_set(material) is not None


def _tint_level(img: np.ndarray, color_bgr: np.ndarray) -> np.ndarray:
    lab = cv2.cvtColor((img / 255.0).astype(np.float32), cv2.COLOR_BGR2LAB)
    t = cv2.cvtColor((color_bgr[None, None, :] / 255.0).astype(np.float32), cv2.COLOR_BGR2LAB)[0, 0]
    L = lab[..., 0]
    med = float(np.median(L))
    out = np.empty_like(lab)
    out[..., 0] = np.clip(t[0] + (L - med) * 0.9, 0, 100)
    out[..., 1] = t[1] + (lab[..., 1] - float(np.median(lab[..., 1]))) * 0.2
    out[..., 2] = t[2] + (lab[..., 2] - float(np.median(lab[..., 2]))) * 0.2
    return np.clip(cv2.cvtColor(out, cv2.COLOR_LAB2BGR) * 255.0, 0, 255)


def albedo_levels(material: str, color_bgr: Optional[np.ndarray], quality: str = "1k") -> Optional[List[np.ndarray]]:
    ts = texture_set(material, quality)
    if ts is None:
        return None
    if color_bgr is None or not PROPS[material].get("tint"):
        return ts.albedo
    key = (material, quality, tuple(int(c) for c in color_bgr))
    with _lock:
        if key in _tinted:
            _tinted.move_to_end(key)
            return _tinted[key]
    levels = _pyramid(_tint_level(ts.albedo[0], color_bgr))
    with _lock:
        _tinted[key] = levels
        while len(_tinted) > 16:
            _tinted.popitem(last=False)
    return levels


def pick_level(levels: List[np.ndarray], size_m: float, metres_per_px: float) -> int:
    texels_per_px = metres_per_px / size_m * levels[0].shape[1]
    lvl = int(np.clip(np.floor(np.log2(max(texels_per_px, 1e-6))), 0, len(levels) - 1))
    return lvl


def sample(img: np.ndarray, fx: np.ndarray, fy: np.ndarray) -> np.ndarray:
    """Bilinear, wrapping lookup at fractional texture coordinates (0..1 = one
    tile). Works for any leading shape of fx/fy."""
    h, w = img.shape[:2]
    shape = fx.shape
    mx = (np.mod(fx, 1.0) * w - 0.5).astype(np.float32).reshape(1, -1)
    my = (np.mod(fy, 1.0) * h - 0.5).astype(np.float32).reshape(1, -1)
    out = np.empty((mx.shape[1],) + img.shape[2:], np.float32)
    step = 30000                     # cv2.remap maps must stay below 32767 wide
    for k in range(0, mx.shape[1], step):
        r = cv2.remap(img, mx[:, k:k + step], my[:, k:k + step], cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)
        out[k:k + step] = r.reshape((-1,) + img.shape[2:])
    return out.reshape(shape + img.shape[2:])


def photo_albedo(material: str, u: np.ndarray, v: np.ndarray, color_bgr: Optional[np.ndarray],
                 quality: str = "1k") -> Optional[np.ndarray]:
    """BGR float (…, 3) texture for real-world coordinates in metres, or None
    when the material has no photographed texture."""
    ts = texture_set(material, quality)
    if ts is None:
        return None
    levels = albedo_levels(material, color_bgr, quality)
    if u.size == 1:                     # a single colour for a tiny face
        return np.broadcast_to(levels[-1].reshape(-1, 3).mean(0), u.shape + (3,)).astype(np.float32)
    if u.ndim == 2 and u.shape[0] > 1 and u.shape[1] > 1:
        du = np.hypot(np.diff(u, axis=1), np.diff(v, axis=1))
        dv = np.hypot(np.diff(u, axis=0), np.diff(v, axis=0))
        mpp = float(max(np.median(du), np.median(dv)))
    else:
        mpp = ts.size_m / levels[0].shape[1]
    lvl = pick_level(levels, ts.size_m, mpp)
    return sample(levels[lvl], u / ts.size_m, v / ts.size_m)
