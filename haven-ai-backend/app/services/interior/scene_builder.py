"""
Layer 1 -> Layer 2: from a segmentation map to an editable scene.

  class map (per pixel)
    -> surfaces: walls (split at room corners), floor, ceiling
    -> objects: connected regions per class group, one instance each; cushions
       touching a sofa/bed become part of it; tiny specks are dropped
    -> soft object masks (GrabCut refinement around each instance)
    -> room layout: where the floor meets the walls, per column
    -> camera (camera.py), estimated real sizes, relationships

Nothing is invented: an element exists in the scene only if the model found
it. Materials of detected objects are not measured; the scene records a guess
from the object type and says so (material_source = "assumed").
"""
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import catalog
from .camera import Camera, estimate_camera

MIN_OBJECT_FRAC = 0.0015
MIN_OBJECT_PX = 300
MIN_WALL_SECTION_FRAC = 0.04
MAX_OBJECTS = 60
LAYOUT_SAMPLES = 96       # columns sampled for the floor/ceiling boundaries


def _hex(bgr) -> str:
    b, g, r = (int(round(float(v))) for v in bgr)
    return f"#{r:02x}{g:02x}{b:02x}"


def median_color(img: np.ndarray, mask: np.ndarray) -> str:
    px = img[mask]
    if len(px) == 0:
        return "#808080"
    if len(px) > 20000:
        px = px[:: len(px) // 20000]
    lab = cv2.cvtColor(px.reshape(-1, 1, 3), cv2.COLOR_BGR2LAB).reshape(-1, 3)
    med = np.median(lab, 0).astype(np.uint8).reshape(1, 1, 3)
    return _hex(cv2.cvtColor(med, cv2.COLOR_LAB2BGR)[0, 0])


def _norm_box(x, y, w, h, W, H) -> Dict[str, float]:
    return {"x": round(x / W, 4), "y": round(y / H, 4), "w": round(w / W, 4), "h": round(h / H, 4)}


def outline(mask: np.ndarray, W: int, H: int, max_points: int = 80) -> List[List[float]]:
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    c = max(contours, key=cv2.contourArea)
    eps = 0.002 * cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, eps, True)
    while len(approx) > max_points:
        eps *= 1.5
        approx = cv2.approxPolyDP(c, eps, True)
    return [[round(float(p[0][0]) / W, 4), round(float(p[0][1]) / H, 4)] for p in approx]


def refine_alpha(img: np.ndarray, mask: np.ndarray, others: np.ndarray) -> np.ndarray:
    """Soft 0..255 alpha for one object. GrabCut snaps the model's outline to
    the photo's real edges; if it strays too far from the model's mask, the
    model's mask is kept."""
    ys, xs = np.where(mask)
    H, W = mask.shape
    m = 14
    y0, y1 = max(0, ys.min() - m), min(H, ys.max() + m + 1)
    x0, x1 = max(0, xs.min() - m), min(W, xs.max() + m + 1)
    crop, cm, co = img[y0:y1, x0:x1], mask[y0:y1, x0:x1], others[y0:y1, x0:x1]
    ch, cw = cm.shape
    s = min(1.0, 360 / max(ch, cw))
    size = (max(8, round(cw * s)), max(8, round(ch * s)))
    small = cv2.resize(crop, size, interpolation=cv2.INTER_AREA)
    sm = cv2.resize(cm.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)
    so = cv2.resize(co.astype(np.uint8), size, interpolation=cv2.INTER_NEAREST).astype(bool)
    k = np.ones((5, 5), np.uint8)
    sure_fg = cv2.erode(sm.astype(np.uint8), k, iterations=1).astype(bool)
    near = cv2.dilate(sm.astype(np.uint8), k, iterations=2).astype(bool)
    gc = np.full(sm.shape, cv2.GC_BGD, np.uint8)
    gc[near] = cv2.GC_PR_BGD
    gc[sm] = cv2.GC_PR_FGD
    gc[sure_fg] = cv2.GC_FGD
    gc[so & ~sure_fg] = cv2.GC_BGD
    refined = sm
    if sure_fg.sum() > 20 and (gc == cv2.GC_BGD).sum() > 20:
        try:
            bgd, fgd = np.zeros((1, 65), np.float64), np.zeros((1, 65), np.float64)
            cv2.grabCut(small, gc, None, bgd, fgd, 3, cv2.GC_INIT_WITH_MASK)
            cand = (gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)
            ratio = cand.sum() / max(1, sm.sum())
            if 0.7 < ratio < 1.35:
                refined = cand
        except cv2.error:
            pass
    up = cv2.resize(refined.astype(np.float32), (cw, ch), interpolation=cv2.INTER_LINEAR)
    up = cv2.GaussianBlur(up, (3, 3), 0)
    out = np.zeros((H, W), np.uint8)
    out[y0:y1, x0:x1] = np.clip(up * 255, 0, 255).astype(np.uint8)
    return out


def recover_legs(img: np.ndarray, mask: np.ndarray, floor: np.ndarray) -> np.ndarray:
    """Thin legs are often missed by the model. Below the body of a floor
    piece, inside the convex hull of its outline, pixels that clearly differ
    from the floor around them and touch the body are taken as legs."""
    ys, xs = np.where(mask)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    H, W = mask.shape
    band_top = y0 + int(0.6 * (y1 - y0))
    band_bot = min(H, y1 + max(3, int(0.08 * (y1 - y0))))
    pts = np.vstack([np.column_stack([xs, ys]), [[x0, band_bot - 1], [x1 - 1, band_bot - 1]]]).astype(np.int32)
    hull = np.zeros((H, W), np.uint8)
    cv2.fillConvexPoly(hull, cv2.convexHull(pts), 1)
    cand = hull.astype(bool) & ~mask
    cand[:band_top] = False
    cand[band_bot:] = False
    ry0, ry1 = band_top, min(H, band_bot + 20)
    rx0, rx1 = max(0, x0 - 20), min(W, x1 + 20)
    ref = floor[ry0:ry1, rx0:rx1]
    if not cand.any() or ref.sum() < 30:
        return np.zeros_like(mask)
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    floor_lab = np.median(lab[ry0:ry1, rx0:rx1][ref], 0)
    diff = np.linalg.norm(lab - floor_lab, axis=2)
    legs = (cand & (diff > 28)).astype(np.uint8)
    legs = cv2.morphologyEx(legs, cv2.MORPH_OPEN, np.ones((3, 1), np.uint8))
    n, cc, stats, _ = cv2.connectedComponentsWithStats(legs, connectivity=8)
    near_body = cv2.dilate(mask.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
    out = np.zeros_like(mask)
    for i in range(1, n):
        bw, bh = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]
        thin = bw <= max(6, 0.08 * (x1 - x0)) and bh >= 1.5 * bw     # a leg, not a shadow
        blob = cc == i
        if thin and stats[i, cv2.CC_STAT_AREA] >= 12 and (blob & near_body).any():
            out |= blob
    return out

def drop_foreign_pixels(img: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """Removes things the model mistook for wall/ceiling (a thin lamp pole, a
    light switch, cables): pixels clearly darker than the wall around them or
    of a clearly different hue, in blobs big enough not to be noise. Shadows
    and gradients on the wall are only moderately darker, so they stay."""
    if mask.sum() < 500:
        return mask
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB).astype(np.float32)
    L = lab[..., 0]
    w = mask.astype(np.float32)
    sigma = 0.02 * max(mask.shape)
    Lloc = cv2.GaussianBlur(L * w, (0, 0), sigma) / np.maximum(cv2.GaussianBlur(w, (0, 0), sigma), 1e-3)
    med_ab = np.median(lab[mask][:, 1:], 0)
    dab = np.linalg.norm(lab[..., 1:] - med_ab, axis=2)
    foreign = mask & ((L < 0.55 * Lloc) | (dab > 22))
    foreign = cv2.morphologyEx(foreign.astype(np.uint8), cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    n, lab_cc, stats, _ = cv2.connectedComponentsWithStats(foreign, connectivity=8)
    keep_out = np.zeros_like(mask)
    for i in range(1, n):
        if stats[i, cv2.CC_STAT_AREA] >= 25:
            keep_out |= lab_cc == i
    keep_out = cv2.dilate(keep_out.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    return mask & ~keep_out


def _split_walls(img: np.ndarray, wall: np.ndarray) -> List[np.ndarray]:
    """Splits the wall region at room corners: long vertical edges inside the
    wall with a clear lighting change across them (two walls facing
    different ways are lit differently)."""
    H, W = wall.shape
    total = wall.sum()
    if total == 0:
        return []
    lab_l = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0].astype(np.float32)
    edges = cv2.Canny(cv2.GaussianBlur(img, (5, 5), 0), 30, 90)
    edges[~cv2.dilate(wall.astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)] = 0
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=40, minLineLength=int(0.18 * H), maxLineGap=10)
    cuts: List[int] = []
    if lines is not None:
        for x1, y1, x2, y2 in lines.reshape(-1, 4):
            if abs(x2 - x1) > 0.03 * abs(y2 - y1):          # not vertical
                continue
            x = int(round((x1 + x2) / 2))
            if x < 0.05 * W or x > 0.95 * W:
                continue
            ya, yb = sorted((y1, y2))
            band = wall[ya:yb, max(0, x - 25):x - 4], wall[ya:yb, x + 4:x + 25]
            if band[0].size == 0 or band[1].size == 0 or band[0].mean() < 0.7 or band[1].mean() < 0.7:
                continue
            left = lab_l[ya:yb, max(0, x - 25):x - 4][band[0]]
            right = lab_l[ya:yb, x + 4:x + 25][band[1]]
            if abs(float(np.median(left)) - float(np.median(right))) >= 7:
                if all(abs(x - c) > 0.08 * W for c in cuts):
                    cuts.append(x)
    bounds = [0] + sorted(cuts) + [W]
    sections = []
    for a, b in zip(bounds, bounds[1:]):
        sec = np.zeros_like(wall)
        sec[:, a:b] = wall[:, a:b]
        if sec.sum() >= MIN_WALL_SECTION_FRAC * total:
            sections.append(sec)
        elif sections:
            sections[-1] |= sec
    if not sections:
        return [wall]
    # Leftover slivers join the section next to them.
    covered = np.zeros_like(wall)
    for s in sections:
        covered |= s
    if (wall & ~covered).any():
        sections[-1] |= wall & ~covered
    return sections


def room_layout(floor_region: np.ndarray, ceiling: np.ndarray, camera: Camera,
                wall: Optional[np.ndarray] = None) -> Dict:
    """Per sampled column: the row where the floor meets the wall (the seam)
    and the row where the ceiling ends, normalised. The seam is measured only
    where the floor visibly touches the wall; behind furniture it is
    interpolated from both sides. Without any floor, it is placed below the
    horizon."""
    H, W = floor_region.shape
    xs = np.linspace(0, W - 1, LAYOUT_SAMPLES).astype(int)
    floor_y, ceil_y = [], []
    gap = max(3, int(0.01 * H))
    for x in xs:
        col = floor_region[:, max(0, x - 2):x + 3].any(1)
        y = float(np.argmax(col)) if col.any() else np.nan
        if wall is not None and not np.isnan(y):
            above = wall[max(0, int(y) - gap):int(y), max(0, x - 2):x + 3]
            if above.size == 0 or not above.any():
                y = np.nan                      # hidden by furniture: interpolate
        floor_y.append(y)
        ccol = ceiling[:, max(0, x - 2):x + 3].any(1)
        ceil_y.append(float(H - 1 - np.argmax(ccol[::-1])) if ccol.any() else np.nan)
    fy = np.array(floor_y)
    if np.isnan(fy).all():
        fy[:] = min(H - 1, camera.horizon + 0.25 * H)
    else:
        idx = np.arange(len(fy))
        good = ~np.isnan(fy)
        fy = np.interp(idx, idx[good], fy[good])
    fy = np.maximum(fy, camera.horizon + 2)
    cy = np.array(ceil_y)
    cy = np.where(np.isnan(cy), -1.0, cy)
    return {"columns": [round(float(x) / W, 4) for x in xs],
            "floor_y": [round(float(v) / H, 4) for v in fy],
            "ceiling_y": [round(float(v) / H, 4) if v >= 0 else -1 for v in cy]}


def floor_row_extents(floor_region: np.ndarray, step: int = 8) -> List[List[float]]:
    """[y, x_min, x_max] of the floor per band of rows (normalised): where a
    floor-standing object may be put down."""
    H, W = floor_region.shape
    out = []
    for y in range(0, H, step):
        band = floor_region[y:y + step].any(0)
        if band.sum() < 3:
            continue
        xs = np.where(band)[0]
        out.append([round(y / H, 4), round(xs.min() / W, 4), round(xs.max() / W, 4)])
    return out


def _visible_floor_seam(floor: np.ndarray) -> Optional[np.ndarray]:
    """Per column, the first row of visible floor (interpolated across
    columns where furniture hides it), or None without floor."""
    H, W = floor.shape
    has = floor.any(0)
    if has.sum() < 0.05 * W:
        return None
    top = np.where(has, floor.argmax(0), 0).astype(float)
    cols = np.arange(W)
    return np.interp(cols, cols[has], top[has])


def calibrate_scale(camera: Camera, objects: List[Dict], W: int) -> Camera:
    """Sets the camera's eye height so the furniture found has typical real
    sizes (median over the pieces fully in view). Without any, the default
    eye height stays."""
    ratios = []
    for c in objects:
        typical = catalog.TYPICAL_WIDTH_M.get(c["type"])
        if not typical or c["placement"] != "floor" or c["x0"] <= 2 or c["x1"] >= W - 2:
            continue
        measured = (c["x1"] - c["x0"]) * camera.metres_per_px(c["bottom"])
        if measured > 0:
            ratios.append(typical / measured)
    if not ratios:
        return camera
    camera.eye_height_m = round(float(np.clip(camera.eye_height_m * np.median(ratios), 0.6, 2.2)), 3)
    camera.source += "+furniture_scale"
    return camera


def _components(mask: np.ndarray, min_px: int) -> List[np.ndarray]:
    n, lab, stats, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    return [lab == i for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= min_px]


def _touches_floor(mask: np.ndarray, floor: np.ndarray) -> bool:
    H = mask.shape[0]
    ys, xs = np.where(mask)
    bottom = ys.max()
    band = floor[min(H - 1, bottom + 1):min(H, bottom + 1 + max(4, int(0.015 * H))), xs.min():xs.max() + 1]
    return band.size > 0 and band.mean() > 0.25


def build_scene(img: np.ndarray, cls_map: np.ndarray, conf: np.ndarray,
                labels: Dict[int, str]) -> Tuple[Dict, np.ndarray, Dict[int, np.ndarray]]:
    """Returns (detection dict, instance map uint8, {instance: alpha uint8})."""
    H, W = cls_map.shape
    N = H * W
    min_px = max(MIN_OBJECT_PX, int(MIN_OBJECT_FRAC * N))
    types = {cid: catalog.CLASS_TO_TYPE.get(name) for cid, name in labels.items()}

    def class_mask(names) -> np.ndarray:
        ids = [cid for cid, n in labels.items() if n in names]
        return np.isin(cls_map, ids) if ids else np.zeros((H, W), bool)

    kernel = np.ones((3, 3), np.uint8)
    wall = cv2.morphologyEx(class_mask({"wall"}).astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    wall = drop_foreign_pixels(img, wall)
    floor = cv2.morphologyEx(class_mask({"floor"}).astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    ceiling = cv2.morphologyEx(class_mask({"ceiling"}).astype(np.uint8), cv2.MORPH_OPEN, kernel).astype(bool)
    ceiling = drop_foreign_pixels(img, ceiling)

    instance_map = np.zeros((H, W), np.uint8)
    alphas: Dict[int, np.ndarray] = {}
    next_index = 1

    # ---- objects -------------------------------------------------------
    type_names = sorted({t for t in types.values() if t})
    type_map = np.full((H, W), -1, dtype=np.int16)
    group_masks: Dict[str, np.ndarray] = {}
    for cid, t in types.items():
        if t is None:
            continue
        m = cls_map == cid
        if not m.any():
            continue
        group = catalog.MERGE_GROUPS.get(t, t)
        group_masks[group] = group_masks.get(group, np.zeros((H, W), bool)) | m
        type_map[m] = type_names.index(t)

    candidates = []
    for group, gm in group_masks.items():
        gm = cv2.morphologyEx(gm.astype(np.uint8), cv2.MORPH_CLOSE, kernel).astype(bool)
        for comp in _components(gm, min_px):
            ts, counts = np.unique(type_map[comp & (type_map >= 0)], return_counts=True)
            if len(ts) == 0:
                continue
            t = type_names[int(ts[np.argmax(counts)])]
            candidates.append({"type": t, "mask": comp})

    # Cushions/pillows on a sofa or bed are part of it.
    hosts = [c for c in candidates if c["type"] in catalog.SOFT_PART_HOSTS]
    kept = []
    for c in candidates:
        if c["type"] in catalog.SOFT_PART_TYPES:
            grown = cv2.dilate(c["mask"].astype(np.uint8), np.ones((7, 7), np.uint8)).astype(bool)
            host = next((h for h in hosts if (grown & h["mask"]).any()), None)
            if host is not None:
                host["mask"] = host["mask"] | c["mask"]
                continue
        kept.append(c)
    kept.sort(key=lambda c: -int(c["mask"].sum()))
    kept = kept[:MAX_OBJECTS]

    # Which objects stand on the floor: their bottom reaches the seam where the
    # visible floor starts (upper kitchen cabinets and pendant lamps do not).
    seam = _visible_floor_seam(floor)
    for c in kept:
        ys, xs = np.where(c["mask"])
        c["bottom"], c["top"], c["x0"], c["x1"] = int(ys.max()) + 1, int(ys.min()), int(xs.min()), int(xs.max()) + 1
        placement = catalog.type_info(c["type"])["placement"]
        on_floor = seam is not None and c["bottom"] >= seam[c["x0"]:c["x1"]].min() - 0.05 * H
        if placement in ("floor", "floor_flat") and not on_floor:
            placement = "wall" if catalog.MERGE_GROUPS.get(c["type"]) == "storage" else "surface"
        elif placement == "surface" and _touches_floor(c["mask"], floor):
            placement = "floor"
        if c["type"] == "lamp" and c["top"] <= 0.02 * H and not on_floor:
            placement = "ceiling"
        c["placement"] = placement

    # Where the floor continues: visible floor, rugs, and under floor-standing furniture.
    floor_region = floor.copy()
    for c in kept:
        if c["placement"] in ("floor", "floor_flat"):
            band = max(2, (c["bottom"] - c["top"]) // 6)
            floor_region[c["bottom"] - band:c["bottom"], c["x0"]:c["x1"]] = True
    floor_region = cv2.morphologyEx(floor_region.astype(np.uint8), cv2.MORPH_CLOSE,
                                    np.ones((15, 15), np.uint8)).astype(bool)

    room_mask = wall | floor | ceiling
    camera = estimate_camera(img, floor_region, room_mask)
    camera = calibrate_scale(camera, kept, W)

    all_objects = np.zeros((H, W), bool)
    for c in kept:
        all_objects |= c["mask"]

    objects = []
    counters: Dict[str, int] = {}
    for c in sorted(kept, key=lambda c: -int(np.where(c["mask"])[0].max())):   # front first
        t, m = c["type"], c["mask"]
        info = catalog.type_info(t)
        idx = next_index
        next_index += 1
        if c["placement"] == "floor":
            m = m | recover_legs(img, m, floor)
        alpha = refine_alpha(img, m, all_objects & ~m)
        solid = alpha >= 128
        if solid.sum() < min_px // 2:
            solid, alpha = m, (m * 255).astype(np.uint8)
        instance_map[solid & (instance_map == 0)] = idx
        alphas[idx] = alpha
        ys, xs = np.where(solid)
        x0, x1, y0, y1 = int(xs.min()), int(xs.max()) + 1, int(ys.min()), int(ys.max()) + 1
        placement = c["placement"]
        counters[t] = counters.get(t, 0) + 1
        anchor_y = y1 if placement in ("floor", "floor_flat") else (y0 + y1) / 2
        dims = None
        if placement in ("floor", "floor_flat"):
            mpp = camera.metres_per_px(y1)
            dims = {"width": round((x1 - x0) * mpp, 2), "height": round((y1 - y0) * mpp, 2)}
            if placement == "floor_flat":
                dims = {"width": round((x1 - x0) * mpp, 2)}
        objects.append({
            "id": f"{t}_{counters[t]:03d}",
            "kind": "object",
            "type": t,
            "label": info["label"],
            "category": info["category"],
            "placement": placement,
            "source": "detected",
            "instance": idx,
            "confidence": round(float(conf[m].mean()), 3),
            "area": round(float(solid.sum()) / N, 4),
            "anchor": {"x": round((x0 + x1) / 2 / W, 4), "y": round(anchor_y / H, 4)},
            "bbox": _norm_box(x0, y0, x1 - x0, y1 - y0, W, H),
            "outline": outline(solid, W, H),
            "color": median_color(img, solid),
            "material_guess": (info.get("materials") or [None])[0],
            "dimensions_m": dims,
        })

    # ---- surfaces --------------------------------------------------------
    surfaces = []
    for i, sec in enumerate(_split_walls(img, wall & (instance_map == 0)), start=1):
        idx = next_index
        next_index += 1
        instance_map[sec & (instance_map == 0)] = idx
        surfaces.append(_surface(f"wall_{i:03d}", "wall", "Wall" if i == 1 else f"Wall {i}", idx, sec, img, conf, W, H))
    for t, m in (("floor", floor), ("ceiling", ceiling)):
        m = m & (instance_map == 0)
        if m.sum() < min_px:
            continue
        idx = next_index
        next_index += 1
        instance_map[m] = idx
        surfaces.append(_surface(f"{t}_001", t, t.capitalize(), idx, m, img, conf, W, H))

    detected_names = sorted({labels[int(c)] for c in np.unique(cls_map)})
    return {
        "camera": camera.to_dict(),
        "layout": room_layout(floor_region, ceiling, camera, class_mask({"wall"})),
        "floor_rows": floor_row_extents(floor_region),
        "surfaces": surfaces,
        "objects": objects,
        "relationships": relationships(objects, surfaces, instance_map),
        "classes_seen": detected_names,
        "people_seen": "person" in detected_names,
        "coverage": {"wall": round(float(wall.mean()), 3), "floor": round(float(floor.mean()), 3),
                     "ceiling": round(float(ceiling.mean()), 3), "objects": round(float(all_objects.mean()), 3)},
    }, instance_map, alphas


def _surface(sid, type_, label, idx, mask, img, conf, W, H) -> Dict:
    ys, xs = np.where(mask)
    return {"id": sid, "kind": "surface", "type": type_, "label": label, "category": "surface",
            "instance": idx, "confidence": round(float(conf[mask].mean()), 3),
            "area": round(float(mask.sum()) / (W * H), 4),
            "bbox": _norm_box(int(xs.min()), int(ys.min()), int(xs.max() - xs.min() + 1),
                              int(ys.max() - ys.min() + 1), W, H),
            "outline": outline(mask, W, H, 120),
            "color": median_color(img, mask),
            "material_guess": None}


def relationships(objects: List[Dict], surfaces: List[Dict], instance_map: np.ndarray) -> List[Dict]:
    """stands_on / hangs_on / on (small object resting on furniture) /
    in_front_of (overlapping floor objects, the nearer one first)."""
    rels = []
    floor = next((s for s in surfaces if s["type"] == "floor"), None)
    walls = [s for s in surfaces if s["type"] == "wall"]
    H, W = instance_map.shape

    def box(o):
        b = o["bbox"]
        return b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]

    for o in objects:
        x0, y0, x1, y1 = box(o)
        if o["placement"] in ("floor", "floor_flat") and floor:
            rels.append({"type": "stands_on", "subject": o["id"], "object": floor["id"]})
        elif o["placement"] == "wall" and walls:
            cx = int(min(W - 1, (x0 + x1) / 2 * W))
            cy = int(min(H - 1, max(0, y0 * H - 3)))
            under = instance_map[cy, cx]
            wall = next((w for w in walls if w["instance"] == under), walls[0])
            rels.append({"type": "hangs_on", "subject": o["id"], "object": wall["id"]})
        elif o["placement"] == "surface":
            best, best_ov = None, 0.0
            for p in objects:
                if p is o or p["placement"] not in ("floor",) or p["area"] <= o["area"]:
                    continue
                px0, py0, px1, py1 = box(p)
                ov = max(0.0, min(x1, px1) - max(x0, px0)) / max(1e-6, x1 - x0)
                if ov > 0.6 and py0 - 0.02 <= y1 <= py0 + 0.5 * (py1 - py0) and ov > best_ov:
                    best, best_ov = p, ov
            if best:
                rels.append({"type": "on", "subject": o["id"], "object": best["id"]})
    floor_objs = [o for o in objects if o["placement"] == "floor"]
    for a in floor_objs:
        for b in floor_objs:
            if a is b:
                continue
            ax0, _, ax1, ay1 = box(a)
            bx0, _, bx1, by1 = box(b)
            if min(ax1, bx1) - max(ax0, bx0) > 0.3 * min(ax1 - ax0, bx1 - bx0) and ay1 > by1 + 0.02:
                rels.append({"type": "in_front_of", "subject": a["id"], "object": b["id"]})
    return rels
