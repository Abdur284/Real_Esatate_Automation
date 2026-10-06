"""
Pixel-space floor-plan segmentation with classical computer vision (OpenCV).

Why classical CV rather than a neural model: floor plans are high-contrast
line drawings whose walls are the thickest long straight strokes on the page,
so morphology finds them reliably and deterministically, in well under a
second on a CPU, with no model download, GPU or external AI service. It also
fails visibly (no enclosed rooms found) instead of hallucinating a layout.
What it cannot do is read text: room names and printed dimensions are not
OCR'd, so the scale must come from the user and room types come only from
HAVEN's colour legend, stair hatching, or the user's review.

Stages (all in pixels, image already rotated so the road is at the bottom):
    1. ink mask         Otsu threshold, capped so pale room fills are not ink
    2. wall thickness   opening sweep over long strokes gives a stroke-thickness
                        histogram; linework is 1-2 px, each wall class is a peak
    3. wall mask        ink opened just below the thinnest wall class, long
                        components, grown across door gaps into one shell;
                        filled areas far thicker than any wall reject the image
    4. gap closing      wall pixels are bridged along each axis across gaps up
                        to a maximum opening width; bridges thicker than a wall
                        are discarded; the kept bridges are the openings
    5. rooms            enclosed free-space components (the one touching the
                        border is outside); non-rectangular rooms are split
                        into rectangles
    6. room evidence    fill colour (HAVEN legend) and stair hatching
"""
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

MAX_SIDE_PX = 1600          # analysis resolution cap
INK_THRESHOLD_CAP = 150     # grey levels above this are never ink (room fills)
RECT_FIT_SINGLE = 0.88      # fill ratio above which a room is one rectangle
MAX_PARTS = 6


def _rect(w: int, h: int) -> np.ndarray:
    return cv2.getStructuringElement(cv2.MORPH_RECT, (max(1, int(w)), max(1, int(h))))


def _open(mask: np.ndarray, w: int, h: int) -> np.ndarray:
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, _rect(w, h))


def _long_strokes(mask: np.ndarray, length: int) -> np.ndarray:
    return cv2.bitwise_or(_open(mask, length, 1), _open(mask, 1, length))


def prepare(img: np.ndarray) -> Tuple[np.ndarray, np.ndarray, float]:
    """Downscales to the analysis resolution. Returns (bgr, gray, factor)."""
    h, w = img.shape[:2]
    f = min(1.0, MAX_SIDE_PX / max(h, w))
    if f < 1.0:
        img = cv2.resize(img, (round(w * f), round(h * f)), interpolation=cv2.INTER_AREA)
    return img, cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), f


def ink_mask(gray: np.ndarray) -> np.ndarray:
    t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return (gray < min(t, INK_THRESHOLD_CAP)).astype(np.uint8)


def _first_run(values: np.ndarray, skip_leading: bool = True) -> int:
    """Length of the first run of ones (after leading zeros if skip_leading)."""
    idx = np.flatnonzero(values)
    if idx.size == 0:
        return 0
    start = idx[0] if skip_leading else 0
    if not skip_leading and values[0] == 0:
        return 0
    zeros = np.flatnonzero(values[start:] == 0)
    return int(zeros[0]) if zeros.size else int(values.size - start)


def detect_walls(gray: np.ndarray) -> Optional[Dict[str, Any]]:
    """Stages 1-3. Returns None when nothing wall-like is found."""
    ink = ink_mask(gray)
    side = max(gray.shape)
    stroke_len = max(15, int(side * 0.03))
    base = int(_long_strokes(ink, stroke_len).sum())
    if base == 0:
        return None

    kmax = max(3, int(side * 0.03))
    counts = [base]
    for k in range(2, kmax + 2):
        counts.append(int(_long_strokes(_open(ink, k, k), stroke_len).sum()))
    # counts[i] is the long-stroke mass surviving an (i+1) x (i+1) opening, so
    # counts[i-1] - counts[i] is the mass of long strokes exactly i px thick:
    # a thickness histogram. Text, dimension lines and door arcs sit at 1-2 px;
    # each wall class (partitions, outer walls) is a separate peak above that.
    mass = {t: counts[t - 1] - counts[t] for t in range(1, len(counts))}
    walls_classes = [t for t, m in mass.items() if t >= 3 and m >= 0.1 * base]
    thin = min(walls_classes) if walls_classes else 1
    # Open just below the thinnest wall class: removes thin linework but keeps
    # every wall, partitions included.
    k = thin
    k_open = max(1, int(round(0.6 * thin))) if thin >= 3 else 1

    opened = _open(ink, k_open, k_open) if k_open > 1 else ink
    n, labels, stats, _ = cv2.connectedComponentsWithStats(opened, connectivity=8)
    min_extent = max(stroke_len, 4 * k)
    keep = [i for i in range(1, n)
            if max(stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT]) >= min_extent]
    if not keep:
        return None

    def box(i):
        return [int(stats[i, cv2.CC_STAT_LEFT]), int(stats[i, cv2.CC_STAT_TOP]),
                int(stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH]),
                int(stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])]

    # Door and window gaps split the outer wall into pieces, so start from the
    # largest piece and absorb every wall piece that lies within a door's
    # width of the building found so far.
    main = max(keep, key=lambda i: stats[i, cv2.CC_STAT_AREA])
    bb = box(main)
    inside = {main}
    grew = True
    while grew:
        grew = False
        reach = int(0.1 * max(bb[2] - bb[0], bb[3] - bb[1]))
        for i in keep:
            if i in inside:
                continue
            b = box(i)
            if b[0] <= bb[2] + reach and b[2] >= bb[0] - reach and b[1] <= bb[3] + reach and b[3] >= bb[1] - reach:
                inside.add(i)
                bb = [min(bb[0], b[0]), min(bb[1], b[1]), max(bb[2], b[2]), max(bb[3], b[3])]
                grew = True
    x, y, w, h = bb[0], bb[1], bb[2] - bb[0], bb[3] - bb[1]
    walls = np.isin(labels, list(inside)).astype(np.uint8)

    wall_px = int(walls.sum())
    straight = int(_long_strokes(walls, max(stroke_len, 3 * k)).sum())

    # Exterior wall thickness: run length inward from each side of the shell.
    runs = []
    for xs in np.linspace(x + w * 0.1, x + w * 0.9, 25).astype(int):
        runs.append(_first_run(walls[y:y + h, xs]))
        runs.append(_first_run(walls[y:y + h, xs][::-1]))
    for ys in np.linspace(y + h * 0.1, y + h * 0.9, 25).astype(int):
        runs.append(_first_run(walls[ys, x:x + w]))
        runs.append(_first_run(walls[ys, x:x + w][::-1]))
    runs = [r for r in runs if 0 < r <= 3 * k + 2]
    ext_t = float(np.median(runs)) if runs else float(k)
    k_max_class = max([t for t in walls_classes] or [k])

    # Walls are strokes of consistent thickness; filled areas (a photo's
    # shadows, a render's road) are far thicker than any wall class.
    dist = cv2.distanceTransform(walls, cv2.DIST_L2, 3)
    wall_dist = dist[walls > 0]
    stroke_p95 = float(np.percentile(wall_dist, 95)) * 2 if wall_dist.size else 0.0

    return {
        "ink": ink, "walls": walls, "k": k, "bbox": (x, y, w, h), "stroke_p95_px": stroke_p95,
        "exterior_thickness_px": ext_t,
        "thickest_wall_px": float(k_max_class),
        "straightness": straight / wall_px if wall_px else 0.0,
        "wall_pixel_share": wall_px / max(1, int(ink.sum())),
        "image_shape": gray.shape,
    }


def close_gaps(walls: np.ndarray, max_gap_px: int, max_wall_px: float) -> np.ndarray:
    """Stage 4: bridges door/window gaps up to max_gap_px wide.

    Closing along each axis bridges any two wall pixels on the same row (or
    column) within the gap limit. A real opening's bridge is only as thick as
    the wall it sits in, even when one side of the gap is a perpendicular wall
    or a short stub. Bridges thicker than a wall are the floor of a narrow
    room or corridor filled across, and are discarded."""
    g = max(3, int(max_gap_px))
    out = walls.copy()
    for kernel, along in (((g, 1), cv2.CC_STAT_WIDTH), ((1, g), cv2.CC_STAT_HEIGHT)):
        closed = cv2.morphologyEx(walls, cv2.MORPH_CLOSE, _rect(*kernel))
        bridge = (closed & (1 - walls)).astype(np.uint8)
        n, lab, stats, _ = cv2.connectedComponentsWithStats(bridge, connectivity=8)
        # Mean thickness across the bridging direction (area / length along
        # it): a hairline between two coincident strokes attached to a door
        # bridge barely changes it, while a filled room fails clearly.
        thickness = stats[1:, cv2.CC_STAT_AREA] / np.maximum(stats[1:, along], 1)
        keep = np.zeros(n, dtype=np.uint8)
        keep[1:] = thickness <= max_wall_px
        out |= keep[lab]
    return out


def _largest_rectangle(grid: np.ndarray) -> Tuple[int, int, int, int, int]:
    """Largest all-ones rectangle: (area, row0, col0, row1, col1) exclusive ends."""
    rows, cols = grid.shape
    heights = np.zeros(cols, dtype=int)
    best = (0, 0, 0, 0, 0)
    for r in range(rows):
        heights = np.where(grid[r] > 0, heights + 1, 0)
        stack: List[int] = []
        for c in range(cols + 1):
            h = heights[c] if c < cols else 0
            while stack and heights[stack[-1]] >= h:
                top = stack.pop()
                height = heights[top]
                left = stack[-1] + 1 if stack else 0
                area = height * (c - left)
                if area > best[0]:
                    best = (int(area), r - height + 1, left, r + 1, c)
            stack.append(c)
    return best


def decompose(mask: np.ndarray, cell: int, min_part_px: int) -> Tuple[List[Tuple[int, int, int, int]], float]:
    """Splits a room mask (cropped to its bbox) into axis-aligned rectangles.
    Returns ([(x0, y0, x1, y1)], coverage) in crop pixels."""
    h, w = mask.shape
    area = int(mask.sum())
    if area == 0:
        return [], 0.0
    if area / float(w * h) >= RECT_FIT_SINGLE:
        return [(0, 0, w, h)], area / float(w * h)
    cell = max(2, int(cell))
    gw, gh = max(1, int(np.ceil(w / cell))), max(1, int(np.ceil(h / cell)))
    pad = np.zeros((gh * cell, gw * cell), dtype=np.float32)
    pad[:h, :w] = mask
    grid = (pad.reshape(gh, cell, gw, cell).mean(axis=(1, 3)) >= 0.5).astype(np.uint8)
    parts = []
    while grid.any() and len(parts) < MAX_PARTS:
        a, r0, c0, r1, c1 = _largest_rectangle(grid)
        if a * cell * cell < min_part_px:
            break
        grid[r0:r1, c0:c1] = 0
        x0, y0, x1, y1 = c0 * cell, r0 * cell, min(w, c1 * cell), min(h, r1 * cell)
        # Snap part edges that fall within one cell of the room's own bbox.
        x0 = 0 if x0 <= cell else x0
        y0 = 0 if y0 <= cell else y0
        x1 = w if w - x1 <= cell else x1
        y1 = h if h - y1 <= cell else y1
        parts.append((x0, y0, x1, y1))
    covered = np.zeros_like(mask)
    for x0, y0, x1, y1 in parts:
        covered[y0:y1, x0:x1] = 1
    coverage = float((covered & mask).sum()) / area
    spill = float((covered & (1 - mask)).sum()) / area
    return parts, max(0.0, coverage - spill)


def _wall_run_outward(closed: np.ndarray, samples: List[Tuple[int, int]], dx: int, dy: int, limit: int) -> float:
    runs = []
    H, W = closed.shape
    for sx, sy in samples:
        n = 0
        x, y = sx, sy
        while 0 <= x < W and 0 <= y < H and closed[y, x] and n < limit:
            n += 1
            x += dx
            y += dy
        runs.append(n)
    runs = [r for r in runs if r > 0]
    return float(np.median(runs)) if runs else 0.0


def _stairs_evidence(gray: np.ndarray, mask: np.ndarray, x: int, y: int) -> float:
    """Regularly spaced full-width lines (tread hatching) inside the room.
    Returns a confidence in [0, 1] (0 = no evidence)."""
    h, w = mask.shape
    if h < 12 or w < 12:
        return 0.0
    crop = gray[y:y + h, x:x + w].astype(np.int16)
    inner = cv2.erode(mask, _rect(5, 5))
    if inner.sum() < 50:
        return 0.0
    fill = np.median(crop[inner > 0])
    ink = ((crop < fill - 40) & (inner > 0)).astype(np.uint8)
    best = 0.0
    for axis in (1, 0):  # rows (horizontal treads), then columns
        span = inner.sum(axis=axis).astype(float)
        frac = np.divide(ink.sum(axis=axis), span, out=np.zeros_like(span), where=span > 0)
        lines = frac > 0.6
        starts = np.flatnonzero(lines[1:] & ~lines[:-1]) + 1
        if lines.size and lines[0]:
            starts = np.insert(starts, 0, 0)
        if starts.size >= 5:
            gaps = np.diff(starts)
            cv = float(np.std(gaps) / np.mean(gaps)) if np.mean(gaps) > 0 else 1.0
            if cv < 0.35:
                best = max(best, min(0.9, 0.5 + 0.05 * starts.size))
    return best


def segment_rooms(bgr: np.ndarray, gray: np.ndarray, wall: Dict[str, Any], max_gap_px: float,
                  min_room_px: float, min_side_px: float) -> Dict[str, Any]:
    """Stages 4-6."""
    walls, k = wall["walls"], wall["k"]
    bx, by, bw, bh = wall["bbox"]
    closed = close_gaps(walls, int(max_gap_px), 1.6 * max(k, wall["exterior_thickness_px"]) + 2)
    H, W = walls.shape

    # Everything outside the shell's bbox is outside; label free space inside.
    pad = 2
    x0, y0 = max(0, bx - pad), max(0, by - pad)
    x1, y1 = min(W, bx + bw + pad), min(H, by + bh + pad)
    free = np.zeros((H, W), dtype=np.uint8)
    free[y0:y1, x0:x1] = 1 - closed[y0:y1, x0:x1]
    n, labels, stats, _ = cv2.connectedComponentsWithStats(free, connectivity=4)

    border = set(np.unique(np.concatenate([labels[y0, x0:x1], labels[y1 - 1, x0:x1],
                                           labels[y0:y1, x0], labels[y0:y1, x1 - 1]])).tolist()) - {0}
    candidates = []
    rejected_small = 0
    for i in range(1, n):
        if i in border:
            continue
        cw, ch, area = stats[i, cv2.CC_STAT_WIDTH], stats[i, cv2.CC_STAT_HEIGHT], stats[i, cv2.CC_STAT_AREA]
        if area < min_room_px or min(cw, ch) < min_side_px:
            rejected_small += 1
            continue
        candidates.append(i)

    # A small region wholly inside a bigger room's bbox is a drawn fixture
    # (a table or bathtub outline), not a room.
    def bbox(i):
        return (stats[i, cv2.CC_STAT_LEFT], stats[i, cv2.CC_STAT_TOP],
                stats[i, cv2.CC_STAT_LEFT] + stats[i, cv2.CC_STAT_WIDTH],
                stats[i, cv2.CC_STAT_TOP] + stats[i, cv2.CC_STAT_HEIGHT])
    fixtures: Dict[int, int] = {}
    for i in candidates:
        a = bbox(i)
        for j in candidates:
            b = bbox(j)
            if i != j and stats[i, cv2.CC_STAT_AREA] < 0.25 * stats[j, cv2.CC_STAT_AREA] \
                    and a[0] > b[0] and a[1] > b[1] and a[2] < b[2] and a[3] < b[3]:
                fixtures[i] = j
                break
    room_ids = [i for i in candidates if i not in fixtures]

    # Share of the shell's free area that is connected to the outside: high for
    # an L-shaped building, or when an outer wall has a very wide opening.
    bbox_free = max(1, int((1 - closed[by:by + bh, bx:bx + bw]).sum()))
    outside_labels = np.isin(labels[by:by + bh, bx:bx + bw], list(border)) if border else np.zeros((bh, bw), bool)
    outside_share = float(outside_labels.sum()) / bbox_free

    rooms = []
    cell = max(2, int(max(k, min(bw, bh) / 60)))
    for i in room_ids:
        rx, ry, rx1, ry1 = (int(v) for v in bbox(i))
        mask = (labels[ry:ry1, rx:rx1] == i).astype(np.uint8)
        parts, coverage = decompose(mask, cell, int(min_room_px * 0.35))
        if not parts:
            continue
        out_parts = []
        for px0, py0, px1, py1 in parts:
            ax0, ay0, ax1, ay1 = rx + px0, ry + py0, rx + px1, ry + py1
            expand = {}
            for side, samples, dx, dy in (
                ("west", [(ax0 - 1, int(v)) for v in np.linspace(ay0 + 1, ay1 - 2, 9)], -1, 0),
                ("east", [(ax1, int(v)) for v in np.linspace(ay0 + 1, ay1 - 2, 9)], 1, 0),
                ("north", [(int(v), ay0 - 1) for v in np.linspace(ax0 + 1, ax1 - 2, 9)], 0, -1),
                ("south", [(int(v), ay1) for v in np.linspace(ax0 + 1, ax1 - 2, 9)], 0, 1),
            ):
                # Only sides on the room's boundary move out to the wall centre;
                # the seam between two parts of one room stays where it is.
                inside = [labels[sy, sx] == i for sx, sy in samples if 0 <= sx < W and 0 <= sy < H]
                if inside and sum(inside) > len(inside) / 2:
                    expand[side] = 0.0
                else:
                    expand[side] = _wall_run_outward(closed, samples, dx, dy, 4 * k + 4) / 2.0
            out_parts.append({"x0": ax0, "y0": ay0, "x1": ax1, "y1": ay1, "expand": expand})

        inner = cv2.erode(mask, _rect(3, 3))
        pix = bgr[ry:ry1, rx:rx1][inner > 0] if inner.sum() > 20 else bgr[ry:ry1, rx:rx1][mask > 0]
        fill = np.median(pix, axis=0) if len(pix) else np.array([255, 255, 255])
        rooms.append({
            "label": i, "bbox": (rx, ry, rx1, ry1), "area_px": int(stats[i, cv2.CC_STAT_AREA]),
            "parts": out_parts, "coverage": coverage,
            "fill_rgb": [int(fill[2]), int(fill[1]), int(fill[0])],
            "stairs": _stairs_evidence(gray, mask, rx, ry),
            "fixtures": sum(1 for f, host in fixtures.items() if host == i),
        })

    openings = _find_openings(bgr, wall["ink"], walls, closed, labels, border, k, min_side_px)
    return {"rooms": rooms, "openings": openings, "closed": closed, "labels": labels,
            "outside_share": outside_share, "rejected_regions": rejected_small}


def _find_openings(bgr, ink, walls, closed, labels, border, k, min_len_px) -> List[Dict[str, Any]]:
    gaps = (closed & (1 - walls)).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(gaps, connectivity=8)
    H, W = walls.shape
    out = []
    for i in range(1, n):
        x, y, w, h = (int(stats[i, c]) for c in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                                  cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
        horizontal = w >= h
        length, across = (w, h) if horizontal else (h, w)
        if length < max(2 * k, min_len_px * 0.5) or across < max(1, k // 2):
            continue
        region = bgr[y:y + h, x:x + w].astype(int)
        b, g, r = region[..., 0], region[..., 1], region[..., 2]
        blue = float(((b > r + 40) & (b > 120) & (g > r)).mean())
        orange = float(((r > b + 60) & (r > 150) & (g > b)).mean())
        dark = ink[y:y + h, x:x + w]
        profile = dark.mean(axis=1 if horizontal else 0)
        lines = profile > 0.7
        nlines = int(np.count_nonzero(lines[1:] & ~lines[:-1]) + (1 if lines.size and lines[0] else 0))

        # Which regions lie on either side of the gap (room labels or outside).
        if horizontal:
            cx = x + w // 2
            side_a = labels[max(0, y - 2), cx]          # above (north of the gap)
            side_b = labels[min(H - 1, y + h + 1), cx]  # below (south of the gap)
        else:
            cy = y + h // 2
            side_a = labels[cy, max(0, x - 2)]          # left (west of the gap)
            side_b = labels[cy, min(W - 1, x + w + 1)]  # right (east of the gap)
        exterior = side_a in border or side_b in border or side_a == 0 or side_b == 0

        if blue > 0.15:
            kind, conf = "window", 0.85
        elif orange > 0.1:
            kind, conf = "door", 0.85
        elif nlines >= 2 or (exterior and nlines >= 1):
            kind, conf = "window", 0.7
        else:
            kind, conf = "door", 0.6 if not exterior else 0.5
        out.append({"kind": kind, "confidence": conf, "horizontal": horizontal,
                    "x0": x, "y0": y, "x1": x + w, "y1": y + h,
                    "side_a": int(side_a), "side_b": int(side_b), "exterior": bool(exterior)})
    return out
