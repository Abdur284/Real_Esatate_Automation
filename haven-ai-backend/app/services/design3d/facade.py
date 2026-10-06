"""
Applies an image-derived facade description to a 3D model.

The photo analysis (reference.py) only yields counts, colours and styles for
the road-facing elevation. This module turns those into exact geometry with
fixed, conventional sizes: doors and windows are spread along the front walls,
balconies are cantilevered off the front at a floor's slab level, and the
colours/cladding are attached as an `appearance` block for the viewer. Nothing
here is measured from the photo.
"""
import re
from typing import Any, Dict, List, Tuple

# (width, height, sill) in feet for each window style.
WINDOW_STYLES = {
    "standard": (4.0, 4.0, 3.0),
    "large": (6.0, 5.0, 2.0),
    "full_height": (5.0, 7.5, 0.5),
}
DOOR = (3.5, 7.0, 0.0)
GARAGE_DOOR = (9.0, 7.5, 0.0)
SMALL_WINDOW = (3.0, 3.5, 3.5)

EDGE_MARGIN_FT = 0.5       # keep openings off wall ends / corners
MIN_GAP_FT = 1.0           # solid wall between two openings
BALCONY_DEPTH_FT = 4.0
BALCONY_RAILING_FT = 3.5

DEFAULT_APPEARANCE = {
    "walls": "#f1f5f9", "facade": "#e2e8f0", "trim": "#94a3b8", "roof": "#b0b8c4",
    "window_frames": "#334155", "door": "#8b5e34",
}
CLADDINGS = {"none", "stone", "brick", "wood", "tile", "concrete", "glass"}
_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _int(v, lo: int, hi: int, default: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


def build_appearance(proposed: Dict[str, Any]) -> Dict[str, Any]:
    colors = proposed.get("colors") or {}
    out = {k: (colors.get(k) if isinstance(colors.get(k), str) and _HEX.match(colors.get(k)) else v)
           for k, v in DEFAULT_APPEARANCE.items()}
    cladding = str(proposed.get("facade_cladding") or "none").lower()
    out["cladding"] = cladding if cladding in CLADDINGS else "none"
    out["style"] = str(proposed.get("style") or "")[:80]
    return out


def _front_walls(storey: Dict[str, Any]) -> List[Dict[str, Any]]:
    return sorted((w for w in storey["walls"]
                   if w["exterior"] and not w.get("parapet")
                   and abs(w["y1"]) < 1e-6 and abs(w["y2"]) < 1e-6),
                  key=lambda w: min(w["x1"], w["x2"]))


def _free_gaps(walls: List[Dict], height_needed: float) -> List[Tuple[Dict, float, float]]:
    """Free stretches of the front walls as (wall, start_x, end_x), already
    keeping clear of wall ends and of openings placed so far."""
    gaps = []
    for wall in walls:
        if height_needed > wall["height"]:
            continue
        start = min(wall["x1"], wall["x2"])
        blocked = sorted((start + o["center"] - o["width"] / 2 - MIN_GAP_FT,
                          start + o["center"] + o["width"] / 2 + MIN_GAP_FT) for o in wall["openings"])
        cursor = start + EDGE_MARGIN_FT
        for lo, hi in blocked + [(start + wall["length"] - EDGE_MARGIN_FT, float("inf"))]:
            if lo > cursor:
                gaps.append((wall, cursor, lo))
            cursor = max(cursor, hi)
    return gaps


def _add(wall: Dict, x: float, spec: Tuple[float, float, float], kind: str) -> None:
    width, height, sill = spec
    wall["openings"].append({"type": "window" if kind == "window" else "door",
                             "center": round(x - min(wall["x1"], wall["x2"]), 2),
                             "width": width, "height": height, "sill": sill})
    wall["openings"].sort(key=lambda o: o["center"])


def _place(walls: List[Dict], center: float, spec: Tuple[float, float, float], kind: str) -> bool:
    """Puts one door as close to `center` (x, feet) as the free wall allows."""
    width, height, sill = spec
    best = None
    for wall, a, b in _free_gaps(walls, sill + height):
        if b - a < width:
            continue
        x = min(max(center, a + width / 2), b - width / 2)
        if best is None or abs(x - center) < abs(best[1] - center):
            best = (wall, x)
    if best is None:
        return False
    _add(best[0], best[1], spec, kind)
    return True


def _place_windows(walls: List[Dict], count: int, style: Tuple[float, float, float]) -> int:
    """Spreads `count` windows evenly over the free wall, falling back to
    smaller windows before leaving any out. Returns how many were placed."""
    if count <= 0:
        return 0
    specs = [style] + [s for s in (WINDOW_STYLES["standard"], SMALL_WINDOW) if s[0] < style[0]]
    for i, spec in enumerate(specs):
        width = spec[0]
        # A gap is already clear of its neighbours, so only the space between
        # two windows inside it needs MIN_GAP_FT.
        gaps = [(w, a, b, int((b - a + MIN_GAP_FT) // (width + MIN_GAP_FT)))
                for w, a, b in _free_gaps(walls, spec[1] + spec[2])]
        gaps = [g for g in gaps if g[3] > 0]
        capacity = sum(g[3] for g in gaps)
        if capacity < count and i < len(specs) - 1:
            continue
        n = min(count, capacity)
        # Share the windows out in proportion to each gap's capacity.
        shares = [min(g[3], int(n * g[3] / capacity)) for g in gaps] if capacity else []
        for j in sorted(range(len(gaps)), key=lambda j: -gaps[j][3]):
            while sum(shares) < n and shares[j] < gaps[j][3]:
                shares[j] += 1
        for (wall, a, b, _), k in zip(gaps, shares):
            if k == 0:
                continue
            between = max(MIN_GAP_FT, (b - a - k * width) / (k + 1))
            end = (b - a - k * width - (k - 1) * between) / 2
            for m in range(k):
                _add(wall, a + end + m * (width + between) + width / 2, spec, "window")
        return n
    return 0


def apply_facade(model: Dict[str, Any], proposed: Dict[str, Any]) -> List[str]:
    """Mutates `model` in place; returns notes about anything that could not
    be applied exactly."""
    notes: List[str] = []
    width = model["footprint"]["width_ft"]
    front_setback = model["footprint"].get("front_setback_ft", BALCONY_DEPTH_FT + 1)
    elevations = {s["level"]: s for s in model["storeys"]}
    per_level = {(_int(e.get("level"), 1, 9, 0)): e for e in proposed.get("front_elevation") or []
                 if isinstance(e, dict)}

    balconies = []
    for b in proposed.get("balconies") or []:
        if not isinstance(b, dict):
            continue
        level = _int(b.get("level"), 1, 9, 0)
        if level < 2 or level not in elevations:
            notes.append(f"A balcony on level {b.get('level')} was skipped: balconies need an upper floor "
                         f"that exists in this {len(elevations)}-storey model.")
            continue
        position = str(b.get("position") or "center").lower()
        try:
            fraction = float(b.get("width_fraction") or 0.4)
        except (TypeError, ValueError):
            fraction = 0.4
        bw = width if position == "full_width" else min(width, max(6.0, width * max(0.2, min(fraction, 1.0))))
        bx = {"left": 0.0, "right": width - bw}.get(position, (width - bw) / 2)
        depth = min(BALCONY_DEPTH_FT, max(front_setback - 0.5, 2.0))
        balconies.append({
            "level": level, "x": round(bx, 2), "y": round(-depth, 2),
            "width": round(bw, 2), "depth": round(depth, 2),
            "elevation": elevations[level]["elevation_ft"],
            "slab_thickness": 0.5, "railing_height": BALCONY_RAILING_FT,
            "railing": "glass" if any(k in str(proposed.get("style", "")).lower()
                                      for k in ("modern", "contemporary", "minimal")) else "solid",
        })
    model["balconies"] = balconies

    for level, storey in elevations.items():
        spec = per_level.get(level)
        walls = _front_walls(storey)
        if spec is None or not walls:
            continue
        for w in walls:  # the photo-derived elevation replaces the generated one
            w["openings"] = []

        window = WINDOW_STYLES.get(str(spec.get("window_style") or "standard").lower(), WINDOW_STYLES["standard"])
        doors = _int(spec.get("doors"), 0, 4, 1 if level == 1 else 0)
        windows = _int(spec.get("windows"), 0, 12, 2)
        balcony = next((b for b in balconies if b["level"] == level), None)
        placed = {"door": 0, "window": 0}

        left = 0.0
        if level == 1 and spec.get("garage_door"):
            if _place(walls, EDGE_MARGIN_FT + GARAGE_DOOR[0] / 2, GARAGE_DOOR, "garage"):
                left = GARAGE_DOOR[0] + EDGE_MARGIN_FT
            else:
                notes.append("The garage door could not be placed: the front of the ground floor is an "
                             "open car porch or too narrow in this model.")
        # A balcony is reached through a door on its floor (want_doors below).

        want_doors = max(doors, 1 if balcony else 0)
        door_centers = [balcony["x"] + balcony["width"] / 2] if balcony else []
        span_mid = (left + width) / 2
        while len(door_centers) < want_doors:
            k = len(door_centers)
            door_centers.append(span_mid + (k - (want_doors - 1) / 2) * (DOOR[0] + 4))
        placed["door"] = sum(_place(walls, c, DOOR, "door") for c in door_centers)
        placed["window"] = _place_windows(walls, windows, window)

        if placed["door"] < want_doors or placed["window"] < windows:
            notes.append(f"{storey['label']}: placed {placed['door']}/{want_doors} front door(s) and "
                         f"{placed['window']}/{windows} front window(s); the rest did not fit the "
                         f"front wall of this model.")
    return notes
