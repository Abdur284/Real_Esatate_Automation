"""
Pixel-space floor-plan segmentation with classical computer vision (OpenCV).

Why classical CV rather than a neural model: floor plans are high-contrast
line drawings whose walls are the thickest long straight strokes on the page,
so morphology finds them reliably and deterministically, in well under a
second on a CPU, with no model download, GPU or external AI service. It also
fails visibly (no enclosed rooms found) instead of hallucinating a layout.
Text (room names, printed sizes) is read separately by text.py.

Stages (all in pixels, image already rotated so the road is at the bottom):
    1. ink mask         Otsu threshold, capped so pale room fills are not ink;
                        outlined (double-line) walls are filled solid
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
LINE_ART_THRESHOLD_CAP = 215  # ... except on white line drawings without fills
RECT_FIT_SINGLE = 0.88      # fill ratio above which a room is one rectangle
FIXTURE_MAX_SHARE = 0.35    # an enclosed outline inside a room, at most this big, is furniture
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


def ink_mask(gray: np.ndarray, cap: int = INK_THRESHOLD_CAP) -> np.ndarray:
    t, _ = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return (gray < min(t, cap)).astype(np.uint8)


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


def fill_hollow_walls(ink: np.ndarray, stroke_len: int) -> Tuple[np.ndarray, float]:
    """Many architectural drawings draw walls as two parallel lines with white
    between them instead of a solid stroke. Those white channels are long,
    thin background regions (a room is wide; a letter's counter is short), so
    they are filled in to give solid walls. Returns (ink, filled share of ink)."""
    side = max(ink.shape)
    max_half = max(3.0, 0.015 * side)          # half the widest hollow wall
    bg = (1 - ink).astype(np.uint8)
    n, lab, stats, _ = cv2.connectedComponentsWithStats(bg, connectivity=4)
    if n <= 1:
        return ink, 0.0
    dist = cv2.distanceTransform(bg, cv2.DIST_L2, 3)
    widest = np.zeros(n, dtype=np.float32)
    np.maximum.at(widest, lab.ravel(), dist.ravel())
    H, W = ink.shape
    fill = np.zeros(n, dtype=bool)
    for i in range(1, n):
        x, y, w, h, area = (int(v) for v in stats[i])
        if x == 0 or y == 0 or x + w >= W or y + h >= H:
            continue  # the page around the building
        if widest[i] <= max_half and max(w, h) >= stroke_len and area >= 2 * stroke_len:
            fill[i] = True
    if not fill.any():
        return ink, 0.0
    # A window in such a wall is drawn as three or more lines across the
    # opening: its channels are much narrower than the wall's own channel.
    # They stay open, so the opening is found (and typed) like any other gap.
    areas = stats[:, cv2.CC_STAT_AREA]
    ids = np.flatnonzero(fill)
    order = ids[np.argsort(widest[ids])]
    cum = np.cumsum(areas[order])
    typical = widest[order[np.searchsorted(cum, cum[-1] / 2)]]
    fill[ids[widest[ids] < 0.6 * typical]] = False
    # Stair treads also leave long thin channels, but stacked side by side; a
    # wall's channel has none parallel right next to it.
    bars = []
    for i in np.flatnonzero(fill):
        x, y, w, h, area = (int(v) for v in stats[i])
        if area >= 0.6 * w * h:
            bars.append((i, x, y, w, h))
    for i, x, y, w, h in bars:
        reach = 2 * widest[i] + 3
        stacked = 0
        for j, x2, y2, w2, h2 in bars:
            if j == i or (w > h) != (w2 > h2):
                continue
            if w > h:
                near = min(abs(y2 - (y + h)), abs(y - (y2 + h2))) <= reach
                overlap = min(x + w, x2 + w2) - max(x, x2) >= 0.5 * min(w, w2)
            else:
                near = min(abs(x2 - (x + w)), abs(x - (x2 + w2))) <= reach
                overlap = min(y + h, y2 + h2) - max(y, y2) >= 0.5 * min(h, h2)
            stacked += near and overlap
        if stacked >= 2:
            fill[i] = False
    # Furniture outlines (a sofa with its cushions, a bed with its pillows)
    # also enclose thin channels, but filling them makes a solid block, not a
    # wall-thick stroke: such channels are left empty.
    solid = (ink | fill[lab]).astype(np.uint8)
    depth = cv2.distanceTransform(solid, cv2.DIST_L2, 3)
    deepest = np.zeros(n, dtype=np.float32)
    np.maximum.at(deepest, lab.ravel(), np.where(fill[lab], depth, 0).ravel())
    fill[np.flatnonzero(fill & (deepest > 2.0 * (typical + 2.0)))] = False
    added = fill[lab]
    return (ink | added).astype(np.uint8), float(added.sum()) / max(1, int(ink.sum()))


def _thick_stroke_classes(ink: np.ndarray, stroke_len: int, base: int, side: int,
                          share: float = 0.1, minimum: int = 3) -> List[int]:
    """Thicknesses (px) of the wall classes among the long strokes."""
    kmax = max(3, int(side * 0.03))
    counts = [base]
    for k in range(2, kmax + 2):
        counts.append(int(_long_strokes(_open(ink, k, k), stroke_len).sum()))
    # counts[i] is the long-stroke mass surviving an (i+1) x (i+1) opening, so
    # counts[i-1] - counts[i] is the mass of long strokes exactly i px thick:
    # a thickness histogram. Text, dimension lines and door arcs sit at 1-2 px;
    # each wall class (partitions, outer walls) is a separate peak above that.
    mass = {t: counts[t - 1] - counts[t] for t in range(1, len(counts))}
    return [t for t, m in mass.items() if t >= minimum and m >= share * base]


def merge_double_lines(ink: np.ndarray, stroke_len: int) -> Tuple[np.ndarray, int]:
    """CAD-style plans often draw each wall as two thin parallel lines whose
    gap is open at doors and corners, so the gap is not a closed channel
    (fill_hollow_walls cannot see it). The most common spacing between
    parallel long lines is the wall's width; pairs of long lines at most that
    far apart are filled in between. Returns (ink, spacing px; 0 = none)."""
    side = max(ink.shape)
    horizontal = _open(ink, stroke_len, 1)
    vertical = _open(ink, 1, stroke_len)
    gmax = max(4, int(side * 0.03))
    hist = np.zeros(gmax + 1, dtype=np.int64)
    for lines in (horizontal, vertical.T):
        for col in lines.T:
            on = np.flatnonzero(col)
            if on.size < 2:
                continue
            gaps = np.diff(on) - 1
            np.add.at(hist, gaps[(gaps >= 3) & (gaps <= gmax)], 1)
    if not hist.any():
        return ink, 0
    g = int(np.argmax(hist))
    bridged = cv2.morphologyEx(horizontal, cv2.MORPH_CLOSE, _rect(1, g + 2))         | cv2.morphologyEx(vertical, cv2.MORPH_CLOSE, _rect(g + 2, 1))
    added = (bridged & (1 - ink)).astype(np.uint8)
    merged = (ink | added).astype(np.uint8)
    # Evenly spaced parallel lines (stair treads, hatching) would merge into
    # a solid block; a wall is only about one spacing thick, so fills that
    # end up deeper than that are undone.
    t = 2 * g + 4  # thicker than a wall plus a window's glazing lines
    blocks = cv2.dilate(_open(merged, t, t), _rect(3, 3))
    merged[(blocks > 0) & (added > 0)] = 0
    return merged, g


def detect_walls(gray: np.ndarray, double_lines: bool = False) -> Optional[Dict[str, Any]]:
    """Stages 1-3. Returns None when nothing wall-like is found. With
    double_lines, walls drawn as two thin parallel lines are merged first
    (the caller retries with it when the plain reading finds no plan)."""
    # Thin anti-aliased CAD lines are often lighter grey than the usual ink
    # cut-off; on a white page with no colour fills they still count as ink.
    white_page = float(np.median(gray)) >= 245 and float(np.mean((gray > 200) & (gray < 240))) < 0.12
    ink = ink_mask(gray, LINE_ART_THRESHOLD_CAP if double_lines and white_page else INK_THRESHOLD_CAP)
    side = max(gray.shape)
    stroke_len = max(15, int(side * 0.03))
    if double_lines:
        ink, spacing = merge_double_lines(ink, stroke_len)
        if not spacing:
            return None
    base = int(_long_strokes(ink, stroke_len).sum())
    if base == 0:
        return None
    hollow = False
    if not double_lines and not _thick_stroke_classes(ink, stroke_len, base, side):
        # No solid walls at all: either single-line walls (fine as they are)
        # or outlined walls, whose channels are then a large share of the ink.
        filled, share = fill_hollow_walls(ink, stroke_len)
        if share > 0.5:
            ink, hollow = filled, True
            base = int(_long_strokes(ink, stroke_len).sum())

    walls_classes = _thick_stroke_classes(ink, stroke_len, base, side)
    thin = min(walls_classes) if walls_classes else 1
    if double_lines:
        # Merged walls vary with the drawn spacing (partitions are drawn
        # narrower), so smaller wall classes count too; the 1-2 px linework
        # of furniture and text is still removed.
        thin = min(walls_classes + _thick_stroke_classes(ink, stroke_len, base, side, share=0.03,
                                                         minimum=max(3, spacing // 2)), default=4)
    # Open just below the thinnest wall class: removes thin linework but keeps
    # every wall, partitions included.
    k = thin
    k_open = max(1, int(round(0.6 * thin))) if thin >= 3 else 1
    if double_lines:
        k_open = max(3, k_open)

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
    if double_lines:
        # Merged furniture outlines (beds, sofas, tables) are small islands
        # inside rooms; wall pieces are long, or join other walls, or sit on
        # the building's outline.
        short = 0.15 * max(w, h)
        edge = 3 * k
        for i in list(inside):
            b = box(i)
            if max(b[2] - b[0], b[3] - b[1]) >= short or i == main:
                continue
            on_outline = b[0] - x <= edge or b[1] - y <= edge or x + w - b[2] <= edge or y + h - b[3] <= edge
            grown = cv2.dilate((labels[max(0, b[1] - 3):b[3] + 3, max(0, b[0] - 3):b[2] + 3] == i)
                               .astype(np.uint8), _rect(5, 5))
            nearby = labels[max(0, b[1] - 3):b[3] + 3, max(0, b[0] - 3):b[2] + 3][grown > 0]
            touches = any(j in inside and j != i for j in np.unique(nearby).tolist())
            if not on_outline and not touches:
                inside.discard(i)
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
        "hollow_walls": hollow,
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
            if i != j and stats[i, cv2.CC_STAT_AREA] < FIXTURE_MAX_SHARE * stats[j, cv2.CC_STAT_AREA] \
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
    return {"rooms": rooms, "openings": openings, "closed": closed, "labels": labels, "fixtures": fixtures,
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
        # Lines running along the gap (window glazing), found by darkness
        # relative to the gap's own paper colour rather than the global ink
        # threshold, so faint or blurred lines on scans still count.
        grey = cv2.cvtColor(bgr[y:y + h, x:x + w], cv2.COLOR_BGR2GRAY).astype(float)
        profile = grey.mean(axis=1 if horizontal else 0)
        paper = float(np.percentile(profile, 90)) if profile.size else 255.0
        lines = (profile < paper - 35) | (ink[y:y + h, x:x + w].mean(axis=1 if horizontal else 0) > 0.7)
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
