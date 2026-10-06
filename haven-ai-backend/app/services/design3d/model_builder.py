"""
Turns the 2D plan produced by layout.py into structured 3D geometry.

The output is plain data (walls, slabs, openings, roof, stairs) that the React
viewer renders with Three.js. No image or mesh generation happens here and no
model is asked to invent geometry -- architecture.md 1.14 requires the 3D
rendering to stay isolated from backend logic, so the backend owns the
measurements and the browser owns the drawing.

All coordinates are in feet, relative to the building footprint's front-left
corner. `y` is depth (front to back); the viewer maps it to Three.js `z`.
"""
from typing import Dict, List, Tuple

# Architectural defaults live in arch_defaults.py; they are re-exported here
# because the other design3d stages import them from this module.
from .arch_defaults import (  # noqa: F401
    DOOR_HEIGHT_FT,
    DOOR_WIDTH_FT,
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
    WINDOW_WIDTH_FT,
)

# Edge keys are rounded so that two rooms sharing a partition produce the
# identical key and the shared wall is emitted once instead of twice.
_PRECISION = 2


def _room_edges(room: Dict) -> List[Tuple]:
    """Front, back, left and right edges of a room, in that order."""
    x, y = round(room["x"], _PRECISION), round(room["y"], _PRECISION)
    w, d = room["width"], room["depth"]
    x2, y2 = round(x + w, _PRECISION), round(y + d, _PRECISION)
    return [
        ("h", y, x, x2),    # front
        ("h", y2, x, x2),   # back
        ("v", x, y, y2),    # left
        ("v", x2, y, y2),   # right
    ]


def _edge_length(edge: Tuple) -> float:
    return round(edge[3] - edge[2], _PRECISION)


def _build_walls(rooms: List[Dict], width: float, depth: float) -> Tuple[List[Dict], Dict[Tuple, Dict]]:
    """De-duplicates room edges into wall segments.

    An edge shared by two rooms becomes a single interior partition. Edges
    belonging only to an unenclosed space (a car porch) are skipped entirely so
    parking reads as an open area rather than a sealed box.
    """
    owners: Dict[Tuple, List[Dict]] = {}
    for room in rooms:
        for edge in _room_edges(room):
            owners.setdefault(edge, []).append(room)

    walls: List[Dict] = []
    by_edge: Dict[Tuple, Dict] = {}

    for edge, edge_rooms in owners.items():
        orientation, coord, start, end = edge
        if orientation == "h":
            exterior = abs(coord) < 1e-6 or abs(coord - depth) < 1e-6
            x1, y1, x2, y2 = start, coord, end, coord
        else:
            exterior = abs(coord) < 1e-6 or abs(coord - width) < 1e-6
            x1, y1, x2, y2 = coord, start, coord, end

        if not any(r["enclosed"] for r in edge_rooms):
            # Interior edges of open space (corridor, terrace) carry no wall.
            # The building envelope still does, except across a car porch,
            # which has to stay open for a vehicle to drive in.
            if not exterior or any(r["type"] == "parking" for r in edge_rooms):
                continue

        # An exterior edge that only borders open space (a terrace) is a
        # railing-height parapet, not a full-height wall.
        parapet = not any(r["enclosed"] for r in edge_rooms)

        wall = {
            "id": f"w{len(walls) + 1}",
            "x1": x1, "y1": y1, "x2": x2, "y2": y2,
            "length": _edge_length(edge),
            "thickness": EXT_WALL_THICKNESS_FT if exterior else INT_WALL_THICKNESS_FT,
            "height": PARAPET_HEIGHT_FT if parapet else WALL_HEIGHT_FT,
            "exterior": exterior,
            "parapet": parapet,
            "openings": [],
        }
        walls.append(wall)
        by_edge[edge] = wall

    return walls, by_edge


def _add_opening(wall: Dict, kind: str) -> bool:
    """Adds a centred door or window. One opening per wall segment keeps the
    generated geometry unambiguous for the renderer."""
    if wall["openings"] or wall.get("parapet"):
        return False
    if kind == "door":
        if wall["length"] < DOOR_WIDTH_FT + 1.5:
            return False
        wall["openings"].append({
            "type": "door", "center": round(wall["length"] / 2, 2),
            "width": DOOR_WIDTH_FT, "height": DOOR_HEIGHT_FT, "sill": 0.0,
        })
        return True
    if wall["length"] < WINDOW_WIDTH_FT + 2.0:
        return False
    wall["openings"].append({
        "type": "window", "center": round(wall["length"] / 2, 2),
        "width": WINDOW_WIDTH_FT, "height": WINDOW_HEIGHT_FT, "sill": WINDOW_SILL_FT,
    })
    return True


def _place_openings(rooms: List[Dict], by_edge: Dict[Tuple, Dict], level: int) -> None:
    if level == 1:
        # Main entrance on the longest front-facing exterior wall, claimed
        # before room doors so the house always has a way in (unless the front
        # is an open car porch, in which case entry is through the porch).
        front = [w for w in by_edge.values()
                 if w["exterior"] and abs(w["y1"]) < 1e-6 and abs(w["y2"]) < 1e-6]
        if front:
            _add_opening(max(front, key=lambda w: w["length"]), "door")

    for room in rooms:
        if not room["enclosed"]:
            continue
        edges = _room_edges(room)

        # A door onto an interior partition is preferred: it opens into the
        # house rather than straight outside.
        interior = [by_edge[e] for e in edges if e in by_edge and not by_edge[e]["exterior"]]
        exterior = [by_edge[e] for e in edges if e in by_edge and by_edge[e]["exterior"]]
        if not any(_add_opening(w, "door") for w in interior):
            for wall in exterior:
                if _add_opening(wall, "door"):
                    break

        for wall in exterior:
            if _add_opening(wall, "window"):
                break


def _merge_collinear(walls: List[Dict]) -> List[Dict]:
    """Rooms of different widths can share part of a wall line (e.g. a 12.5 ft
    room behind an 11.2 ft one). Their edges are different keys, so both walls
    are emitted and overlap, and the solid one hides the other's door. This
    merges overlapping collinear walls into one, keeping every opening that
    does not clash with an earlier one."""
    lines: Dict[Tuple, List[Dict]] = {}
    for w in walls:
        horiz = abs(w["y1"] - w["y2"]) < 1e-6
        coord = round(w["y1"] if horiz else w["x1"], _PRECISION)
        lines.setdefault((horiz, coord), []).append(w)

    out: List[Dict] = []
    for (horiz, coord), group in lines.items():
        start = lambda w: min(w["x1"], w["x2"]) if horiz else min(w["y1"], w["y2"])  # noqa: E731
        group.sort(key=start)
        merged: List[Tuple[float, float, List[Dict]]] = []
        for w in group:
            s = start(w)
            if merged and s < merged[-1][1] - 1e-6:
                merged[-1] = (merged[-1][0], max(merged[-1][1], s + w["length"]), merged[-1][2] + [w])
            else:
                merged.append((s, s + w["length"], [w]))
        for s, e, parts in merged:
            if len(parts) == 1:
                out.append(parts[0])
                continue
            solid = [p for p in parts if not p.get("parapet")]
            base = dict(solid[0] if solid else parts[0])
            openings: List[Dict] = []
            for p in parts:
                for op in p["openings"]:
                    center = start(p) + op["center"] - s
                    lo, hi = center - op["width"] / 2, center + op["width"] / 2
                    if any(lo < o["center"] + o["width"] / 2 and hi > o["center"] - o["width"] / 2 for o in openings):
                        continue
                    openings.append({**op, "center": round(center, 2)})
            openings.sort(key=lambda o: o["center"])
            base.update({
                "x1": s if horiz else coord, "y1": coord if horiz else s,
                "x2": e if horiz else coord, "y2": coord if horiz else e,
                "length": round(e - s, _PRECISION),
                "thickness": max(p["thickness"] for p in parts),
                "height": max(p["height"] for p in parts),
                "exterior": any(p["exterior"] for p in parts),
                "parapet": not solid,
                "openings": openings,
            })
            out.append(base)
    return out


def _build_stairs(rooms: List[Dict], elevation: float) -> Dict:
    stair_room = next((r for r in rooms if r["type"] == "stairs"), None)
    if not stair_room:
        return None
    return {
        "x": stair_room["x"],
        "y": stair_room["y"],
        "width": stair_room["width"],
        "depth": stair_room["depth"],
        "base_elevation": elevation,
        "total_rise": STOREY_PITCH_FT,
        "steps": STAIR_STEPS,
    }


def build_model(floors: List[List[Dict]], footprint: Dict[str, float],
                plot: Dict[str, float]) -> Dict:
    """Assembles the complete 3D model description."""
    width, depth = footprint["width_ft"], footprint["depth_ft"]
    storeys = []

    for index, rooms in enumerate(floors):
        level = index + 1
        elevation = round(index * STOREY_PITCH_FT, 2)
        walls, by_edge = _build_walls(rooms, width, depth)
        _place_openings(rooms, by_edge, level)
        walls = _merge_collinear(walls)

        storeys.append({
            "level": level,
            "label": STOREY_LABELS.get(level, f"Floor {level}"),
            "elevation_ft": elevation,
            "wall_height_ft": WALL_HEIGHT_FT,
            "slab": {
                "x": 0.0, "y": 0.0, "width": width, "depth": depth,
                "thickness": SLAB_THICKNESS_FT, "elevation": elevation,
            },
            "rooms": rooms,
            "walls": walls,
            "covered_area_sqft": round(sum(r["width"] * r["depth"] for r in rooms), 1),
            "stairs": _build_stairs(rooms, elevation) if level < len(floors) else None,
        })

    roof_elevation = round(len(floors) * STOREY_PITCH_FT, 2)

    # A terrace on the top storey must stay open to the sky, so the roof slab
    # stops where that band begins (terraces are always a full-width rear band).
    top_rooms = floors[-1] if floors else []
    terraces = [r for r in top_rooms if r["type"] == "terrace"]
    roof_depth = round(min(r["y"] for r in terraces), 2) if terraces else depth

    model = {
        "plot": {"width_ft": plot["width_ft"], "length_ft": plot["length_ft"]},
        "footprint": footprint,
        "storeys": storeys,
        "roof": {
            "type": "flat",
            "x": 0.0, "y": 0.0, "width": width, "depth": roof_depth,
            "thickness": SLAB_THICKNESS_FT,
            "elevation": roof_elevation,
            "parapet_height": PARAPET_HEIGHT_FT,
            "parapet_thickness": EXT_WALL_THICKNESS_FT,
        },
        "totals": {
            "storeys": len(storeys),
            "covered_area_sqft": round(sum(s["covered_area_sqft"] for s in storeys), 1),
            "building_height_ft": round(roof_elevation + PARAPET_HEIGHT_FT, 2),
            "plot_area_sqft": round(plot["width_ft"] * plot["length_ft"], 1),
        },
    }
    return model
