"""
Converts a 2D floor plan (from the 2D Design module) into the same 3D model
structure build_model() produces, so the existing Three.js viewer can show it.

The 2D plan's rooms are arbitrary rectangles (not the full-width bands the 3D
packer makes), so walls cannot be de-duplicated by identical room edges.
Instead every wall line is cut at all room corners on it into elementary
segments, each segment is classified by what lies on either side of it, and
neighbouring segments with the same classification are merged back.

Coordinates stay in plot space (feet, origin at the plot's front-left corner,
y = depth from the road), which is also the 2D plan's convention, so the
footprint origin is (0, 0).
"""
from typing import Any, Dict, List, Optional, Tuple

from .model_builder import (
    DOOR_HEIGHT_FT,
    EXT_WALL_THICKNESS_FT,
    INT_WALL_THICKNESS_FT,
    PARAPET_HEIGHT_FT,
    SLAB_THICKNESS_FT,
    STAIR_STEPS,
    STOREY_LABELS,
    STOREY_PITCH_FT,
    WALL_HEIGHT_FT,
    WINDOW_HEIGHT_FT,
    WINDOW_SILL_FT,
)
from .arch_defaults import PLAUSIBLE_WALL_THICKNESS_FT

FLOOR_KEYS = ("ground_floor", "first_floor")
SECTIONS = ("rooms", "circulation", "open_spaces")
EPS = 1e-6

# Open to the sky: no roof or slab above, no full-height walls of their own.
OPEN_AIR = {"courtyard", "lawn", "setback", "terrace", "balcony"}
# Roofed but not walled in: walls come only from enclosed neighbours or the
# building's outside edge.
COVERED_OPEN = {"corridor", "lobby", "entrance"}
# A car porch stays open on its outside edges so a car can drive in.
PORCH = {"parking"}

# 2D room types -> the type names the 3D viewer colours.
TYPE_MAP = {
    "staircase": "stairs", "master_bedroom": "bedroom", "guest_room": "bedroom",
    "servant_room": "bedroom", "living_room": "tv_lounge", "store": "store_room",
    "laundry": "store_room", "lobby": "corridor", "entrance": "corridor",
    "garage": "parking", "balcony": "terrace", "setback": "lawn",
}


def _num(v) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def _items(floor: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = []
    for section in SECTIONS:
        for it in (floor or {}).get(section) or []:
            if not isinstance(it, dict):
                continue
            rect = [_num(it.get(k)) for k in ("x", "y", "width", "length")]
            if None in rect or rect[2] <= 0 or rect[3] <= 0:
                continue
            itype = str(it.get("type") or "other").lower()
            if section == "open_spaces" and itype not in PORCH:
                itype = itype if itype in OPEN_AIR else "courtyard"
            # Rooms that are not rectangles (e.g. an L-shape read from an image)
            # arrive as several rectangles sharing one `group`.
            group = it.get("group")
            out.append({"src": it, "type": itype, "x": rect[0], "y": rect[1],
                        "w": rect[2], "d": rect[3], "name": str(it.get("name") or itype),
                        "group": str(group) if isinstance(group, (str, int)) and group != "" else None})
    return out


def _enclosed(it) -> bool:
    return it is not None and it["type"] not in OPEN_AIR | COVERED_OPEN | PORCH


def _roofed(it) -> bool:
    """Counts as inside the building envelope for exterior-wall purposes."""
    return it is not None and it["type"] not in OPEN_AIR | PORCH


def _classify(a, b, level: int) -> Optional[Tuple[str, bool]]:
    """What (if anything) stands on a segment with item a on one side and b on
    the other. Returns (kind, exterior) with kind 'wall' or 'parapet'."""
    if a is not None and b is not None and a["group"] and a["group"] == b["group"]:
        return None  # two parts of the same room
    if _enclosed(a) or _enclosed(b):
        return "wall", not (_roofed(a) and _roofed(b))
    for x, y in ((a, b), (b, a)):
        if x is not None and x["type"] in COVERED_OPEN and not _roofed(y) and (y is None or y["type"] not in PORCH):
            return "wall", True
    if level > 1:
        for x, y in ((a, b), (b, a)):
            if x is not None and x["type"] in OPEN_AIR and y is None:
                return "parapet", True
    return None


def _build_walls(items: List[Dict], level: int, ext_t: float = EXT_WALL_THICKNESS_FT,
                 int_t: float = INT_WALL_THICKNESS_FT) -> List[Dict]:
    walls: List[Dict] = []
    for orient in ("h", "v"):
        # line coordinate -> list of (start, end, item, side); side 0 = the item
        # lies before the line (below / left), 1 = after it (above / right).
        lines: Dict[float, List] = {}
        for it in items:
            if orient == "h":
                edges = [(it["y"], it["x"], it["x"] + it["w"], 1), (it["y"] + it["d"], it["x"], it["x"] + it["w"], 0)]
            else:
                edges = [(it["x"], it["y"], it["y"] + it["d"], 1), (it["x"] + it["w"], it["y"], it["y"] + it["d"], 0)]
            for coord, s, e, side in edges:
                lines.setdefault(round(coord, 2), []).append((s, e, it, side))

        for coord, edges in sorted(lines.items()):
            cuts = sorted({round(v, 2) for s, e, _, _ in edges for v in (s, e)})
            current = None
            for s, e in zip(cuts, cuts[1:]):
                if e - s < EPS:
                    continue
                mid = (s + e) / 2
                sides = [None, None]
                for es, ee, it, side in edges:
                    if es - EPS <= mid <= ee + EPS:
                        sides[side] = it
                kind = _classify(sides[0], sides[1], level)
                if kind and current and current["_kind"] == kind and abs(current["_end"] - s) < EPS:
                    current["_end"] = e
                    continue
                if current:
                    walls.append(current)
                current = {"_kind": kind, "_start": s, "_end": e, "_orient": orient, "_coord": coord} if kind else None
            if current:
                walls.append(current)

    out = []
    for i, w in enumerate(walls, 1):
        kind, exterior = w["_kind"]
        s, e, c = w["_start"], w["_end"], w["_coord"]
        x1, y1, x2, y2 = (s, c, e, c) if w["_orient"] == "h" else (c, s, c, e)
        out.append({
            "id": f"w{level}_{i}",
            "x1": round(x1, 2), "y1": round(y1, 2), "x2": round(x2, 2), "y2": round(y2, 2),
            "length": round(e - s, 2),
            "thickness": ext_t if exterior else int_t,
            "height": PARAPET_HEIGHT_FT if kind == "parapet" else WALL_HEIGHT_FT,
            "exterior": exterior,
            "parapet": kind == "parapet",
            "openings": [],
        })
    return out


def _place_openings(items: List[Dict], walls: List[Dict]) -> int:
    """Maps each 2D door/window onto the 3D wall segment it sits on. Returns
    how many openings could not be placed (no wall there, or a clash)."""
    skipped = 0
    for it in items:
        for kind in ("doors", "windows"):
            for op in it["src"].get(kind) or []:
                if not isinstance(op, dict):
                    continue
                wall_side = str(op.get("wall", "")).lower()
                off = _num(op.get("offset_ft")) or 0.0
                width = _num(op.get("width_ft")) or (3.0 if kind == "doors" else 4.0)
                if wall_side in ("south", "north"):
                    orient, coord = "h", it["y"] if wall_side == "south" else it["y"] + it["d"]
                    a = it["x"] + off
                elif wall_side in ("west", "east"):
                    orient, coord = "v", it["x"] if wall_side == "west" else it["x"] + it["w"]
                    a = it["y"] + off
                else:
                    skipped += 1
                    continue
                b = a + width
                host = None
                for w in walls:
                    horiz = abs(w["y1"] - w["y2"]) < EPS
                    if w["parapet"] or horiz != (orient == "h"):
                        continue
                    if abs((w["y1"] if horiz else w["x1"]) - coord) > 0.05:
                        continue
                    ws = w["x1"] if horiz else w["y1"]
                    if ws - 0.05 <= a and b <= ws + w["length"] + 0.05:
                        host = w
                        break
                if host is None:
                    skipped += 1
                    continue
                ws = host["x1"] if abs(host["y1"] - host["y2"]) < EPS else host["y1"]
                lo, hi = max(a - ws, 0.0), min(b - ws, host["length"])
                if any(lo < o["center"] + o["width"] / 2 and hi > o["center"] - o["width"] / 2
                       for o in host["openings"]):
                    continue  # same opening listed by the rooms on both sides
                is_door = kind == "doors"
                host["openings"].append({
                    "type": "door" if is_door else "window",
                    "center": round((lo + hi) / 2, 2), "width": round(hi - lo, 2),
                    "height": DOOR_HEIGHT_FT if is_door else WINDOW_HEIGHT_FT,
                    "sill": 0.0 if is_door else WINDOW_SILL_FT,
                })
    for w in walls:
        w["openings"].sort(key=lambda o: o["center"])
    return skipped


def _subtract(rect, others) -> List[Tuple[float, float, float, float]]:
    """rect minus the union of others, as a list of (x, y, w, d) rectangles."""
    x, y, w, d = rect
    xs = sorted({x, x + w, *[min(max(v, x), x + w) for o in others for v in (o[0], o[0] + o[2])]})
    ys = sorted({y, y + d, *[min(max(v, y), y + d) for o in others for v in (o[1], o[1] + o[3])]})
    out = []
    for y0, y1 in zip(ys, ys[1:]):
        if y1 - y0 < EPS:
            continue
        runs: List[List[float]] = []  # merged free x-intervals in this row
        for x0, x1 in zip(xs, xs[1:]):
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            covered = any(o[0] <= cx <= o[0] + o[2] and o[1] <= cy <= o[1] + o[3] for o in others)
            if covered or x1 - x0 < EPS:
                continue
            if runs and abs(runs[-1][1] - x0) < EPS:
                runs[-1][1] = x1
            else:
                runs.append([x0, x1])
        out.extend((a, y0, b - a, y1 - y0) for a, b in runs)
    return out


def _rect(it) -> Tuple[float, float, float, float]:
    return (it["x"], it["y"], it["w"], it["d"])


def _wall_thickness(plan: Dict[str, Any]) -> Tuple[float, float]:
    """Wall thicknesses measured from an uploaded drawing (plan.structure),
    used only when plausible; otherwise the architectural defaults."""
    lo, hi = PLAUSIBLE_WALL_THICKNESS_FT
    structure = plan.get("structure") if isinstance(plan.get("structure"), dict) else {}
    out = []
    for key, default in (("exterior_wall_thickness_ft", EXT_WALL_THICKNESS_FT),
                         ("interior_wall_thickness_ft", INT_WALL_THICKNESS_FT)):
        v = _num(structure.get(key))
        out.append(round(v, 3) if v is not None and lo <= v <= hi else default)
    return out[0], out[1]


def build_model_from_plan2d(plan: Dict[str, Any]) -> Dict[str, Any]:
    plot = plan.get("plot") or {}
    ext_t, int_t = _wall_thickness(plan)
    pw, pl = _num(plot.get("width_ft")), _num(plot.get("length_ft"))
    design = plan.get("design") or {}
    floor_count = 2 if design.get("floors") == 2 else 1
    floors = [_items(design.get(k)) for k in FLOOR_KEYS[:floor_count]]

    storeys = []
    skipped_openings = 0
    for index, items in enumerate(floors):
        level = index + 1
        elevation = round(index * STOREY_PITCH_FT, 2)
        walls = _build_walls(items, level, ext_t, int_t)
        skipped_openings += _place_openings(items, walls)

        rooms = [{
            "id": f"r{level}_{i}",
            "type": TYPE_MAP.get(it["type"], it["type"]),
            "label": it["name"],
            "x": it["x"], "y": it["y"], "width": it["w"], "depth": it["d"],
            "enclosed": _enclosed(it),
            **({"group": it["group"]} if it["group"] else {}),
            **({"detection": it["src"]["detection"]} if isinstance(it["src"].get("detection"), dict) else {}),
        } for i, it in enumerate(items, 1)]

        # Ground floor: a slab under the built area. Upper floor: a slab under
        # every room and terrace, which also roofs the ground floor below it.
        slab_items = items if level > 1 else [it for it in items if it["type"] not in OPEN_AIR]
        stair = next((it for it in items if it["type"] == "staircase"), None)
        storeys.append({
            "level": level,
            "label": STOREY_LABELS.get(level, f"Floor {level}"),
            "elevation_ft": elevation,
            "wall_height_ft": WALL_HEIGHT_FT,
            "slabs": [{"x": it["x"], "y": it["y"], "width": it["w"], "depth": it["d"],
                       "thickness": SLAB_THICKNESS_FT, "elevation": elevation}
                      for it in slab_items if not (level > 1 and it["type"] == "staircase")],
            "rooms": rooms,
            "walls": walls,
            "covered_area_sqft": round(sum(it["w"] * it["d"] for it in items
                                           if it["type"] not in OPEN_AIR), 1),
            "stairs": {
                "x": stair["x"], "y": stair["y"], "width": stair["w"], "depth": stair["d"],
                "base_elevation": elevation, "total_rise": STOREY_PITCH_FT, "steps": STAIR_STEPS,
            } if stair and level < floor_count else None,
        })

    # Roof: over the top floor's roofed rooms, plus any part of the ground
    # floor's roofed area that the first floor does not already cover.
    top = floors[-1]
    roof_pieces = [{"x": it["x"], "y": it["y"], "width": it["w"], "depth": it["d"],
                    "elevation": round(floor_count * STOREY_PITCH_FT, 2)}
                   for it in top if it["type"] not in OPEN_AIR]
    if floor_count == 2:
        upper = [_rect(it) for it in floors[1]]
        for it in floors[0]:
            if it["type"] in OPEN_AIR:
                continue
            for x, y, w, d in _subtract(_rect(it), upper):
                roof_pieces.append({"x": round(x, 2), "y": round(y, 2), "width": round(w, 2),
                                    "depth": round(d, 2), "elevation": STOREY_PITCH_FT})

    built = [it for items in floors for it in items if it["type"] not in OPEN_AIR]
    min_x = min((it["x"] for it in built), default=0.0)
    min_y = min((it["y"] for it in built), default=0.0)
    max_x = max((it["x"] + it["w"] for it in built), default=0.0)
    max_y = max((it["y"] + it["d"] for it in built), default=0.0)
    roof_elevation = round(floor_count * STOREY_PITCH_FT, 2)

    model = {
        "source": plan.get("source") if plan.get("source") in ("image_analysis", "embedded_plan") else "plan2d",
        "wall_thickness_ft": {"exterior": ext_t, "interior": int_t},
        "plot": {"width_ft": pw, "length_ft": pl},
        "footprint": {
            "origin_x_ft": 0.0, "origin_y_ft": 0.0,
            "width_ft": round(max_x - min_x, 2), "depth_ft": round(max_y - min_y, 2),
        },
        "storeys": storeys,
        "roof": {
            "type": "flat",
            "pieces": roof_pieces,
            "thickness": SLAB_THICKNESS_FT,
            "elevation": roof_elevation,
            "parapet_height": PARAPET_HEIGHT_FT,
            "parapet_thickness": EXT_WALL_THICKNESS_FT,
        },
        "totals": {
            "storeys": len(storeys),
            "covered_area_sqft": round(sum(s["covered_area_sqft"] for s in storeys), 1),
            "building_height_ft": round(roof_elevation + SLAB_THICKNESS_FT, 2),
            "plot_area_sqft": round(pw * pl, 1),
        },
    }
    return {"model": model, "skipped_openings": skipped_openings}


def generate_3d_from_plan2d(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Entry point for the REST endpoint. Re-validates the plan (it arrives
    from the browser, so it cannot be trusted) before converting it."""
    import copy
    from app.services.design2d.validator import DESIGN_STATUSES, validate_plan

    plan = copy.deepcopy(plan) if isinstance(plan, dict) else {}
    status = plan.get("status")
    if status not in DESIGN_STATUSES:
        return {"status": "NOT_FEASIBLE",
                "message": f"Only a feasible 2D floor plan can be converted to 3D (this one is {status})."}

    report = validate_plan(plan)
    geometry_errors = [e for e in report["errors"]
                       if "outside" in e or "overlaps" in e or "numeric" in e or "non-positive" in e
                       or "plot." in e]
    if geometry_errors:
        return {"status": "NOT_FEASIBLE",
                "message": "The 2D plan's geometry is invalid, so it cannot be built in 3D: "
                           + "; ".join(geometry_errors[:3])}

    result = build_model_from_plan2d(plan)
    model = result["model"]
    thickness = model["wall_thickness_ft"]
    measured = model["source"] == "image_analysis" and (
        thickness["exterior"] != EXT_WALL_THICKNESS_FT or thickness["interior"] != INT_WALL_THICKNESS_FT)
    first = ("Built from the floor plan read from your image: room positions and sizes are the "
             "reviewed analysis results, scaled from the dimensions you gave."
             if model["source"] == "image_analysis" else
             "Built from your 2D floor plan: room positions and sizes are taken exactly from it.")
    assumptions = [
        first,
        f"Floor-to-floor height assumed at {STOREY_PITCH_FT:g}ft ({WALL_HEIGHT_FT:g}ft clear); "
        f"walls {thickness['exterior'] * 12:g} inch outside and {thickness['interior'] * 12:g} inch inside"
        f"{' (measured from the drawing)' if measured else ''}.",
        "Open spaces (courtyards, lawns, terraces, balconies) are left unroofed; "
        "a car porch is left open at the front.",
        "A conceptual massing model, not a construction drawing.",
    ]
    if result["skipped_openings"]:
        assumptions.append(f"{result['skipped_openings']} door/window position(s) from the 2D plan "
                           "had no wall to sit in (e.g. an open porch) and were left out.")
    if report["errors"]:
        assumptions.append("The 2D plan had unresolved check failures: " + "; ".join(report["errors"][:3]))

    return {
        "status": "FEASIBLE",
        "source": "plan2d",
        "plan_source": model["source"],
        "message": f"Built a {model['totals']['storeys']}-storey model from your 2D floor plan.",
        "plot": model["plot"],
        "model": model,
        "assumptions": assumptions,
    }
