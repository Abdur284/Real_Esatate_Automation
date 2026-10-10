"""
Checks that a 3D model is a faithful reconstruction of the 2D plan it was
built from, before it is sent to the browser.

The 3D builder is deterministic, so these checks guard against regressions
and malformed plans rather than "creativity": every room must come out with
the same position and size, neighbouring rooms must still share their wall,
every enclosed room must be closed by walls, and every door and window must
have landed in a wall. A failed geometry check withholds the model; a door or
window that could not be placed is reported but does not block it.
"""
from typing import Any, Dict, List, Tuple

TOL_FT = 0.02


def _check(name: str, ok: bool, detail: str, blocking: bool = True) -> Dict[str, Any]:
    return {"name": name, "ok": bool(ok), "detail": detail, "blocking": blocking}


def _shares_edge(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> bool:
    ax, ay, aw, ad = a
    bx, by, bw, bd = b
    overlap_x = min(ax + aw, bx + bw) - max(ax, bx)
    overlap_y = min(ay + ad, by + bd) - max(ay, by)
    vertical = (abs(ax + aw - bx) < TOL_FT or abs(bx + bw - ax) < TOL_FT) and overlap_y > 0.5
    horizontal = (abs(ay + ad - by) < TOL_FT or abs(by + bd - ay) < TOL_FT) and overlap_x > 0.5
    return vertical or horizontal


def _covered(walls: List[Dict], horizontal: bool, coord: float, a: float, b: float) -> float:
    """Length of [a, b] on the given wall line that walls stand on."""
    spans = []
    for w in walls:
        if w.get("parapet"):
            continue
        is_h = abs(w["y1"] - w["y2"]) < 1e-6
        if is_h != horizontal:
            continue
        if abs((w["y1"] if is_h else w["x1"]) - coord) > TOL_FT:
            continue
        s, e = (w["x1"], w["x2"]) if is_h else (w["y1"], w["y2"])
        s, e = min(s, e), max(s, e)
        lo, hi = max(s, a), min(e, b)
        if hi > lo:
            spans.append((lo, hi))
    spans.sort()
    total, cur = 0.0, None
    for lo, hi in spans:
        if cur and lo <= cur[1]:
            cur = (cur[0], max(cur[1], hi))
        else:
            if cur:
                total += cur[1] - cur[0]
            cur = (lo, hi)
    if cur:
        total += cur[1] - cur[0]
    return total


def check_reconstruction(floors_items: List[List[Dict[str, Any]]], model: Dict[str, Any],
                         skipped_openings: int, enclosed) -> Dict[str, Any]:
    """floors_items: from_plan2d._items() per floor, in build order.
    enclosed: from_plan2d._enclosed."""
    checks: List[Dict[str, Any]] = []
    storeys = model["storeys"]
    plot = model["plot"]

    # 1. Same rooms, same count, same place and size, per floor.
    moved: List[str] = []
    for items, storey in zip(floors_items, storeys):
        rooms = storey["rooms"]
        if len(items) != len(rooms):
            moved.append(f"{storey['label']}: {len(items)} plan room(s) but {len(rooms)} in 3D")
            continue
        for it, room in zip(items, rooms):
            if any(abs(p - q) > TOL_FT for p, q in ((it["x"], room["x"]), (it["y"], room["y"]),
                                                    (it["w"], room["width"]), (it["d"], room["depth"]))):
                moved.append(f"{it['name']} ({storey['label']})")
    n_rooms = sum(len(s["rooms"]) for s in storeys)
    checks.append(_check("rooms", not moved,
                         f"All {n_rooms} room(s) have the plan's exact position and size."
                         if not moved else "Changed from the plan: " + "; ".join(moved[:4])))

    # 2. Neighbours in the plan are still neighbours (relative positions).
    total = kept = 0
    for items, storey in zip(floors_items, storeys):
        rooms = storey["rooms"]
        if len(items) != len(rooms):
            continue
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                a = (items[i]["x"], items[i]["y"], items[i]["w"], items[i]["d"])
                b = (items[j]["x"], items[j]["y"], items[j]["w"], items[j]["d"])
                if _shares_edge(a, b):
                    total += 1
                    ra, rb = rooms[i], rooms[j]
                    kept += _shares_edge((ra["x"], ra["y"], ra["width"], ra["depth"]),
                                         (rb["x"], rb["y"], rb["width"], rb["depth"]))
    checks.append(_check("adjacency", kept == total,
                         f"{kept} of {total} shared wall(s) between neighbouring rooms preserved."))

    # 3. No overlapping rooms, nothing outside the plot.
    problems = []
    for storey in storeys:
        rooms = storey["rooms"]
        for i, a in enumerate(rooms):
            if a["x"] < -TOL_FT or a["y"] < -TOL_FT or a["x"] + a["width"] > plot["width_ft"] + TOL_FT \
                    or a["y"] + a["depth"] > plot["length_ft"] + TOL_FT:
                problems.append(f"{a['label']} is outside the plot")
            for b in rooms[i + 1:]:
                dx = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
                dy = min(a["y"] + a["depth"], b["y"] + b["depth"]) - max(a["y"], b["y"])
                if dx > TOL_FT and dy > TOL_FT:
                    problems.append(f"{a['label']} overlaps {b['label']}")
    checks.append(_check("geometry", not problems,
                         "No overlapping rooms; everything is inside the plot."
                         if not problems else "; ".join(problems[:4])))

    # 4. Every enclosed room is closed by walls on all four sides (except
    #    where it continues into another part of the same room).
    open_sides = []
    for items, storey in zip(floors_items, storeys):
        for it in items:
            if not enclosed(it):
                continue
            x, y, w, d = it["x"], it["y"], it["w"], it["d"]
            for horizontal, coord, a, b in ((True, y, x, x + w), (True, y + d, x, x + w),
                                            (False, x, y, y + d), (False, x + w, y, y + d)):
                same_group = sum(
                    max(0.0, min(b, (o["x"] + o["w"]) if horizontal else (o["y"] + o["d"]))
                        - max(a, o["x"] if horizontal else o["y"]))
                    for o in items if o is not it and it["group"] and o["group"] == it["group"]
                    and (abs(o["y"] + o["d"] - coord) < TOL_FT or abs(o["y"] - coord) < TOL_FT
                         if horizontal else abs(o["x"] + o["w"] - coord) < TOL_FT or abs(o["x"] - coord) < TOL_FT))
                if _covered(storey["walls"], horizontal, coord, a, b) + same_group < (b - a) - 0.05:
                    open_sides.append(it["name"])
                    break
    checks.append(_check("walls", not open_sides,
                         "Every enclosed room is surrounded by walls."
                         if not open_sides else "Not fully walled: " + ", ".join(sorted(set(open_sides))[:5])))

    # 5. Doors and windows.
    doors = sum(1 for s in storeys for w in s["walls"] for o in w["openings"] if o["type"] == "door")
    windows = sum(1 for s in storeys for w in s["walls"] for o in w["openings"] if o["type"] == "window")
    checks.append(_check("openings", skipped_openings == 0,
                         f"{doors} door(s) and {windows} window(s) placed in the plan's walls"
                         + (f"; {skipped_openings} could not be placed." if skipped_openings else "."),
                         blocking=False))

    return {"passed": all(c["ok"] for c in checks if c["blocking"]), "checks": checks}


def check_glb(model: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    """The exported GLB carries one pickable floor node per model room."""
    want = sum(len(s["rooms"]) for s in model["storeys"])
    got = metadata.get("rooms")
    return _check("glb", got == want, f"3D file contains {got} of {want} room(s).")
