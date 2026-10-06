"""
Scene state -> image. The deterministic "composite" renderer.

The picture is always rebuilt from the original photo and the scene, never
edited in place, so undo/redo/reload reproduce it exactly:

  1. clean plate: the photo with every object that no longer sits where it
     was photographed (moved, resized, mirrored, replaced, removed) erased.
     The hole is filled with the surface behind it -- floor below the
     wall/floor seam, wall above -- by copying real texture from the same
     image row (same distance from the camera) over a smooth lighting fill.
  2. surfaces: new wall/floor/ceiling colours and materials, lit like the
     original, textures laid in real-world metres along the floor plane.
  3. objects, far to near: photo cut-outs (recoloured/re-materialed, then
     moved and scaled with perspective, with a contact shadow) and 3D models
     (projected through the camera, lit, with a contact shadow).

This is the final image too (with the high-quality assets); no generative
model repaints it, so what the editor shows is what is downloaded.
"""
import math
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Tuple

import cv2
import numpy as np

from . import geometry, lighting, mesh_render, wall2d
from .camera import Camera
from .materials import appearance_pixels, hex_to_bgr, texture, texture_fast

LIGHT_DIR = np.array([-0.35, 0.85, -0.4]) / np.linalg.norm([-0.35, 0.85, -0.4])
BEHIND_WALL, BEHIND_FLOOR, BEHIND_CEILING = 0, 1, 2


@dataclass
class Assets:
    original: np.ndarray                      # BGR uint8, working size
    instances: np.ndarray                     # uint8 instance index per pixel
    alphas: Dict[int, Tuple[int, int, np.ndarray]]   # idx -> (y0, x0, alpha crop)
    plates: "OrderedDict[FrozenSet[int], tuple]" = field(default_factory=OrderedDict)
    surfaces: "OrderedDict[tuple, tuple]" = field(default_factory=OrderedDict)
    textures: "OrderedDict[tuple, np.ndarray]" = field(default_factory=OrderedDict)
    layers: "OrderedDict[str, dict]" = field(default_factory=OrderedDict)    # rendered 3D models
    lock: threading.Lock = field(default_factory=threading.Lock)


def full_mask(assets: Assets, idx: int, threshold: int = 20) -> np.ndarray:
    H, W = assets.instances.shape
    m = np.zeros((H, W), bool)
    if idx in assets.alphas:
        y0, x0, a = assets.alphas[idx]
        m[y0:y0 + a.shape[0], x0:x0 + a.shape[1]] = a > threshold
    return m


def behind_map(scene: Dict, H: int, W: int) -> np.ndarray:
    """What is behind any pixel if the furniture were gone: floor below the
    wall/floor seam, ceiling above the ceiling line, wall in between."""
    xs = np.arange(W)
    lay = scene["layout"]
    seam = np.interp(xs / W, lay["columns"], lay["floor_y"]) * H
    rows = np.arange(H)[:, None]
    out = np.full((H, W), BEHIND_WALL, np.uint8)
    out[rows >= seam[None, :]] = BEHIND_FLOOR
    ceil = [(c, v) for c, v in zip(lay["columns"], lay["ceiling_y"]) if v >= 0]
    if ceil:
        cy = np.interp(xs / W, [c for c, _ in ceil], [v for _, v in ceil]) * H
        out[(rows <= cy[None, :]) & (out == BEHIND_WALL)] = BEHIND_CEILING
    return out


# ---- 1. clean plate ----------------------------------------------------------

def _erase_mask(assets: Assets, scene: Dict, erase: FrozenSet[int]) -> np.ndarray:
    H, W = assets.instances.shape
    hole = np.zeros((H, W), bool)
    placements = {o["instance"]: o["placement"] for o in scene["_detections"]}
    k = max(4, int(0.009 * max(H, W)))
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1))
    for idx in erase:
        if idx not in assets.alphas:
            continue
        y0, x0, a = assets.alphas[idx]
        h, w = a.shape
        # grow inside a padded window so the margin is not cut off at the crop
        py0, px0 = max(0, y0 - k - 1), max(0, x0 - k - 1)
        py1, px1 = min(H, y0 + h + k + 1), min(W, x0 + w + k + 1)
        m = np.zeros((py1 - py0, px1 - px0), np.uint8)
        m[y0 - py0:y0 - py0 + h, x0 - px0:x0 - px0 + w] = a > 20
        m = cv2.dilate(m, kernel)
        hole[py0:py1, px0:px1] |= m.astype(bool)
        if placements.get(idx) in ("floor", "floor_flat"):
            # the contact shadow just under the piece goes too
            ys, xs = np.where(a > 20)
            bottom = y0 + ys.max()
            drop = max(3, int(0.12 * h))   # shadow and thin legs the mask missed
            xa, xb = max(0, x0 + xs.min() - k), min(W, x0 + xs.max() + k + 1)
            hole[bottom:min(H, bottom + drop), xa:xb] = True
            hole |= _legs_below(assets.original, bottom, xa, xb, h)
    return hole


def _legs_below(img: np.ndarray, bottom: int, xa: int, xb: int, h: int) -> np.ndarray:
    """Legs and feet under a piece that the segmentation left out: pixels in
    a band under it whose colour is unlike the floor beside it in the same
    row, connected to the piece's bottom edge."""
    H, W = img.shape[:2]
    out = np.zeros((H, W), bool)
    y1 = min(H, bottom + max(4, int(0.28 * h)))
    if y1 <= bottom + 1 or xb - xa < 4:
        return out
    lab = cv2.cvtColor(img[bottom:y1], cv2.COLOR_BGR2LAB).astype(np.float32)
    side = max(8, (xb - xa) // 6)
    ref_cols = np.r_[max(0, xa - side):xa, xb:min(W, xb + side)]
    if len(ref_cols) < 4:
        return out
    ref = np.median(lab[:, ref_cols], axis=1)                    # floor colour per row
    diff = np.sqrt(((lab[:, xa:xb] - ref[:, None, :]) ** 2).sum(2))
    cand = (diff > 16).astype(np.uint8)
    cand = cv2.morphologyEx(cand, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    n, lbl, stats, _ = cv2.connectedComponentsWithStats(cand, 8)
    keep = np.zeros_like(cand, bool)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_TOP] <= 2:               # legs, feet and the contact shadow hang from the piece
            keep |= lbl == i
    keep = cv2.dilate(keep.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    out[bottom:y1, xa:xb] = keep
    return out


def _fill_from(values: np.ndarray, known: np.ndarray, radius: int = 5,
               need: Optional[np.ndarray] = None, pad: int = 24) -> np.ndarray:
    """Fills the unknown pixels of a small float image (any sign) from the
    known ones (Telea inpainting, per channel). With `need`, only a window
    around those pixels is solved."""
    if need is not None and need.any():
        ys, xs = np.where(need)
        y0, y1 = max(0, ys.min() - pad), min(values.shape[0], ys.max() + pad + 1)
        x0, x1 = max(0, xs.min() - pad), min(values.shape[1], xs.max() + pad + 1)
        out = values.copy()
        out[y0:y1, x0:x1] = _fill_from(values[y0:y1, x0:x1], known[y0:y1, x0:x1], radius)
        return out
    unknown = (~known).astype(np.uint8)
    if not unknown.any() or not known.any():
        return values
    lo, hi = float(values[known].min()), float(values[known].max())
    scale = 255.0 / max(hi - lo, 1e-3)
    out = np.empty_like(values)
    for c in range(values.shape[2]):
        ch = np.clip((values[..., c] - lo) * scale, 0, 255).astype(np.uint8)
        out[..., c] = cv2.inpaint(ch, unknown, radius, cv2.INPAINT_TELEA).astype(np.float32) / scale + lo
    return out


def clean_plate(assets: Assets, scene: Dict, erase: FrozenSet[int]) -> Tuple[np.ndarray, Optional[np.ndarray]]:
    """(photo with the erased objects removed, mask of the removed area)."""
    if not erase:
        return assets.original, None
    with assets.lock:
        if erase in assets.plates:
            assets.plates.move_to_end(erase)
            return assets.plates[erase]
    img = assets.original
    imgf = img.astype(np.float32)
    H, W = img.shape[:2]
    hole = _erase_mask(assets, scene, erase)
    behind = behind_map(scene, H, W)
    surface_ids = [s["instance"] for s in scene["surfaces"]]
    bare = np.isin(assets.instances, surface_ids)

    # 1. smooth lighting, solved at quarter size, each surface only from itself
    #    (the floor is never filled with wall colour or the other way round)
    s = 0.25
    sw, sh = max(1, int(W * s)), max(1, int(H * s))
    small = cv2.resize(imgf, (sw, sh), interpolation=cv2.INTER_AREA)
    s_hole = cv2.resize(hole.astype(np.uint8), (sw, sh), interpolation=cv2.INTER_NEAREST)
    s_hole = cv2.dilate(s_hole, np.ones((3, 3), np.uint8)).astype(bool)
    s_behind = cv2.resize(behind, (sw, sh), interpolation=cv2.INTER_NEAREST)
    s_bare = cv2.resize(bare.astype(np.uint8), (sw, sh), interpolation=cv2.INTER_NEAREST).astype(bool)
    low_small = small.copy()
    classes = np.unique(s_behind[s_hole])
    for cls in classes:
        known = ~s_hole & (s_behind == cls) & s_bare
        if known.sum() < 20:
            known = ~s_hole
        sel = s_hole & (s_behind == cls)
        filled = _fill_from(small, known, need=sel)
        low_small[sel] = filled[sel]
    low = cv2.resize(low_small, (W, H), interpolation=cv2.INTER_CUBIC)

    # 2. match the fill to the photo at the hole's edge (per surface), so no
    #    seam shows where the fill meets the untouched photo
    ring = cv2.dilate(hole.astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool) & ~hole & bare
    resid = np.where(ring[..., None], imgf - low, 0).astype(np.float32)
    r_small = cv2.resize(resid, (sw, sh), interpolation=cv2.INTER_AREA)
    r_known = cv2.resize(ring.astype(np.float32), (sw, sh), interpolation=cv2.INTER_AREA)
    r_small = r_small / np.maximum(r_known, 1e-3)[..., None]
    offset = np.zeros_like(r_small)
    for cls in classes:
        known = (r_known > 0.25) & (s_behind == cls)
        if known.sum() < 5:
            continue
        sel = s_hole & (s_behind == cls)
        filled = _fill_from(r_small, known, 9, need=sel)
        offset[sel] = filled[sel]
    low += cv2.resize(cv2.GaussianBlur(offset, (0, 0), 1.0), (W, H), interpolation=cv2.INTER_CUBIC)

    # 3. fine texture. Floor: copied from the same image row (same distance
    #    from the camera, so planks and tiles keep their scale), never across
    #    strong edges. Wall/ceiling: a fine grain matched to the wall around.
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    grad = np.abs(cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)) + np.abs(cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3))
    detail_src = np.clip(imgf - cv2.GaussianBlur(imgf, (0, 0), 3.0), -14, 14)
    detail = np.zeros_like(imgf)
    floor_hole = hole & (behind == BEHIND_FLOOR)
    floor_fill, floor_got = None, None
    if floor_hole.any():
        cam = geometry.camera(scene)
        floor_ok = (~hole) & bare & (behind == BEHIND_FLOOR) & (grad < 90)
        floor_fill, floor_got = _floor_mirror(imgf, floor_hole, floor_ok, cam)
    rng = np.random.default_rng(sum(sorted(erase)))
    for cls in (BEHIND_WALL, BEHIND_CEILING):
        sel = hole & (behind == cls)
        near = ring & (behind == cls)
        if sel.any() and near.sum() > 30:
            sd = detail_src[near].std(0)
            grain = cv2.GaussianBlur(rng.standard_normal((H, W, 3)).astype(np.float32), (0, 0), 0.6) * 1.6
            detail[sel] = (grain * sd[None, None, :])[sel]
    fill = low + detail
    if floor_fill is not None:
        fill[floor_got] = floor_fill[floor_got]
    _wall_base_rows(fill, imgf, hole, behind, bare, scene)
    soft = cv2.GaussianBlur(hole.astype(np.float32), (0, 0), 1.5)[..., None]
    plate = imgf * (1 - soft) + fill * soft
    plate = np.clip(plate, 0, 255).astype(np.uint8)
    with assets.lock:
        assets.plates[erase] = (plate, hole)
        while len(assets.plates) > 12:
            assets.plates.popitem(last=False)
    return plate, hole

def _wall_base_rows(fill: np.ndarray, imgf: np.ndarray, hole: np.ndarray, behind: np.ndarray,
                    bare: np.ndarray, scene: Dict) -> None:
    """The bottom of the wall (skirting board, the seam with the floor) is
    horizontal: in the removed area it is continued row by row from the
    clean wall on both sides instead of being blurred."""
    H, W = hole.shape
    xs = np.arange(W)
    seam = np.interp(xs / W, scene["layout"]["columns"], scene["layout"]["floor_y"]) * H
    band = max(4, int(0.03 * H))
    for y in np.where((hole & (behind == BEHIND_WALL)).any(1))[0]:
        near_seam = (seam - band <= y) & (y < seam + 2)
        need = hole[y] & (behind[y] == BEHIND_WALL) & near_seam
        if not need.any():
            continue
        known = ~hole[y] & bare[y] & (behind[y] == BEHIND_WALL)
        if known.sum() < 6:
            continue
        kx = np.flatnonzero(known)
        # fades in towards the seam, so the band has no visible top edge
        w = np.clip(1 - (seam[need] - y) / band, 0, 1)[:, None] ** 0.7
        row = np.stack([np.interp(xs[need], kx, cv2.blur(imgf[y:y + 1, :, c], (5, 1))[0, kx]) for c in range(3)], 1)
        fill[y, need] = fill[y, need] * (1 - w) + row * w


def _floor_mirror(src_img: np.ndarray, floor_hole: np.ndarray, floor_ok: np.ndarray,
                  cam: Camera) -> Tuple[np.ndarray, np.ndarray]:
    """Floor for the removed area, continued along the floor's own lines.
    The floor is resampled so that lines running away from the camera (plank
    joints, tile rows) become vertical columns; there each gap is filled by
    mirroring the clean floor just in front of it (or behind it), then the
    result is mapped back. Planks stay straight and keep their width and the
    floor's own colour and grain continue, instead of the zig-zag a sideways
    copy makes. Returns (image, where it was filled)."""
    H, W = floor_hole.shape
    out = np.zeros_like(src_img)
    got = np.zeros((H, W), bool)
    ys, xs = np.nonzero(floor_hole)
    y_top = max(int(cam.horizon) + 3, 0)
    if y_top >= H - 2:
        return out, got
    detail_src = src_img
    rows = np.arange(y_top, H, dtype=np.float32)
    dv = rows - cam.horizon
    # u = (x - vx) / (y - horizon) is constant along a line to the vanishing point
    u_lo = float(((0 - cam.vx) / dv).min())
    u_hi = float(((W - 1 - cam.vx) / dv).max())
    hole_u = (xs - cam.vx) / np.maximum(ys - cam.horizon, 1.0)
    u_lo = max(u_lo, float(hole_u.min()) - 0.5)
    u_hi = min(u_hi, float(hole_u.max()) + 0.5)
    nu = int(np.clip(W * 1.2, 64, 2400))
    us = np.linspace(u_lo, u_hi, nu, dtype=np.float32)
    map_x = (cam.vx + us[None, :] * dv[:, None]).astype(np.float32)
    map_y = np.repeat(rows[:, None], nu, 1).astype(np.float32)
    inside = (map_x >= 0) & (map_x <= W - 1)
    low_src = cv2.GaussianBlur(detail_src, (0, 0), 3.0)
    hp_src = np.clip(detail_src - low_src, -18, 18)
    rect_low = cv2.remap(low_src, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rect_hp = cv2.remap(hp_src, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    rect_ok = cv2.remap(floor_ok.astype(np.uint8), map_x, map_y, cv2.INTER_NEAREST) > 0
    rect_ok &= inside
    rect_ok = cv2.erode(rect_ok.astype(np.uint8), np.ones((3, 1), np.uint8)).astype(bool)   # skip edge pixels
    R = len(rows)
    idx = np.arange(R)[:, None].repeat(nu, 1)
    col = np.arange(nu)[None, :].repeat(R, 0)
    # nearest clean row in front (below in the picture), else behind
    below = np.where(rect_ok, idx, R)
    below = np.minimum.accumulate(below[::-1], axis=0)[::-1]
    above = np.where(rect_ok, idx, -1)
    above = np.maximum.accumulate(above, axis=0)
    has_b, has_a = below < R, above >= 0
    edge = np.where(has_b, below, np.where(has_a, above, idx))
    # tone: the floor's colour at that edge, continued along the line
    # (sampled a little away from the edge: right at it the floor often
    # still carries the removed piece's shadow or reflection)
    step = max(4, R // 25)
    away = np.clip(np.where(has_b, edge + step, edge - step), 0, R - 1)
    away = np.where(np.take_along_axis(rect_ok, away, 0), away, edge)
    low = rect_low[np.clip(away, 0, R - 1), col]
    # grain: mirrored across the edge
    src = np.clip(2 * edge - idx, 0, R - 1)
    src_ok = np.take_along_axis(rect_ok, src, 0)
    grain = np.where(src_ok[..., None], rect_hp[src, col], 0)
    rect_fill = low + grain
    rect_got = (has_b | has_a).astype(np.float32)
    # back to the photo: (x, y) -> (u index, row)
    hu = (hole_u - u_lo) / (u_hi - u_lo) * (nu - 1)
    hv = ys - y_top
    good = (ys >= y_top) & (hu >= 0) & (hu <= nu - 1)
    rect_fill = np.dstack([rect_fill, rect_got])
    px, py = hu[good].astype(np.float32), hv[good].astype(np.float32)
    back = np.empty((len(px), 4), np.float32)
    for k in range(0, len(px), 30000):          # remap maps must stay under 32767 wide
        back[k:k + 30000] = cv2.remap(rect_fill, px[k:k + 30000].reshape(1, -1), py[k:k + 30000].reshape(1, -1),
                                      cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)[0]
    ok = back[:, 3] > 0.99
    out[ys[good][ok], xs[good][ok]] = back[ok, :3]
    got[ys[good][ok], xs[good][ok]] = True
    return out, got


# ---- 2. surfaces ---------------------------------------------------------------

def surface_uv(scene: Dict, surface: Dict, cam: Camera, y0: int, x0: int, h: int, w: int):
    """Real-world texture coordinates (metres) for each pixel of a surface,
    and the size of one pixel there (for fading fine patterns far away)."""
    yy, xx = np.mgrid[y0:y0 + h, x0:x0 + w].astype(np.float64)
    if surface["type"] == "floor":
        dy = np.maximum(yy - cam.horizon, 0.5)
        Z = np.minimum(cam.f * cam.eye_height_m / dy, 25.0)
        return (xx - cam.vx) * Z / cam.f, Z, Z / cam.f
    if surface["type"] == "wall":
        return _wall_uv(scene, surface, cam, yy, xx, x0, w)
    mpp = 3.0 / cam.f
    return xx * mpp, yy * mpp, np.full(yy.shape, mpp)


def _wall_uv(scene: Dict, surface: Dict, cam: Camera, yy, xx, x0: int, w: int):
    """A wall is a vertical plane standing on a straight line of the floor.
    That line is fitted to the wall/floor seam under this wall section; then
    u runs along the wall and v down from the seam, both in metres, so
    bricks and panels stay straight and shrink correctly with distance."""
    W, H = geometry.size(scene)
    lay = scene["layout"]
    cols = np.array(lay["columns"]) * W
    seam = np.array(lay["floor_y"]) * H
    b = surface["bbox"]
    sel = (cols >= b["x"] * W) & (cols <= (b["x"] + b["w"]) * W)
    if sel.sum() < 3:
        sel = np.ones_like(cols, bool)
    slope, icpt = np.polyfit(cols[sel], seam[sel], 1)
    xs = np.arange(x0, x0 + w, dtype=np.float64)
    ys = np.maximum(slope * xs + icpt, cam.horizon + 2)
    Z = np.minimum(cam.f * cam.eye_height_m / (ys - cam.horizon), 25.0)
    X = (xs - cam.vx) * Z / cam.f
    d = np.array([X[-1] - X[0], Z[-1] - Z[0]])
    d = d / np.linalg.norm(d) if np.linalg.norm(d) > 1e-6 else np.array([1.0, 0.0])
    u = (X - X[0]) * d[0] + (Z - Z[0]) * d[1] + X[0]
    v = (yy - ys[None, :]) * Z[None, :] / cam.f
    return np.broadcast_to(u[None, :], yy.shape), v, np.broadcast_to((Z / cam.f)[None, :], yy.shape)


def apply_surfaces(canvas: np.ndarray, plate: np.ndarray, assets: Assets, scene: Dict,
                   erase_hole: Optional[np.ndarray], cam: Camera, erase: FrozenSet[int] = frozenset()) -> None:
    H, W = canvas.shape[:2]
    for s in scene["surfaces"]:
        ap = s["appearance"]
        if (ap.get("material") or "original") == "original" and not ap.get("color"):
            continue
        key = (s["instance"], ap.get("material"), ap.get("color"), erase, s["type"])
        with assets.lock:
            hit = assets.surfaces.get(key)
            if hit is not None:
                assets.surfaces.move_to_end(key)
        if hit is None:
            hit = _surface_patch(plate, assets, scene, erase_hole, cam, s)
            with assets.lock:
                assets.surfaces[key] = hit
                while len(assets.surfaces) > 16:
                    assets.surfaces.popitem(last=False)
        if hit[0] is None:
            continue
        (y0, y1, x0, x1), new, wgt = hit
        canvas[y0:y1, x0:x1] = canvas[y0:y1, x0:x1] * (1 - wgt) + new * wgt


def _cached(assets: Assets, key: tuple, make, limit: int = 160):
    with assets.lock:
        if key in assets.textures:
            assets.textures.move_to_end(key)
            return assets.textures[key]
    value = make()
    with assets.lock:
        assets.textures[key] = value
        while len(assets.textures) > limit:
            assets.textures.popitem(last=False)
    return value


def _surface_extent(assets: Assets, scene: Dict, s: Dict, behind: np.ndarray, walls: List[Dict]) -> np.ndarray:
    """Every pixel this surface could ever cover: its own pixels plus
    everything behind furniture that belongs to it."""
    H, W = behind.shape
    cls = {"wall": BEHIND_WALL, "floor": BEHIND_FLOOR, "ceiling": BEHIND_CEILING}[s["type"]]
    region = (assets.instances == s["instance"]) | ((behind == cls) & ~np.isin(
        assets.instances, [o["instance"] for o in scene["surfaces"] if o["instance"] != s["instance"]]))
    if s["type"] == "wall" and len(walls) > 1:
        region &= (_wall_owner(walls, W) == walls.index(s))[None, :] | (assets.instances == s["instance"])
    return region


def _surface_patch(plate: np.ndarray, assets: Assets, scene: Dict, erase_hole: Optional[np.ndarray],
                   cam: Camera, s: Dict):
    """(box, new pixels, weight) of one re-styled surface, or (None,...)."""
    H, W = plate.shape[:2]
    walls = [w for w in scene["surfaces"] if w["type"] == "wall"]
    ap = s["appearance"]
    behind = behind_map(scene, H, W)
    extent = _cached(assets, ("extent", s["instance"], s["type"]),
                     lambda: _surface_extent(assets, scene, s, behind, walls))
    region = assets.instances == s["instance"]
    if erase_hole is not None and erase_hole.any():
        region = region | (erase_hole & extent)
    if not region.any():
        return None, None, None
    ys, xs = np.where(extent)
    ey0, ey1, ex0, ex1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    ys, xs = np.where(region)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    weight = cv2.GaussianBlur(region[y0:y1, x0:x1].astype(np.float32), (3, 3), 0)
    crop = plate[y0:y1, x0:x1]
    material = ap.get("material") or "original"
    tex = fp = None
    if material != "original":
        def make():
            u, v, f = surface_uv(scene, s, cam, ey0, ex0, ey1 - ey0, ex1 - ex0)
            t = texture_fast(material, np.ascontiguousarray(u), np.ascontiguousarray(v), ap.get("color"))
            return t, np.ascontiguousarray(f, dtype=np.float32)
        full_tex, full_fp = _cached(assets, ("surface", s["instance"], material, ap.get("color")), make)
        tex = full_tex[y0 - ey0:y1 - ey0, x0 - ex0:x1 - ex0]
        fp = full_fp[y0 - ey0:y1 - ey0, x0 - ex0:x1 - ex0]
    detail = {"floor": 0.15, "wall": 0.35, "ceiling": 0.3}[s["type"]]
    new = appearance_pixels(crop, weight, ap, None, detail, tex=tex)
    if new is None:
        return None, None, None
    if fp is not None:
        # far away the pattern is finer than a pixel: fade to its average
        fade = np.clip((fp - 0.004) / 0.012, 0, 1)[..., None].astype(np.float32)
        inside = weight > 0.5
        mean = new[inside].mean(0) if inside.any() else new.reshape(-1, 3).mean(0)
        new = new * (1 - fade) + mean[None, None, :] * fade
    return (y0, y1, x0, x1), new.astype(np.float32), weight[..., None]


def _wall_owner(walls: List[Dict], W: int) -> np.ndarray:
    xs = (np.arange(W) + 0.5) / W
    owner = np.zeros(W, np.int32)
    for i, s in enumerate(walls):
        b = s["bbox"]
        inside = (xs >= b["x"]) & (xs <= b["x"] + b["w"])
        owner[inside] = i
    return owner


# ---- 3. objects ------------------------------------------------------------------

def _composite(canvas: np.ndarray, rgb: np.ndarray, alpha: np.ndarray, y0: int, x0: int) -> None:
    H, W = canvas.shape[:2]
    h, w = alpha.shape
    ya, xa = max(0, y0), max(0, x0)
    yb, xb = min(H, y0 + h), min(W, x0 + w)
    if ya >= yb or xa >= xb:
        return
    a = alpha[ya - y0:yb - y0, xa - x0:xb - x0, None]
    canvas[ya:yb, xa:xb] = canvas[ya:yb, xa:xb] * (1 - a) + rgb[ya - y0:yb - y0, xa - x0:xb - x0] * a


def _shadow(canvas: np.ndarray, poly: np.ndarray, strength: float, blur: float) -> None:
    H, W = canvas.shape[:2]
    x0, y0 = np.floor(poly.min(0) - 3 * blur).astype(int)
    x1, y1 = np.ceil(poly.max(0) + 3 * blur).astype(int)
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x0 >= x1 or y0 >= y1:
        return
    m = np.zeros((y1 - y0, x1 - x0), np.float32)
    cv2.fillPoly(m, [np.round((poly - [x0, y0]) * 4).astype(np.int32)], 1.0, lineType=cv2.LINE_AA, shift=2)
    m = cv2.GaussianBlur(m, (0, 0), max(0.8, blur))
    canvas[y0:y1, x0:x1] *= (1 - strength * m)[..., None]


def draw_photo_object(canvas: np.ndarray, obj: Dict, assets: Assets, scene: Dict, cam: Camera) -> None:
    idx = obj["instance"]
    if idx not in assets.alphas:
        return
    H, W = canvas.shape[:2]
    y0, x0, a = assets.alphas[idx]
    h, w = a.shape
    crop = assets.original[y0:y0 + h, x0:x0 + w]
    alpha = a.astype(np.float32) / 255.0
    rgb = crop.astype(np.float32)
    mpp = cam.metres_per_px(obj["original"]["anchor"]["y"] * H) if obj["placement"] == "floor" else 0.004
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    new = appearance_pixels(crop, alpha, obj["appearance"], (xx * mpp, yy * mpp), 0.75)
    if new is not None:
        rgb = new.astype(np.float32)
    if not geometry.is_displaced(obj):
        _composite(canvas, rgb, alpha, y0, x0)
        return
    M = geometry.photo_matrix(obj, cam, W, H)
    corners = np.array([[x0, y0], [x0 + w, y0], [x0 + w, y0 + h], [x0, y0 + h]], np.float64)
    dst = corners @ M[:, :2].T + M[:, 2]
    dx0, dy0 = np.floor(dst.min(0)).astype(int) - 1
    dx1, dy1 = np.ceil(dst.max(0)).astype(int) + 1
    dx0, dy0, dx1, dy1 = max(0, dx0), max(0, dy0), min(W, dx1), min(H, dy1)
    if dx0 >= dx1 or dy0 >= dy1:
        return
    # sprite pixel (i, j) -> original (x0 + j, y0 + i) -> destination - ROI origin
    Mroi = M.copy()
    Mroi[:, 2] = M[:, :2] @ np.array([x0, y0]) + M[:, 2] - np.array([dx0, dy0])
    rgba = np.dstack([rgb, alpha * 255.0]).astype(np.float32)
    warped = cv2.warpAffine(rgba, Mroi, (dx1 - dx0, dy1 - dy0), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    if obj["placement"] in ("floor",):
        px, py = obj["transform"]["position"]["x"] * W, obj["transform"]["position"]["y"] * H
        bw = (dst[:, 0].max() - dst[:, 0].min())
        ang = np.linspace(0, 2 * np.pi, 32)
        ell = np.stack([px + bw * 0.47 * np.cos(ang), py - bw * 0.012 + bw * 0.045 * np.sin(ang)], 1)
        _shadow(canvas, ell, 0.38, max(1.5, bw * 0.025))
    _composite(canvas, warped[..., :3], warped[..., 3] / 255.0, dy0, dx0)


ROLE_COLORS = {
    "screen": "#0d0f12", "screen_frame": "#18181a", "shade": "#f3e7cf", "pot": "#e9e4dc",
    "leaf0": "#3f7a45", "leaf1": "#4f8c4a", "leaf2": "#2f6337", "pillow": "#f2efe8", "back": None,
    "stem": "#4a5d3a", "book0": "#8a3b2e", "book1": "#2c3e57", "book2": "#d4a373", "book3": "#5a6b4f", "handle": "#b8903e",
}
DARK_ACCENT = {"wood": "#4a3424", "metal": "#1e1e1e"}


ROLE_COLORS.update({"mattress": "#f1eee8", "throw": None, "shade_dark": None, "bulb": "#fff6de",
                    "basket": "#b08a5a", "stone": "#e4e1dc", "base": "#e9e4dc", "mirror": "#c7d3d9",
                    "glass": "#cfe3e8", "frame": None, "frame_leg": None})
WOOD_OR_METAL = {"wood": "wood_walnut", "oak": "wood_oak", "walnut": "wood_walnut", "white": "white_wood",
                 "black": "metal_black", "brass": "metal_brass", "steel": "metal_steel"}


def _role_material(obj: Dict, role: str) -> Tuple[str, Optional[str], float]:
    """(material, colour, brightness factor) for a model part. The library
    item's parameters say what the fixed parts are made of (legs, metal,
    bed frame, secondary colour)."""
    ap = obj["appearance"]
    mat = ap.get("material") or "fabric"
    color = ap.get("color")
    _, params = geometry.model_spec(obj)
    if role in ("main", "back", "detail"):
        f = {"main": 1.0, "back": 0.85, "detail": 0.62}[role]
        return mat, color, f
    if role == "rug":
        return "carpet", color, 1.0
    if role == "cushion":
        cm = params.get("cushion_material")
        return (cm or mat), (params.get("cushion_color") or color), 1.06
    if role in ("leg", "accent", "frame_leg"):
        key = params.get("legs_material") or ("black" if mat.startswith("metal") else "wood")
        return WOOD_OR_METAL.get(key, "wood_walnut"), None, 1.0
    if role == "metal":
        return WOOD_OR_METAL.get(params.get("metal", "black"), "metal_black"), None, 1.0
    if role == "frame":
        fm = params.get("frame_material")
        return (WOOD_OR_METAL.get(fm, mat) if fm else mat), (None if fm else color), 0.95
    if role == "throw":
        return "fabric", params.get("throw_color", "#8a7968"), 1.0
    if role in ("shade", "shade_dark"):
        if role == "shade_dark" or params.get("shade_color"):
            return "painted", params.get("shade_color") or color or "#2b2b2b", 1.0
        return "linen", params.get("shade_color") or "#f3e7cf", 1.0
    if role in ("glass", "mirror", "stone", "base", "bulb", "mattress", "basket"):
        if role == "stone":
            return "marble_white", None, 1.0
        if role == "base" and params.get("base_color"):
            return "painted", params["base_color"], 1.0
        return "painted", ROLE_COLORS[role], 1.0
    if role == "pot":
        return "painted", params.get("pot_color", ROLE_COLORS["pot"]), 1.0
    return "painted", ROLE_COLORS.get(role) or "#808080", 1.0


def _white_balance(original: np.ndarray) -> np.ndarray:
    wb = original.reshape(-1, 3).mean(0)
    wb = wb / max(wb.mean(), 1)
    return 1 + 0.35 * (wb - 1)


def mesh_context(scene: Dict, assets: Optional[Assets], cam: Camera, erase: FrozenSet[int] = frozenset(),
                 quality: str = "1k", S: int = 2, backdrop: Optional[np.ndarray] = None) -> Dict:
    """What drawing real 3D models needs: the room's light, what is behind
    each pixel and which pixels are bare floor/wall (they receive shadows)."""
    W, H = geometry.size(scene)
    if assets is None:                        # library previews: studio light
        return {"light": lighting.studio(cam, H, W, backdrop if backdrop is not None
                                         else np.full((H, W, 3), 220, np.uint8)),
                "behind": behind_map(scene, H, W), "receivers": np.ones((H, W), bool),
                "quality": quality, "S": S, "erase": erase}
    detected = {d["instance"] for d in scene.get("_detections") or [] if d.get("instance")}
    furniture = _cached(assets, ("furniture_mask",), lambda: np.isin(assets.instances, sorted(detected)))
    light = _cached(assets, ("room_light",), lambda: lighting.estimate(scene, assets.original, furniture, cam))
    behind = _cached(assets, ("behind",), lambda: behind_map(scene, H, W))
    kept = sorted(detected - set(erase))
    free = ~np.isin(assets.instances, kept) if kept else np.ones((H, W), bool)
    return {"light": light, "behind": behind, "receivers": free, "quality": quality, "S": S, "erase": erase}


def draw_mesh(canvas: np.ndarray, obj: Dict, scene: Dict, cam: Camera, assets: Optional[Assets], ctx: Dict) -> None:
    """A real 3D model: its shadow on the room, then the model itself. The
    rendered model is cached by its own state; its shadow also depends on
    which photo pieces are gone (bare floor receives it)."""
    H, W = canvas.shape[:2]
    light = ctx["light"]
    key = mesh_render.state_key(obj, ctx["quality"], ctx["S"], light)
    shadow_key = key + "|" + ",".join(map(str, sorted(ctx["erase"])))
    cache = assets.layers if assets is not None else None
    layer = cache.get(key) if cache is not None else None
    if layer is None:
        try:
            layer = mesh_render.render_layer(obj, cam, W, H, light, ctx["quality"], ctx["S"])
        except FileNotFoundError:
            return
        if layer is None:
            return
        layer["shadows"] = {}
        if cache is not None:
            with assets.lock:
                cache[key] = layer
                while len(cache) > 24:
                    cache.popitem(last=False)
    if obj["placement"] == "surface":
        # it stands on a photographed piece (no geometry to cast onto): a soft contact shadow
        foot, _ = geometry.model_footprint(obj, cam, W, H)
        fw = max(3.0, float(np.ptp(foot[:, 0])))
        _shadow(canvas, foot.mean(0) + (foot - foot.mean(0)) * 1.15, 0.45, fw * 0.06)
    elif obj["placement"] != "ceiling":
        if shadow_key not in layer["shadows"]:
            layer["shadows"] = {shadow_key: mesh_render.room_shadow(layer, obj, scene, cam, light, ctx["behind"],
                                                                     ctx["receivers"], W, H)}
        shadow = layer["shadows"][shadow_key]
        if shadow is not None:
            dark, sx, sy = shadow
            h, w = dark.shape
            canvas[sy:sy + h, sx:sx + w] *= dark[..., None]
    _composite(canvas, layer["rgb"], layer["alpha"], layer["y0"], layer["x0"])


def draw_model(canvas: np.ndarray, obj: Dict, scene: Dict, cam: Camera, room_light: float,
               wb: np.ndarray, assets: Optional[Assets] = None, ctx: Optional[Dict] = None) -> None:
    H, W = canvas.shape[:2]
    if geometry.is_mesh_item(obj):
        if ctx is None:
            ctx = mesh_context(scene, assets, cam, S=1 if assets is None else 2,
                               backdrop=np.clip(canvas, 0, 255).astype(np.uint8))
        return draw_mesh(canvas, obj, scene, cam, assets, ctx)
    generator, params = geometry.model_spec(obj)
    if geometry.is_image_item(obj):
        return draw_image_item(canvas, obj, scene, cam, room_light, wb)
    if geometry.is_wall_item(obj):
        quad = geometry.wall_panel(obj, cam, scene)
        return wall2d.draw(canvas, obj, generator, params, quad, room_light, wb)
    faces = geometry.model_faces(obj, cam, W, H)
    if not faces:
        return
    foot, _ = geometry.model_footprint(obj, cam, W, H)
    fw = max(4.0, float(np.ptp(foot[:, 0])))
    if generator != "rug" and obj["placement"] != "ceiling":
        grown = foot.mean(0) + (foot - foot.mean(0)) * 1.08
        _shadow(canvas, grown, 0.5 if obj["placement"] == "floor" else 0.35, fw * 0.03)
    pts_all = np.vstack([f["pts"] for f in faces])
    x0, y0 = np.floor(pts_all.min(0)).astype(int) - 2
    x1, y1 = np.ceil(pts_all.max(0)).astype(int) + 2
    x0c, y0c, x1c, y1c = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x0c >= x1c or y0c >= y1c:
        return
    S = 2   # supersampling for smooth edges
    hh, ww = (y1c - y0c) * S, (x1c - x0c) * S
    layer = np.zeros((hh, ww, 3), np.float32)
    alpha = np.zeros((hh, ww), np.float32)
    origin = np.array([x0c, y0c], np.float64)
    top_y = max([p[1] for f in faces for p in f["local"]] or [1.0]) or 1.0
    for face in faces:
        if face.get("foliage"):
            _draw_foliage(layer, alpha, face, origin, S, room_light, wb, obj["id"], params)
            continue
        pts = (face["pts"] - origin) * S
        fx0, fy0 = np.floor(pts.min(0)).astype(int) - 1
        fx1, fy1 = np.ceil(pts.max(0)).astype(int) + 2
        fx0, fy0, fx1, fy1 = max(0, fx0), max(0, fy0), min(ww, fx1), min(hh, fy1)
        if fx0 >= fx1 or fy0 >= fy1:
            continue
        local = pts - [fx0, fy0]
        mat, color, factor = _role_material(obj, face["role"])
        lam = max(0.0, float(np.dot(face["normal"], LIGHT_DIR)))
        shade = (0.55 + 0.5 * lam) * room_light * factor
        if face["role"] in ("shade", "bulb"):
            shade = 1.08                       # lit from inside
        glass = face["role"] in ("glass",)
        fmask = np.zeros((fy1 - fy0, fx1 - fx0), np.float32)
        cv2.fillPoly(fmask, [np.round(local * 4).astype(np.int32)], 1.0, lineType=cv2.LINE_AA, shift=2)
        if fmask.sum() < 1:
            continue
        if face["role"] == "rug" and len(face["local"]) == 4 and fmask.sum() > 300:
            col = _rug_texture(face, local, color, params, fmask.shape)
        elif len(face["local"]) == 4 and fmask.sum() > 300:
            col = _face_texture(face, local, mat, color, fmask.shape, top_y, assets)
        else:
            col = np.broadcast_to(texture(mat, np.zeros((1, 1)), np.zeros((1, 1)), color)[0, 0], fmask.shape + (3,))
        col = np.ascontiguousarray(col * shade * wb[None, None, :], dtype=np.float32)
        # a slightly darker rim gives each panel definition
        rim = (col.reshape(-1, 3).mean(0) * 0.72).tolist()
        cv2.polylines(col, [np.round(local * 4).astype(np.int32)], True, rim, 1, cv2.LINE_AA, shift=2)
        if glass:
            fmask = fmask * 0.35
        fm = fmask[..., None]
        sub = layer[fy0:fy1, fx0:fx1]
        sub[:] = sub * (1 - fm) + col * fm
        np.maximum(alpha[fy0:fy1, fx0:fx1], fmask, out=alpha[fy0:fy1, fx0:fx1])
    layer = cv2.resize(layer, (x1c - x0c, y1c - y0c), interpolation=cv2.INTER_AREA)
    alpha = cv2.resize(alpha, (x1c - x0c, y1c - y0c), interpolation=cv2.INTER_AREA)
    _composite(canvas, np.clip(layer, 0, 255), alpha, y0c, x0c)


_images: "OrderedDict[str, np.ndarray]" = OrderedDict()


def _asset_image(rel: str) -> Optional[np.ndarray]:
    """BGRA pixels of a library 2D asset (cached)."""
    from .library import DATA_DIR
    if rel in _images:
        return _images[rel]
    path = os.path.normpath(os.path.join(DATA_DIR, rel))
    if not path.startswith(os.path.normpath(DATA_DIR)) or not os.path.isfile(path):
        return None
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        return None
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA)
    elif img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    _images[rel] = img
    while len(_images) > 32:
        _images.popitem(last=False)
    return img


def draw_image_item(canvas: np.ndarray, obj: Dict, scene: Dict, cam: Camera, room_light: float,
                    wb: np.ndarray) -> None:
    """A cut-out picture at real size, lit like the room, with a contact
    shadow when it stands on the floor. Colour changes tint it."""
    img = _asset_image(obj["model"].get("file", ""))
    if img is None:
        return
    H, W = canvas.shape[:2]
    quad = geometry.image_quad(obj, cam, scene)
    if obj["placement"] == "floor":
        bw = float(np.ptp(quad[:, 0]))
        cx, by = quad[2:, 0].mean(), quad[2:, 1].mean()
        ang = np.linspace(0, 2 * np.pi, 32)
        _shadow(canvas, np.stack([cx + bw * 0.5 * np.cos(ang), by + bw * 0.06 * np.sin(ang)], 1), 0.4, bw * 0.03)
    x0, y0 = np.floor(quad.min(0)).astype(int) - 2
    x1, y1 = np.ceil(quad.max(0)).astype(int) + 2
    x0, y0, x1, y1 = max(0, x0), max(0, y0), min(W, x1), min(H, y1)
    if x0 >= x1 or y0 >= y1:
        return
    h, w = img.shape[:2]
    Hm = cv2.getPerspectiveTransform(np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]]),
                                     (quad - [x0, y0]).astype(np.float32))
    warped = cv2.warpPerspective(img.astype(np.float32), Hm, (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR)
    rgb = warped[..., :3] * room_light * wb[None, None, :]
    tint = obj["appearance"].get("color")
    if tint and (obj.get("model") or {}).get("tintable"):
        rgb = rgb * (hex_to_bgr(tint) / 255.0)[None, None, :] * 1.3
    _composite(canvas, np.clip(rgb, 0, 255), warped[..., 3] / 255.0, y0, x0)


LEAF_GREENS = [(69, 122, 63), (74, 140, 79), (55, 99, 47), (90, 150, 84), (48, 86, 52)]


FLOWER_COLORS = [(214, 92, 110), (240, 190, 70), (245, 245, 240), (180, 110, 200)]


def _draw_foliage(layer: np.ndarray, alpha: np.ndarray, face: Dict, origin: np.ndarray, S: int,
                  room_light: float, wb: np.ndarray, seed_text: str, params: Optional[Dict] = None) -> None:
    """A leafy cluster (leaves, palm fronds, succulent rosettes or blossoms)."""
    cx, cy = (np.array(face["center"]) - origin) * S
    r = face["radius"] * S
    if r < 2:
        return
    kind = face["role"]
    rng = np.random.default_rng(sum(map(ord, seed_text)) * 31 + face["seed"])
    count = {"frond": 14, "succulent": 16, "flower": 12}.get(kind, int(min(90, 25 + r / 3)))
    for _ in range(count):
        ang = rng.uniform(0, 2 * np.pi)
        dist = r * np.sqrt(rng.uniform(0, 1)) * (0.6 if kind == "succulent" else 1.0)
        x, y = cx + dist * np.cos(ang), cy + dist * np.sin(ang) * 0.9
        length = r * (rng.uniform(0.5, 0.8) if kind == "frond" else rng.uniform(0.22, 0.38))
        width = length * (0.12 if kind == "frond" else rng.uniform(0.3, 0.45))
        tilt = np.degrees(ang) + rng.uniform(-35, 35)
        lift = 1.0 - 0.35 * (y - (cy - r)) / (2 * r)          # lighter at the top
        if kind == "flower":
            g = np.array(FLOWER_COLORS[int(((params or {}).get("flower", 0) + rng.integers(2)) % 4)], np.float64)[::-1]
            length = width = r * rng.uniform(0.12, 0.2)
        elif kind == "succulent":
            g = np.array((120, 160, 130), np.float64)[::-1] * rng.uniform(0.85, 1.1)
        else:
            g = np.array(LEAF_GREENS[rng.integers(len(LEAF_GREENS))], np.float64)[::-1]
        col = (g * lift * room_light * rng.uniform(0.85, 1.15) * wb).tolist()
        cv2.ellipse(layer, (int(x * 4), int(y * 4)), (int(length * 2), int(width * 2)), tilt, 0, 360, col,
                    -1, cv2.LINE_AA, shift=2)
        cv2.ellipse(alpha, (int(x * 4), int(y * 4)), (int(length * 2), int(width * 2)), tilt, 0, 360, 1.0,
                    -1, cv2.LINE_AA, shift=2)


def _rug_texture(face: Dict, pts: np.ndarray, color: Optional[str], params: Dict, shape) -> np.ndarray:
    """Rug patterns (plain, border, stripes, geometric) in the rug's own
    metres, warped onto its top face."""
    v0, v1, _, v3 = (np.array(p) for p in face["local"])
    wm, hm = float(np.linalg.norm(v1 - v0)), float(np.linalg.norm(v3 - v0))
    res = int(min(320, max(24, max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))))
    tw, th = (res, max(8, int(res * hm / max(wm, 1e-3)))) if wm >= hm else (max(8, int(res * wm / max(hm, 1e-3))), res)
    uu, vv = np.meshgrid(np.linspace(0, wm, tw), np.linspace(0, hm, th))
    base = texture("carpet", uu, vv, color)
    accent = np.clip(base * 0.55, 0, 255)
    light = np.clip(base * 1.25 + 20, 0, 255)
    pattern = params.get("pattern", "plain")
    edge = np.minimum(np.minimum(uu, wm - uu), np.minimum(vv, hm - vv))
    if pattern == "border":
        band = ((edge > 0.08) & (edge < 0.16))[..., None]
        base = np.where(band, accent, base)
    elif pattern == "stripes":
        band = ((np.floor(uu / 0.18) % 2) == 0)[..., None]
        base = np.where(band, base, light)
    elif pattern == "geometric":
        d = (np.abs((uu % 0.5) - 0.25) + np.abs((vv % 0.5) - 0.25)) < 0.12
        base = np.where(d[..., None], accent, base)
        base = np.where(((edge > 0.05) & (edge < 0.1))[..., None], accent, base)
    if params.get("fringe"):
        base = np.where((np.minimum(uu, wm - uu) < 0.03)[..., None], light, base)
    src = np.float32([[0, th - 1], [tw - 1, th - 1], [tw - 1, 0], [0, 0]])
    Hm = cv2.getPerspectiveTransform(src, pts.astype(np.float32))
    return cv2.warpPerspective(base.astype(np.float32), Hm, (shape[1], shape[0]), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)


def _face_texture(face: Dict, pts: np.ndarray, mat: str, color: Optional[str], shape, top_y: float,
                  assets: Optional[Assets] = None) -> np.ndarray:
    """Texture laid on a quad face at real scale, warped into place, darker
    towards the floor on upright faces (soft ambient occlusion)."""
    v0, v1, _, v3 = (np.array(p) for p in face["local"])
    wm = max(0.01, float(np.linalg.norm(v1 - v0)))
    hm = max(0.01, float(np.linalg.norm(v3 - v0)))
    res = int(min(256, max(16, max(np.ptp(pts[:, 0]), np.ptp(pts[:, 1])))))
    tw, th = (res, max(4, int(res * hm / wm))) if wm >= hm else (max(4, int(res * wm / hm)), res)
    ou, ov = round(float(v0[0] + v0[2]), 2), round(float(v0[1]), 2)

    def make():
        uu, vv = np.meshgrid(np.linspace(0, wm, tw), np.linspace(0, hm, th))
        return texture(mat, uu + ou, vv + ov, color)
    key = ("face", mat, color, round(wm, 3), round(hm, 3), tw, th, ou, ov)
    tex = _cached(assets, key, make) if assets is not None else make()
    if abs(face["normal"][1]) < 0.5:          # upright face: y runs from v0 (bottom) to v3 (top)
        heights = np.linspace(v3[1], v0[1], th)[:, None, None]
        tex = tex * (0.8 + 0.2 * np.clip(heights / max(top_y, 0.3), 0, 1) ** 0.5)
    # texture rows run from the face's top edge (v3) down to its base (v0)
    src = np.float32([[0, th - 1], [tw - 1, th - 1], [tw - 1, 0], [0, 0]])
    Hm = cv2.getPerspectiveTransform(src, pts.astype(np.float32))
    return cv2.warpPerspective(tex, Hm, (shape[1], shape[0]), flags=cv2.INTER_LINEAR,
                               borderMode=cv2.BORDER_REPLICATE)


# ---- the whole picture -------------------------------------------------------

def erased_instances(scene: Dict) -> FrozenSet[int]:
    """Detected instances whose pixels must be removed from the photo."""
    current = {o["instance"]: o for o in scene["objects"] if o.get("instance")}
    out = set()
    for det in scene["_detections"]:
        o = current.get(det["instance"])
        if o is None or o["source"] != "detected" or geometry.is_displaced(o):
            out.add(det["instance"])
    return frozenset(out)


def render(scene: Dict, assets: Assets, quality: str = "1k") -> np.ndarray:
    """BGR uint8 image of the scene. `scene["_detections"]` must hold the
    original detected objects (the service attaches it). quality "2k" uses
    the high-quality 3D assets (when downloaded) and finer anti-aliasing,
    for the final render."""
    cam = geometry.camera(scene)
    erase = erased_instances(scene)
    plate, hole = clean_plate(assets, scene, erase)
    canvas = plate.astype(np.float32)
    apply_surfaces(canvas, plate, assets, scene, hole, cam, erase)

    lab_l = cv2.cvtColor(assets.original, cv2.COLOR_BGR2LAB)[..., 0].mean() / 255 * 100
    room_light = float(np.clip(lab_l / 62, 0.55, 1.15))
    wb = _white_balance(assets.original)
    ctx = None
    for obj in sorted(scene["objects"], key=lambda o: -o.get("depth", 0)):
        if obj["source"] == "detected":
            draw_photo_object(canvas, obj, assets, scene, cam)
        else:
            if ctx is None and geometry.is_mesh_item(obj):
                ctx = mesh_context(scene, assets, cam, erase, quality, 3 if quality != "1k" else 2)
            draw_model(canvas, obj, scene, cam, room_light, wb, assets, ctx)
    return np.clip(canvas, 0, 255).astype(np.uint8)


def object_sprite(scene: Dict, assets: Assets, object_id: str) -> Optional[Tuple[np.ndarray, Dict]]:
    """The object alone (BGRA, cropped to its current bounds) for smooth drag
    previews in the editor. Returns (image, normalised bounds)."""
    obj = next((o for o in scene["objects"] if o["id"] == object_id), None)
    if obj is None:
        return None
    H, W = assets.original.shape[:2]
    cam = geometry.camera(scene)
    canvas = np.zeros((H, W, 3), np.float32)
    marker = np.zeros((H, W, 3), np.float32)
    ones = np.full((H, W, 3), 255.0, np.float32)
    if obj["source"] == "detected":
        draw_photo_object(canvas, obj, assets, scene, cam)
        draw_photo_object(ones, obj, assets, scene, cam)
    else:
        wb = _white_balance(assets.original)
        ctx = mesh_context(scene, assets, cam, erased_instances(scene)) if geometry.is_mesh_item(obj) else None
        draw_model(canvas, obj, scene, cam, 1.0, wb, assets, ctx)
        draw_model(ones, obj, scene, cam, 1.0, wb, assets, ctx)
    # alpha from drawing on black and on white: a = 1 - (white - black) / 255
    alpha = 1 - (ones - canvas).mean(2) / 255.0
    b = obj["bounds"]
    x0, y0 = max(0, int(b["x"] * W)), max(0, int(b["y"] * H))
    x1, y1 = min(W, int(math.ceil((b["x"] + b["w"]) * W))), min(H, int(math.ceil((b["y"] + b["h"]) * H)))
    if x0 >= x1 or y0 >= y1:
        return None
    a = np.clip(alpha[y0:y1, x0:x1], 0, 1)
    col = np.where(a[..., None] > 1e-3, canvas[y0:y1, x0:x1] / np.maximum(a[..., None], 1e-3), 0)
    bgra = np.dstack([np.clip(col, 0, 255), a * 255]).astype(np.uint8)
    return bgra, {"x": x0 / W, "y": y0 / H, "w": (x1 - x0) / W, "h": (y1 - y0) / H}
