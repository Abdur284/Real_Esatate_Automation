"""
Pixels -> structured floor plan (feet), in the same JSON schema the 2D Design
module produces, so Layer 2 (design3d.from_plan2d) consumes both identically.

Conventions (see design3d/arch_defaults.py): origin at the drawn plan's
front-left outer corner, x to the right, y from the road (bottom of the image)
to the back. The scale comes only from dimensions the user typed; the outer
faces of the exterior walls span exactly those dimensions.

Every room rectangle is pushed out from its free floor area to the centre of
the surrounding walls, then all edges are clustered so neighbouring rooms
share exactly one wall line (and the exterior walls land on one line each).
"""
from typing import Any, Dict, List, Optional, Tuple

# Mirrors haven-ai-react/src/components/floorPlanColors.js (the legend drawn on
# HAVEN's own 2D plans). Where two types share a colour, the first one wins.
HAVEN_LEGEND: List[Tuple[str, str]] = [
    ("bedroom", "#bbf7d0"), ("master_bedroom", "#86efac"), ("guest_room", "#d9f99d"),
    ("bathroom", "#ddd6fe"), ("kitchen", "#bfdbfe"), ("dining_room", "#a5f3fc"),
    ("living_room", "#fed7aa"), ("tv_lounge", "#fdba74"), ("drawing_room", "#fecaca"),
    ("parking", "#cbd5e1"), ("staircase", "#fde68a"), ("store", "#e5e7eb"),
    ("study", "#fbcfe8"), ("prayer_room", "#f5d0fe"), ("servant_room", "#e7e5e4"),
    ("corridor", "#f1f5f9"), ("courtyard", "#d1fae5"), ("terrace", "#ccfbf1"),
]
LEGEND_TOLERANCE = 14        # max RGB distance to count as a legend colour
DISTINCTIVE_SATURATION = 25  # max-min channel spread; pale greys are ambiguous

OPEN_AIR = {"courtyard", "lawn", "terrace", "balcony", "setback"}
CIRCULATION = {"corridor", "lobby", "entrance"}
MIN_DOOR_FT = 1.5
MIN_WINDOW_FT = 1.0


def _hex(c: str) -> Tuple[int, int, int]:
    c = c.lstrip("#")
    return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


def match_legend(rgb: List[int]) -> Optional[Tuple[str, bool, float]]:
    """Returns (type, distinctive, distance) of the closest legend colour, or None."""
    best = None
    for rtype, color in HAVEN_LEGEND:
        ref = _hex(color)
        d = sum((a - b) ** 2 for a, b in zip(rgb, ref)) ** 0.5
        if d <= LEGEND_TOLERANCE and (best is None or d < best[2]):
            best = (rtype, max(ref) - min(ref) >= DISTINCTIVE_SATURATION, d)
    return best


def _cluster(values: List[float], anchors: List[float], tol: float) -> Dict[float, float]:
    """Maps each value to its cluster's representative. A cluster containing an
    anchor (an exterior wall centreline) snaps to the anchor exactly."""
    out: Dict[float, float] = {}
    pts = sorted(set(values) | set(anchors))
    group: List[float] = []

    def flush():
        if not group:
            return
        anchor = [a for a in anchors if group[0] - 1e-9 <= a <= group[-1] + 1e-9]
        rep = anchor[0] if anchor else sorted(group)[len(group) // 2]
        for v in group:
            out[v] = round(rep, 2)

    for v in pts:
        if group and (v - group[-1] > tol or v - group[0] > 2 * tol):
            flush()
            group = []
        group.append(v)
    flush()
    return out


def _snap(v: float, mapping: Dict[float, float], tol: float) -> float:
    """Nearest wall line (cluster representative) to v, if within tol."""
    reps = set(mapping.values())
    near = min(reps, key=lambda r: abs(r - v)) if reps else v
    return near if abs(near - v) <= tol else round(v, 2)


def _pretty(rtype: str) -> str:
    return rtype.replace("_", " ").title()


def build_plan(seg: Dict[str, Any], wall: Dict[str, Any], sx: float, sy: float,
               width_ft: float, depth_ft: float, room_text: Optional[Dict[str, Any]] = None
               ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Returns (plan, report). sx/sy are pixels per foot. room_text holds the
    printed labels and sizes found inside each room (see service._room_text)."""
    room_text = room_text or {"names": {}, "sizes": {}}
    bx, by, bw, bh = wall["bbox"]
    k = wall["k"]
    X = lambda px: (px - bx) / sx            # noqa: E731
    Y = lambda py: (by + bh - py) / sy       # noqa: E731
    t_ext_ft = round(wall["exterior_thickness_px"] / ((sx + sy) / 2), 3)
    tol = min(1.25, max(0.5, 1.2 * k / min(sx, sy)))
    warnings: List[str] = []

    # ── Rectangles in feet, pushed out to the wall centrelines ──
    raw = []
    for room in seg["rooms"]:
        for p in room["parts"]:
            e = p["expand"]
            raw.append({"room": room, "w": X(p["x0"] - e["west"]), "e": X(p["x1"] + e["east"]),
                        "s": Y(p["y1"] + e["south"]), "n": Y(p["y0"] - e["north"]), "expand": e})
    xs = [v for r in raw for v in (r["w"], r["e"])]
    ys = [v for r in raw for v in (r["s"], r["n"])]
    half = t_ext_ft / 2
    xmap = _cluster(xs, [half, width_ft - half], tol)
    ymap = _cluster(ys, [half, depth_ft - half], tol)

    interior_runs = []
    for r in raw:
        for side, v, anchors, m in (("west", r["w"], (half, width_ft - half), xmap),
                                    ("east", r["e"], (half, width_ft - half), xmap),
                                    ("south", r["s"], (half, depth_ft - half), ymap),
                                    ("north", r["n"], (half, depth_ft - half), ymap)):
            if r["expand"][side] > 0 and all(abs(m[v] - a) > 1e-6 for a in anchors):
                interior_runs.append(2 * r["expand"][side] / ((sx + sy) / 2))
        r.update(w=xmap[r["w"]], e=xmap[r["e"]], s=ymap[r["s"]], n=ymap[r["n"]])
    interior_runs.sort()
    t_int_ft = round(interior_runs[len(interior_runs) // 2], 3) if interior_runs else None

    # ── Room identity: printed label, then stair hatching, then HAVEN's colour legend ──
    legend = {r["label"]: match_legend(r["fill_rgb"]) for r in seg["rooms"]}
    use_all_legend = sum(1 for m in legend.values() if m and m[1]) >= 2
    counters: Dict[str, int] = {}
    items_by_label: Dict[int, List[Dict[str, Any]]] = {}
    typed = named = merged = 0
    used_names: Dict[str, int] = {}
    floor = {"rooms": [], "circulation": [], "open_spaces": []}
    for room in seg["rooms"]:
        parts = [r for r in raw if r["room"] is room and r["e"] - r["w"] >= 1.0 and r["n"] - r["s"] >= 1.0]
        if not parts:
            continue
        m = legend.get(room["label"])
        printed = room_text["names"].get(room["label"]) or []
        label_name = None
        if printed:
            # Biggest text first: the room name is usually the largest label.
            printed = sorted(printed, key=lambda t: -(t["box"][2] - t["box"][0]) * (t["box"][3] - t["box"][1]))
            names = list(dict.fromkeys(t["name"] for t in printed))
            if len(names) > 1:
                merged += 1
            rtype, source, conf = printed[0]["type"], "read_from_label", printed[0]["score"]
            label_name = " / ".join(names[:3])
            named += 1
        elif room["stairs"] >= 0.5:
            rtype, source, conf = "staircase", "inferred_from_stair_hatching", room["stairs"]
        elif m and (m[1] or use_all_legend):
            rtype, source, conf = m[0], "inferred_from_colour_legend", round(0.9 - m[2] / 100, 2)
        else:
            rtype, source, conf = "other", "unknown", 0.0
        if rtype != "other":
            typed += 1
        counters[rtype] = counters.get(rtype, 0) + 1
        name = label_name or (f"Room {sum(counters.values())}" if rtype == "other"
                              else f"{_pretty(rtype)} {counters[rtype]}")
        if label_name:
            # Two rooms printed "BEDROOM" become "Bedroom" and "Bedroom 2".
            seen = used_names.get(name.lower(), 0)
            used_names[name.lower()] = seen + 1
            if seen:
                name = f"{name} {seen + 1}"
        sizes = room_text["sizes"].get(room["label"]) or []
        group = f"g{room['label']}" if len(parts) > 1 else None
        section = "open_spaces" if rtype in OPEN_AIR else "circulation" if rtype in CIRCULATION else "rooms"
        for pi, p in enumerate(parts):
            item = {
                "id": f"room_{room['label']}" + (f"_{pi + 1}" if group else ""),
                "name": name if not group else f"{name} ({chr(65 + pi)})",
                "type": rtype,
                "x": round(p["w"], 2), "y": round(p["s"], 2),
                "width": round(p["e"] - p["w"], 2), "length": round(p["n"] - p["s"], 2),
                "doors": [], "windows": [],
                "detection": {
                    "geometry": "detected", "type_source": source, "type_confidence": conf,
                    "shape": "multi_rectangle" if group else "rectangle",
                    "shape_fit": round(room["coverage"], 2),
                    **({"fixtures_seen": room["fixtures"]} if room["fixtures"] else {}),
                    **({"label_text": [t["text"] for t in printed]} if printed else {}),
                    **({"printed_size": sizes[0]["text"]} if sizes else {}),
                },
            }
            if group:
                item["group"] = group
            floor[section].append(item)
            items_by_label.setdefault(room["label"], []).append(item)

    _resolve_overlaps(floor, warnings)

    # ── Doors and windows onto the room walls they sit in ──
    placed = {"door": 0, "window": 0}
    skipped = 0
    op_conf = []
    for op in seg["openings"]:
        hosts = []
        if op["horizontal"]:
            line = _snap(Y((op["y0"] + op["y1"]) / 2), ymap, tol)
            a, b = X(op["x0"]), X(op["x1"])
            hosts = [(op["side_a"], "south"), (op["side_b"], "north")]
        else:
            line = _snap(X((op["x0"] + op["x1"]) / 2), xmap, tol)
            a, b = Y(op["y1"]), Y(op["y0"])
            hosts = [(op["side_a"], "east"), (op["side_b"], "west")]
        names = {lab: items_by_label[lab][0]["name"] for lab, _ in hosts if lab in items_by_label}
        host = _host_part(items_by_label, hosts, line, a, b, tol)
        if host is None:
            skipped += 1
            continue
        item, wall_side, other = host
        span = item["width"] if wall_side in ("south", "north") else item["length"]
        start = item["x"] if wall_side in ("south", "north") else item["y"]
        width = round(min(b - a, span), 2)
        if width < (MIN_DOOR_FT if op["kind"] == "door" else MIN_WINDOW_FT):
            skipped += 1
            continue
        offset = round(min(max(a - start, 0.0), span - width), 2)
        entry = {"wall": wall_side, "offset_ft": offset, "width_ft": width,
                 "detection": {"source": "detected_gap", "confidence": op["confidence"]}}
        if op["kind"] == "door":
            entry["to"] = "Outside" if op["exterior"] else names.get(other, "Adjacent space")
            if width > 5.0:
                entry["detection"]["note"] = "wide opening"
        item["doors" if op["kind"] == "door" else "windows"].append(entry)
        placed[op["kind"]] += 1
        op_conf.append(op["confidence"])
    if skipped:
        warnings.append(f"{skipped} gap(s) in the walls could not be matched to a room wall and were left out.")

    walls_ft = _wall_segments(wall, X, Y, sx, sy)

    plan = {
        "status": "FEASIBLE",
        "source": "image_analysis",
        "plot": {"width_ft": round(width_ft, 2), "length_ft": round(depth_ft, 2),
                 "area_sqft": round(width_ft * depth_ft, 2)},
        "structure": {"exterior_wall_thickness_ft": t_ext_ft,
                      **({"interior_wall_thickness_ft": t_int_ft} if t_int_ft else {})},
        "design": {"floors": 1, "ground_floor": floor,
                   "first_floor": {"rooms": [], "circulation": [], "open_spaces": []}},
        "walls": walls_ft,
    }
    report = {
        "rooms": sum(len(v) for v in floor.values()),
        "distinct_rooms": len(items_by_label),
        "typed_rooms": typed,
        "named_rooms": named,
        "merged_labels": merged,
        "doors": placed["door"], "windows": placed["window"],
        "stairs": counters.get("staircase", 0),
        "opening_confidence": round(sum(op_conf) / len(op_conf), 2) if op_conf else None,
        "snap_tolerance_ft": round(tol, 2),
        "exterior_wall_thickness_ft": t_ext_ft,
        "interior_wall_thickness_ft": t_int_ft,
        "warnings": warnings,
    }
    return plan, report


def _host_part(items_by_label, hosts, line, a, b, tol):
    """Picks the room part whose wall lies on `line` and covers most of [a, b]."""
    best = None
    for lab, side in hosts:
        for item in items_by_label.get(lab, []):
            if side in ("south", "north"):
                edge = item["y"] if side == "south" else item["y"] + item["length"]
                s0, s1 = item["x"], item["x"] + item["width"]
            else:
                edge = item["x"] if side == "west" else item["x"] + item["width"]
                s0, s1 = item["y"], item["y"] + item["length"]
            if abs(edge - line) > tol:
                continue
            cover = min(b, s1) - max(a, s0)
            if cover > 0 and (best is None or cover > best[0]):
                other = next((l for l, _ in hosts if l != lab), None)
                best = (cover, item, side, other)
    return None if best is None else best[1:]


def _resolve_overlaps(floor: Dict[str, List[Dict]], warnings: List[str]) -> None:
    """Snapping can leave slivers of overlap between neighbours; trim the
    smaller rectangle along the axis with the smaller overlap."""
    items = [it for sec in floor.values() for it in sec]
    trimmed = 0
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            dx = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
            dy = min(a["y"] + a["length"], b["y"] + b["length"]) - max(a["y"], b["y"])
            if dx <= 0.01 or dy <= 0.01:
                continue
            small = a if a["width"] * a["length"] < b["width"] * b["length"] else b
            big = b if small is a else a
            if dx <= dy:
                if small["x"] < big["x"]:
                    small["width"] = round(big["x"] - small["x"], 2)
                else:
                    new_x = big["x"] + big["width"]
                    small["width"] = round(small["x"] + small["width"] - new_x, 2)
                    small["x"] = round(new_x, 2)
            else:
                if small["y"] < big["y"]:
                    small["length"] = round(big["y"] - small["y"], 2)
                else:
                    new_y = big["y"] + big["length"]
                    small["length"] = round(small["y"] + small["length"] - new_y, 2)
                    small["y"] = round(new_y, 2)
            trimmed += 1
    if trimmed:
        warnings.append(f"{trimmed} overlapping room edge(s) were trimmed after snapping to wall lines.")


def _wall_segments(wall: Dict[str, Any], X, Y, sx: float, sy: float) -> List[Dict[str, Any]]:
    """The detected wall strokes as straight segments in feet (informational;
    3D walls are rebuilt from the rooms so they always close exactly)."""
    import cv2

    walls, k = wall["walls"], wall["k"]
    piece = max(3 * k, 5)
    out = []
    for horizontal, kernel in ((True, (piece, 1)), (False, (1, piece))):
        mask = cv2.morphologyEx(walls, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, kernel))
        n, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        for i in range(1, n):
            x, y, w, h = (int(stats[i, c]) for c in (cv2.CC_STAT_LEFT, cv2.CC_STAT_TOP,
                                                      cv2.CC_STAT_WIDTH, cv2.CC_STAT_HEIGHT))
            if horizontal:
                c = Y(y + h / 2)
                start, end, t = [round(X(x), 2), round(c, 2)], [round(X(x + w), 2), round(c, 2)], h / sy
            else:
                c = X(x + w / 2)
                start, end, t = [round(c, 2), round(Y(y + h), 2)], [round(c, 2), round(Y(y), 2)], w / sx
            out.append({"id": f"wall_{len(out) + 1:02d}", "start": start, "end": end,
                        "thickness": round(t, 2), "source": "detected"})
            if len(out) >= 300:
                return out
    return out
