"""
Deterministic checks on the floor plan Gemini returns.

The layout itself is produced by the language model, so nothing here trusts
it: plot area is recomputed, every rectangle is checked against the plot
boundary and every other rectangle on its floor, floor count and staircase
rules are enforced, and room counts are compared with the requirements the
model itself extracted. Errors are sent back to the model for one repair
attempt; anything still wrong is reported to the user rather than hidden.
"""
from typing import Any, Dict, List, Tuple

VALID_STATUSES = {"FEASIBLE", "FEASIBLE_WITH_TWO_FLOORS", "NOT_FEASIBLE", "INSUFFICIENT_INFORMATION"}
DESIGN_STATUSES = {"FEASIBLE", "FEASIBLE_WITH_TWO_FLOORS"}
FLOOR_KEYS = ("ground_floor", "first_floor")
SECTIONS = ("rooms", "circulation", "open_spaces")
WALLS = {"north", "south", "east", "west"}

EDGE_TOLERANCE_FT = 0.25     # rounding slack at the plot boundary
OVERLAP_TOLERANCE_SQFT = 1.0  # ignore sliver overlaps from rounding

MIN_ROOM_SIZES_FT = {
    # (shorter side, longer side) below which a room is not practical to use.
    "bedroom": (9, 10),
    "master_bedroom": (10, 12),
    "guest_room": (9, 10),
    "bathroom": (4, 6),
    "kitchen": (6, 8),
    "drawing_room": (10, 12),
    "living_room": (10, 12),
    "tv_lounge": (10, 12),
    "parking": (9, 16),
    "garage": (9, 16),
    "staircase": (3.5, 8),
}

# Which item types count towards each requirement key.
REQUIREMENT_TYPES = {
    "bedrooms": {"bedroom", "master_bedroom", "guest_room"},
    "bathrooms": {"bathroom"},
    "kitchens": {"kitchen"},
    "drawing_rooms": {"drawing_room"},
    "living_rooms": {"living_room", "tv_lounge"},
    "dining_rooms": {"dining_room"},
}


def _num(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError
    return float(value)


def _items(floor: Dict[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    out = []
    for section in SECTIONS:
        for item in floor.get(section) or []:
            if isinstance(item, dict):
                out.append((section, item))
    return out


def _overlap(a, b) -> float:
    dx = min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])
    dy = min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def _check_openings(label: str, item: Dict[str, Any], rect, warnings: List[str]):
    x, y, w, l = rect
    for kind in ("doors", "windows"):
        for op in item.get(kind) or []:
            if not isinstance(op, dict):
                continue
            wall = str(op.get("wall", "")).lower()
            try:
                off, ow = _num(op.get("offset_ft", 0)), _num(op.get("width_ft", 0))
            except ValueError:
                warnings.append(f"{label}: a {kind[:-1]} has non-numeric offset/width.")
                continue
            if wall not in WALLS:
                warnings.append(f"{label}: a {kind[:-1]} is on unknown wall '{wall}'.")
                continue
            wall_len = w if wall in ("north", "south") else l
            if off < 0 or ow <= 0 or off + ow > wall_len + EDGE_TOLERANCE_FT:
                warnings.append(f"{label}: a {kind[:-1]} on the {wall} wall does not fit "
                                f"({off:g}+{ow:g} ft on a {wall_len:g} ft wall).")


def validate_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Returns {"passed", "errors", "warnings", "corrections"}.

    errors      - geometry or rule violations (sent back for repair)
    warnings    - quality issues shown to the user
    corrections - values this function fixed in place (e.g. plot area)
    """
    errors: List[str] = []
    warnings: List[str] = []
    corrections: List[str] = []

    if not isinstance(plan, dict):
        return {"passed": False, "errors": ["Response is not a JSON object."], "warnings": [], "corrections": []}

    status = plan.get("status")
    if status not in VALID_STATUSES:
        errors.append(f"status '{status}' is not one of {sorted(VALID_STATUSES)}.")
        return {"passed": False, "errors": errors, "warnings": warnings, "corrections": corrections}

    plot = plan.get("plot") or {}
    try:
        pw, pl = _num(plot.get("width_ft")), _num(plot.get("length_ft"))
    except ValueError:
        pw = pl = None

    if status == "INSUFFICIENT_INFORMATION":
        return {"passed": True, "errors": [], "warnings": warnings, "corrections": corrections}

    if pw is None or pl is None or pw <= 0 or pl <= 0:
        errors.append("plot.width_ft and plot.length_ft must be positive numbers.")
        return {"passed": False, "errors": errors, "warnings": warnings, "corrections": corrections}

    area = round(pw * pl, 2)
    try:
        stated = _num(plot.get("area_sqft"))
    except ValueError:
        stated = None
    if stated is None or abs(stated - area) > 0.5:
        corrections.append(f"plot.area_sqft corrected from {plot.get('area_sqft')} to {area:g} "
                           f"({pw:g} x {pl:g}).")
        plot["area_sqft"] = area

    if status not in DESIGN_STATUSES:
        return {"passed": True, "errors": [], "warnings": warnings, "corrections": corrections}

    design = plan.get("design") or {}
    floors = design.get("floors")
    expected_floors = 1 if status == "FEASIBLE" else 2
    if floors != expected_floors:
        errors.append(f"status {status} requires design.floors = {expected_floors}, got {floors}.")

    counts: Dict[str, int] = {}
    stair_rects = {}
    for fi, fkey in enumerate(FLOOR_KEYS):
        floor = design.get(fkey) or {}
        items = _items(floor)
        if fi >= expected_floors:
            if items:
                errors.append(f"{fkey} must be empty for a {expected_floors}-floor design.")
            continue
        if not items:
            errors.append(f"{fkey} has no rooms.")
            continue

        rects = []
        for section, item in items:
            label = f"{fkey}.{section} '{item.get('name', '?')}'"
            try:
                rect = tuple(_num(item.get(k)) for k in ("x", "y", "width", "length"))
            except ValueError:
                errors.append(f"{label} is missing numeric x, y, width or length.")
                continue
            x, y, w, l = rect
            if w <= 0 or l <= 0:
                errors.append(f"{label} has non-positive size {w:g} x {l:g}.")
                continue
            if (x < -EDGE_TOLERANCE_FT or y < -EDGE_TOLERANCE_FT
                    or x + w > pw + EDGE_TOLERANCE_FT or y + l > pl + EDGE_TOLERANCE_FT):
                errors.append(f"{label} at ({x:g},{y:g}) size {w:g}x{l:g} extends outside the "
                              f"{pw:g} x {pl:g} ft plot.")

            dims = item.get("approximate_dimensions_ft") or {}
            if dims.get("width") != item.get("width") or dims.get("length") != item.get("length"):
                item["approximate_dimensions_ft"] = {"length": l, "width": w}

            itype = str(item.get("type", "other")).lower()
            counts[itype] = counts.get(itype, 0) + 1
            if itype == "staircase":
                stair_rects[fkey] = rect
            if itype in MIN_ROOM_SIZES_FT:
                short, long_ = MIN_ROOM_SIZES_FT[itype]
                if min(w, l) < short or max(w, l) < long_:
                    warnings.append(f"{label} is {w:g} x {l:g} ft, smaller than a practical "
                                    f"{short:g} x {long_:g} ft.")
            _check_openings(label, item, rect, warnings)
            rects.append((label, rect))

        for i in range(len(rects)):
            for j in range(i + 1, len(rects)):
                ov = _overlap(rects[i][1], rects[j][1])
                if ov > OVERLAP_TOLERANCE_SQFT:
                    errors.append(f"{rects[i][0]} overlaps {rects[j][0]} by {ov:.1f} sq ft.")

    if expected_floors == 2:
        if set(stair_rects) != set(FLOOR_KEYS):
            errors.append("A two-floor design needs a staircase (type 'staircase') on both floors.")
        else:
            g, f = stair_rects["ground_floor"], stair_rects["first_floor"]
            if any(abs(a - b) > 0.5 for a, b in zip(g, f)):
                errors.append("The staircase must have the same x, y, width, length on both floors.")

    # A staircase counted once per floor is still one staircase.
    if "staircase" in counts:
        counts["staircase"] = 1

    reqs = plan.get("requirements") or {}
    for key, types in REQUIREMENT_TYPES.items():
        want = reqs.get(key)
        if isinstance(want, (int, float)) and not isinstance(want, bool) and want > 0:
            have = sum(counts.get(t, 0) for t in types)
            if have < want:
                errors.append(f"requirements.{key} = {want:g} but the design contains only {have}.")

    parking_want = any(
        isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0
        for v in (reqs.get("parking_spaces"), reqs.get("garage")))
    if parking_want and counts.get("parking", 0) + counts.get("garage", 0) == 0:
        errors.append("Parking was requested but no item has type 'parking' or 'garage'.")

    return {"passed": not errors, "errors": errors, "warnings": warnings, "corrections": corrections}
