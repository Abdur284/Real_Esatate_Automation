"""
Indicative furniture for the 3D model (a visual aid, never architecture).

Pieces are placed deterministically from each room's type and rectangle:
against a side that is fully walled and has no door or window, clear of every
door's swing zone, and only when the room is big enough to keep a walkway.
A room that cannot fit a piece simply gets none. Everything is returned in
plan feet (x, y = depth, h = height above ground) as axis-aligned boxes; the
GLB exporter converts them. Furniture is flagged as indicative in the model
metadata and can be hidden in the viewer.
"""
from typing import Dict, List, Tuple

INSET_FT = 0.45          # half a wall plus a little air
WALKWAY_FT = 2.5         # free floor kept in front of a piece
DOOR_CLEARANCE_FT = 0.5  # extra space either side of / beyond a door leaf

Box = Tuple[float, float, float, float, float, float]  # x0, y0, h0, x1, y1, h1

BEDROOMS = {"bedroom", "master_bedroom", "guest_room", "servant_room"}
LOUNGES = {"tv_lounge", "living_room", "family_hall", "drawing_room"}


def _overlap_1d(a0, a1, b0, b1) -> float:
    return min(a1, b1) - max(a0, b0)


def _side_info(room: Dict, walls: List[Dict]) -> Dict[str, Dict]:
    """For each side of the room: its span, how much of it carries a wall, and
    the openings on it (absolute intervals along the side)."""
    x, y, w, d = room["x"], room["y"], room["width"], room["depth"]
    sides = {
        "south": ("h", y, x, x + w), "north": ("h", y + d, x, x + w),
        "west": ("v", x, y, y + d), "east": ("v", x + w, y, y + d),
    }
    out = {}
    for name, (orient, coord, s0, s1) in sides.items():
        covered, openings = 0.0, []
        for wall in walls:
            horiz = abs(wall["y1"] - wall["y2"]) < 1e-6
            if horiz != (orient == "h") or wall.get("parapet"):
                continue
            if abs((wall["y1"] if horiz else wall["x1"]) - coord) > 0.05:
                continue
            ws = min(wall["x1"], wall["x2"]) if horiz else min(wall["y1"], wall["y2"])
            ov = _overlap_1d(ws, ws + wall["length"], s0, s1)
            if ov <= 0:
                continue
            covered += ov
            for op in wall["openings"]:
                a, b = ws + op["center"] - op["width"] / 2, ws + op["center"] + op["width"] / 2
                if _overlap_1d(a, b, s0, s1) > 0:
                    openings.append((op["type"], a, b))
        out[name] = {"orient": orient, "coord": coord, "span": (s0, s1),
                     "walled": covered >= (s1 - s0) - 0.1, "openings": openings}
    return out


def _door_zones(room: Dict, sides: Dict[str, Dict]) -> List[Tuple[float, float, float, float]]:
    """Floor rectangles (x0, y0, x1, y1) inside the room that a door swings over."""
    zones = []
    x, y, w, d = room["x"], room["y"], room["width"], room["depth"]
    for name, info in sides.items():
        for kind, a, b in info["openings"]:
            if kind != "door":
                continue
            reach = (b - a) + DOOR_CLEARANCE_FT
            a, b = a - DOOR_CLEARANCE_FT, b + DOOR_CLEARANCE_FT
            if name == "south":
                zones.append((a, y, b, y + reach))
            elif name == "north":
                zones.append((a, y + d - reach, b, y + d))
            elif name == "west":
                zones.append((x, a, x + reach, b))
            else:
                zones.append((x + w - reach, a, x + w, b))
    return zones


class _Room:
    """Placement helper working in the room's local frame for one chosen side:
    `along` runs along the side, `out` runs from the side into the room."""

    def __init__(self, room: Dict, side: str, elevation: float):
        self.r, self.side, self.el = room, side, elevation
        horiz = side in ("south", "north")
        self.along_len = (room["width"] if horiz else room["depth"]) - 2 * INSET_FT
        self.out_len = (room["depth"] if horiz else room["width"]) - 2 * INSET_FT

    def box(self, a0: float, a1: float, o0: float, o1: float, h0: float, h1: float) -> Box:
        """a/o measured from the side's inner corner; h above the floor."""
        r = self.r
        x0, y0 = r["x"] + INSET_FT, r["y"] + INSET_FT
        x1, y1 = r["x"] + r["width"] - INSET_FT, r["y"] + r["depth"] - INSET_FT
        if self.side == "south":
            bx = (x0 + a0, y0 + o0, x0 + a1, y0 + o1)
        elif self.side == "north":
            bx = (x0 + a0, y1 - o1, x0 + a1, y1 - o0)
        elif self.side == "west":
            bx = (x0 + o0, y0 + a0, x0 + o1, y0 + a1)
        else:
            bx = (x1 - o1, y0 + a0, x1 - o0, y0 + a1)
        return (bx[0], bx[1], self.el + h0, bx[2], bx[3], self.el + h1)


def _clear(boxes: List[Tuple[str, str, Box]], zones) -> bool:
    for _, _, b in boxes:
        for z in zones:
            if _overlap_1d(b[0], b[3], z[0], z[2]) > 0.01 and _overlap_1d(b[1], b[4], z[1], z[3]) > 0.01:
                return False
    return True


def _candidate_sides(sides: Dict[str, Dict]) -> List[str]:
    """Fully walled sides without openings, longest first."""
    good = [n for n, s in sides.items() if s["walled"] and not s["openings"]]
    return sorted(good, key=lambda n: -(sides[n]["span"][1] - sides[n]["span"][0]))


def _bedroom(R: _Room) -> List[Tuple[str, str, Box]]:
    bed_w = 5.0 if R.along_len >= 8.5 else 3.5
    bed_l = 6.5
    if R.along_len < bed_w + 0.5 or R.out_len < bed_l + WALKWAY_FT:
        return []
    c = R.along_len / 2
    a0, a1 = c - bed_w / 2, c + bed_w / 2
    items = [
        ("bed_headboard", "wood", R.box(a0, a1, 0, 0.3, 0, 3.4)),
        ("bed_base", "fabric", R.box(a0, a1, 0.3, bed_l, 0, 1.7)),
        ("bed_blanket", "accent", R.box(a0 + 0.05, a1 - 0.05, 2.6, bed_l + 0.05, 1.7, 1.85)),
    ]
    pillows = [(a0 + 0.3, a1 - 0.3)] if bed_w < 4 else [(a0 + 0.3, c - 0.15), (c + 0.15, a1 - 0.3)]
    items += [("bed_pillow", "fabric", R.box(p0, p1, 0.5, 1.6, 1.7, 2.05)) for p0, p1 in pillows]
    if a0 >= 1.8 and R.along_len - a1 >= 1.8:
        items.append(("nightstand", "wood", R.box(a0 - 1.7, a0 - 0.2, 0, 1.5, 0, 1.8)))
        items.append(("nightstand", "wood", R.box(a1 + 0.2, a1 + 1.7, 0, 1.5, 0, 1.8)))
    return items


def _lounge(R: _Room) -> List[Tuple[str, str, Box]]:
    sofa_w = 7.0 if R.along_len >= 9 else 5.0
    if R.along_len < sofa_w + 0.5 or R.out_len < 3 + 1.5 + 2 + WALKWAY_FT:
        return []
    c = R.along_len / 2
    a0, a1 = c - sofa_w / 2, c + sofa_w / 2
    return [
        ("sofa_seat", "upholstery", R.box(a0, a1, 0, 3, 0, 1.4)),
        ("sofa_back", "upholstery", R.box(a0, a1, 0, 0.8, 1.4, 2.8)),
        ("sofa_arm", "upholstery", R.box(a0, a0 + 0.6, 0.8, 3, 1.4, 2.1)),
        ("sofa_arm", "upholstery", R.box(a1 - 0.6, a1, 0.8, 3, 1.4, 2.1)),
        ("coffee_table", "wood", R.box(c - 1.75, c + 1.75, 4.5, 6.5, 0, 1.4)),
    ]


def _dining(R: _Room) -> List[Tuple[str, str, Box]]:
    tl, tw = 6.0, 3.5
    if R.along_len < tl + 2 * WALKWAY_FT or R.out_len < tw + 2 * WALKWAY_FT:
        return []
    c, m = R.along_len / 2, R.out_len / 2
    items = [("dining_table", "wood", R.box(c - tl / 2, c + tl / 2, m - tw / 2, m + tw / 2, 0, 2.5))]
    for off in (-1.8, 0, 1.8):
        items.append(("chair", "wood", R.box(c + off - 0.75, c + off + 0.75, m - tw / 2 - 1.7, m - tw / 2 - 0.2, 0, 1.5)))
        items.append(("chair", "wood", R.box(c + off - 0.75, c + off + 0.75, m + tw / 2 + 0.2, m + tw / 2 + 1.7, 0, 1.5)))
    return items


def _kitchen(R: _Room) -> List[Tuple[str, str, Box]]:
    if R.along_len < 4 or R.out_len < 2 + WALKWAY_FT:
        return []
    return [
        ("counter", "cabinet", R.box(0, R.along_len, 0, 2, 0, 2.9)),
        ("counter_top", "stone", R.box(0, R.along_len, 0, 2.1, 2.9, 3.05)),
    ]


def _bathroom(R: _Room) -> List[Tuple[str, str, Box]]:
    if R.along_len < 2 or R.out_len < 2.3 + 1.5:
        return []
    items = [("wc", "sanitary", R.box(0.2, 1.7, 0, 2.3, 0, 1.3)),
             ("wc_tank", "sanitary", R.box(0.2, 1.7, 0, 0.6, 1.3, 2.6))]
    if R.along_len >= 4.6:
        items.append(("basin", "sanitary", R.box(R.along_len - 2.1, R.along_len - 0.1, 0, 1.5, 0, 2.8)))
    return items


def _study(R: _Room) -> List[Tuple[str, str, Box]]:
    if R.along_len < 4.5 or R.out_len < 2 + WALKWAY_FT:
        return []
    c = R.along_len / 2
    return [("desk", "wood", R.box(c - 2, c + 2, 0, 2, 0, 2.5))]


PLANNERS = {
    **{t: _bedroom for t in BEDROOMS},
    **{t: _lounge for t in LOUNGES},
    "dining_room": _dining,
    "kitchen": _kitchen,
    "bathroom": _bathroom,
    "study": _study,
}


def furnish_room(room: Dict, walls: List[Dict], elevation: float) -> List[Tuple[str, str, Box]]:
    """Returns [(piece_name, material_key, box)] for one room (possibly empty)."""
    plan = PLANNERS.get(room.get("type"))
    if plan is None or not room.get("enclosed", True):
        return []
    sides = _side_info(room, walls)
    zones = _door_zones(room, sides)
    for side in _candidate_sides(sides):
        items = plan(_Room(room, side, elevation))
        if items and _clear(items, zones):
            return items
    return []


def furnish_storey(storey: Dict, origin: Tuple[float, float] = (0.0, 0.0)) -> List[Tuple[str, str, Box]]:
    """Furniture for every room of one storey, in plot coordinates."""
    ox, oy = origin
    out: List[Tuple[str, str, Box]] = []
    for room in storey.get("rooms") or []:
        if room.get("group"):
            continue  # multi-part rooms are left empty rather than guessed at
        for name, mat, b in furnish_room(room, storey.get("walls") or [], storey["elevation_ft"]):
            out.append((name, mat, (b[0] + ox, b[1] + oy, b[2], b[3] + ox, b[4] + oy, b[5])))
    return out


def furnish_model(model: Dict) -> Dict[int, List[Tuple[str, str, Box]]]:
    origin = (model["footprint"].get("origin_x_ft", 0.0), model["footprint"].get("origin_y_ft", 0.0))
    return {s["level"]: furnish_storey(s, origin) for s in model.get("storeys") or []}
