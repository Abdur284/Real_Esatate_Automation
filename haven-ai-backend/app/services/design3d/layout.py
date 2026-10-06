"""
Deterministic space planning for the 3D Design module.

Produces the 2D footprint of every room (the plan) which model_builder.py then
extrudes into 3D. No AI involvement: feasibility here is an exact geometric
result, not an estimate, because the packer itself decides what fits.

Rooms are packed into full-width bands which are then stretched to tile the
buildable rectangle exactly. Because neighbouring rooms therefore share exact
edges, partition walls stay collinear -- which is both how a plan is really
drawn and what makes wall de-duplication in model_builder exact.
"""
from typing import Any, Dict, List, Tuple

from .requirements import ROOM_LABELS, ROOM_SPECS

MAX_STOREYS = 2  # hard rule for this module: never model a third storey

# Generic, conservative setback assumptions for a residential plot in Pakistan.
# These are planning conventions, NOT any specific society's official bylaws --
# surfaced to the user as assumptions rather than presented as regulations.
FRONT_SETBACK_FT = 5.0
REAR_SETBACK_FT = 3.0
SIDE_SETBACK_FT_NARROW = 0.0   # party-wall row plots (< 30 ft wide)
SIDE_SETBACK_FT_WIDE = 3.0     # wider plots conventionally keep a side gap
WIDE_PLOT_THRESHOLD_FT = 30.0

PLOT_MIN_DIM_FT = 12.0
PLOT_MAX_DIM_FT = 400.0

# Shared/service spaces belong downstairs; bedrooms and their bathrooms move
# upstairs in a two-storey design, which is the conventional arrangement.
GROUND_FLOOR_TYPES = ("parking", "drawing_room", "kitchen", "tv_lounge", "store_room")
PRIVATE_TYPES = ("bedroom", "bathroom")

# Rooms are stretched to tile the plan exactly, but only within reason: without
# a cap a lone room in the last band becomes an absurd 25 ft wide bathroom.
# Anything left over becomes real circulation/open space instead.
MAX_WIDTH_STRETCH = 1.4
MAX_DEPTH_STRETCH = 1.25
MIN_CORRIDOR_WIDTH_FT = 3.5
MIN_TERRACE_DEPTH_FT = 5.0
# The building need not consume the whole buildable depth -- the remainder is
# simply back garden, which is how a real plot is used.
DEPTH_SLACK = 1.15


class RoomSpec:
    __slots__ = ("room_type", "label", "width", "depth")

    def __init__(self, room_type: str, label: str, width: float, depth: float):
        self.room_type = room_type
        self.label = label
        self.width = width
        self.depth = depth


def validate_plot(width_ft, length_ft) -> str:
    if width_ft is None or length_ft is None:
        return "MISSING_DIMENSIONS"
    if width_ft <= 0 or length_ft <= 0:
        return "INVALID_DIMENSIONS"
    if width_ft < PLOT_MIN_DIM_FT or length_ft < PLOT_MIN_DIM_FT:
        return "INVALID_DIMENSIONS"
    if width_ft > PLOT_MAX_DIM_FT or length_ft > PLOT_MAX_DIM_FT:
        return "INVALID_DIMENSIONS"
    return ""


def compute_footprint(plot_width: float, plot_length: float) -> Dict[str, float]:
    side = SIDE_SETBACK_FT_WIDE if plot_width >= WIDE_PLOT_THRESHOLD_FT else SIDE_SETBACK_FT_NARROW
    return {
        "origin_x_ft": side,
        "origin_y_ft": FRONT_SETBACK_FT,
        "width_ft": round(plot_width - 2 * side, 2),
        "depth_ft": round(plot_length - FRONT_SETBACK_FT - REAR_SETBACK_FT, 2),
        "side_setback_ft": side,
        "front_setback_ft": FRONT_SETBACK_FT,
        "rear_setback_ft": REAR_SETBACK_FT,
    }


def _spec(room_type: str, label: str = None) -> RoomSpec:
    w, d = ROOM_SPECS[room_type]
    return RoomSpec(room_type, label or ROOM_LABELS[room_type], w, d)


def build_room_specs(reqs: Dict[str, Any]) -> List[RoomSpec]:
    specs: List[RoomSpec] = []
    if reqs.get("parking"):
        specs.append(_spec("parking"))
    if reqs.get("drawing_room"):
        specs.append(_spec("drawing_room"))
    for i in range(reqs.get("kitchens", 0)):
        specs.append(_spec("kitchen", "Kitchen" if i == 0 else f"Kitchen {i + 1}"))
    if reqs.get("tv_lounge"):
        specs.append(_spec("tv_lounge"))
    if reqs.get("store_room"):
        specs.append(_spec("store_room"))
    for i in range(reqs.get("bathrooms", 0)):
        specs.append(_spec("bathroom", f"Bathroom {i + 1}"))
    for i in range(reqs.get("bedrooms", 0)):
        specs.append(_spec("bedroom", f"Bedroom {i + 1}"))
    return specs


def _pack_rows(specs: List[RoomSpec], width: float, depth: float
               ) -> Tuple[List[List[RoomSpec]], List[RoomSpec]]:
    """Greedy band packing. Rooms are grouped by similar depth so a band is not
    forced to the depth of one deep outlier, which is what wastes space.

    A stairwell is kept first so it lands in the same corner on every storey.
    Returns (rows_that_fit, leftover_specs)."""
    stairs = [s for s in specs if s.room_type == "stairs"]
    others = sorted((s for s in specs if s.room_type != "stairs"),
                    key=lambda s: (-s.depth, s.room_type))
    ordered = stairs + others

    leftover: List[RoomSpec] = []
    rows: List[List[RoomSpec]] = []
    current: List[RoomSpec] = []
    current_w = 0.0

    for spec in ordered:
        if spec.width > width + 1e-6:
            leftover.append(spec)  # can never fit this footprint's width
            continue
        if current and current_w + spec.width > width + 1e-6:
            rows.append(current)
            current, current_w = [spec], spec.width
        else:
            current.append(spec)
            current_w += spec.width
    if current:
        rows.append(current)

    fitting: List[List[RoomSpec]] = []
    used = 0.0
    for index, row in enumerate(rows):
        row_depth = max(s.depth for s in row)
        if used + row_depth > depth + 1e-6:
            for remaining in rows[index:]:
                leftover.extend(remaining)
            break
        fitting.append(row)
        used += row_depth

    return fitting, leftover


def natural_depth(rows: List[List[RoomSpec]]) -> float:
    """Depth the bands need at their minimum sizes."""
    return sum(max(s.depth for s in row) for row in rows)


def _filler(level: int, index: int, room_type: str, label: str,
            x: float, y: float, width: float, depth: float,
            enclosed: bool = False) -> Dict:
    return {
        "id": f"r{level}_{index}",
        "type": room_type,
        "label": label,
        "x": round(x, 2), "y": round(y, 2),
        "width": round(width, 2), "depth": round(depth, 2),
        "enclosed": enclosed,
    }


def _materialize(rows: List[List[RoomSpec]], width: float, depth: float,
                 level: int, is_top: bool) -> List[Dict]:
    """Turns packed bands into positioned rooms tiling the building rectangle.

    Rooms stretch only up to a cap; leftover width becomes a corridor and
    leftover depth on the top storey becomes a terrace, so the plan stays
    gap-free without inflating rooms to unrealistic sizes.
    """
    if not rows:
        return []

    min_total = natural_depth(rows)
    depth_scale = min(depth / min_total, MAX_DEPTH_STRETCH) if min_total > 0 else 1.0

    placed: List[Dict] = []
    y = 0.0
    for row_index, row in enumerate(rows):
        row_depth = round(max(s.depth for s in row) * depth_scale, 2)
        remaining_rows = len(rows) - row_index - 1
        if remaining_rows == 0 and depth - y - row_depth < MIN_TERRACE_DEPTH_FT:
            row_depth = round(depth - y, 2)  # absorb a small remainder

        total_w = sum(s.width for s in row)
        width_scale = min(width / total_w, MAX_WIDTH_STRETCH) if total_w > 0 else 1.0
        stretched = [round(s.width * width_scale, 2) for s in row]
        slack = round(width - sum(stretched), 2)
        if 0 < slack < MIN_CORRIDOR_WIDTH_FT and stretched:
            stretched[-1] = round(stretched[-1] + slack, 2)
            slack = 0.0

        x = 0.0
        for position, spec in enumerate(row):
            w = stretched[position]
            if position == len(row) - 1 and slack <= 0:
                w = round(width - x, 2)
            placed.append({
                "id": f"r{level}_{len(placed) + 1}",
                "type": spec.room_type,
                "label": spec.label,
                "x": round(x, 2), "y": round(y, 2),
                "width": round(w, 2), "depth": round(row_depth, 2),
                "enclosed": spec.room_type != "parking",
            })
            x += w

        if slack >= MIN_CORRIDOR_WIDTH_FT:
            leftover_w = width - x
            big = leftover_w * row_depth > 120
            placed.append(_filler(level, len(placed) + 1, "corridor",
                                  "Open Hall" if big else "Corridor",
                                  x, y, leftover_w, row_depth))
        y += row_depth

    leftover = round(depth - y, 2)
    if leftover >= MIN_TERRACE_DEPTH_FT:
        if is_top:
            # Open to the sky, so it keeps only a parapet and no roof above it.
            placed.append(_filler(level, len(placed) + 1, "terrace", "Terrace",
                                  0.0, y, width, leftover))
        else:
            # There is a floor slab directly above, so this has to be enclosed
            # living space rather than an open court.
            placed.append(_filler(level, len(placed) + 1, "family_hall", "Family Hall",
                                  0.0, y, width, leftover, enclosed=True))
    elif leftover > 0 and placed:
        for room in placed:  # nudge the last band to close a sub-threshold gap
            if abs(room["y"] + room["depth"] - y) < 1e-6:
                room["depth"] = round(room["depth"] + leftover, 2)

    return placed


def _allocate(specs: List[RoomSpec], storey_count: int) -> List[List[RoomSpec]]:
    """Splits rooms across storeys by purpose rather than by whatever happens
    to fit first, so a two-storey house gets shared space downstairs and
    bedrooms upstairs instead of an arbitrary split.

    Only the shared spaces plus one bathroom are claimed downstairs: bedrooms
    are left upstairs and pulled back down by the overflow pass in
    plan_storeys only if the upper floor genuinely runs out of room. That
    ordering is what keeps the kitchen and lounge on the ground floor.
    """
    if storey_count == 1:
        return [list(specs)]

    ground = [s for s in specs if s.room_type in GROUND_FLOOR_TYPES]
    bedrooms = [s for s in specs if s.room_type == "bedroom"]
    bathrooms = [s for s in specs if s.room_type == "bathroom"]

    # A ground-floor WC is standard whenever more than one bathroom is asked for.
    if len(bathrooms) >= 2:
        ground.append(bathrooms.pop(0))

    upper = bedrooms + bathrooms
    if not upper:  # nothing private left to justify an upper floor
        upper = [ground.pop()] if len(ground) > 1 else []
    return [ground, upper]


def plan_storeys(reqs: Dict[str, Any], footprint: Dict[str, float]) -> Dict[str, Any]:
    """Allocates rooms across at most two storeys and reports exact feasibility."""
    width, depth = footprint["width_ft"], footprint["depth_ft"]
    if width <= 0 or depth <= 0:
        return {
            "status": "NOT_FEASIBLE",
            "message": (
                f"After the assumed setbacks (front {FRONT_SETBACK_FT}ft, rear {REAR_SETBACK_FT}ft, "
                f"side {footprint['side_setback_ft']}ft each), no buildable area remains on this plot."
            ),
            "suggestion": "Use a larger plot, or confirm the setbacks that actually apply to it.",
        }

    specs = build_room_specs(reqs)
    if not specs:
        return {
            "status": "NO_ROOMS",
            "message": "No rooms were requested. Mention what you need, for example "
                       "\"3 bedrooms, 2 bathrooms, a kitchen and a TV lounge\".",
            "suggestion": None,
        }

    requested = reqs.get("storeys_requested")
    wants_stairs = bool(reqs.get("stairs_mentioned"))

    def attempt(storey_count: int):
        """Returns (floors_of_rooms, leftover_specs) for a given storey count."""
        allocation = _allocate(specs, storey_count)
        needs_stairs = storey_count > 1 or wants_stairs

        rows_per_floor: List[List[List[RoomSpec]]] = []
        overflow: List[RoomSpec] = []

        for level in range(storey_count):
            level_specs = list(allocation[level]) + overflow
            overflow = []
            if needs_stairs:
                level_specs = [_spec("stairs")] + level_specs
            rows, leftover = _pack_rows(level_specs, width, depth)
            rows_per_floor.append(rows)
            overflow = [s for s in leftover if s.room_type != "stairs"]

        # Anything still homeless gets one more attempt on an earlier floor
        # that may still have spare depth.
        if overflow:
            for level in range(storey_count):
                retry_specs = [s for row in rows_per_floor[level] for s in row] + overflow
                rows, leftover = _pack_rows(retry_specs, width, depth)
                remaining = [s for s in leftover if s.room_type != "stairs"]
                if len(remaining) < len(overflow):
                    rows_per_floor[level] = rows
                    overflow = remaining
                if not overflow:
                    break

        return rows_per_floor, overflow

    max_allowed = min(requested, MAX_STOREYS) if requested else MAX_STOREYS
    rows_per_floor, leftover = attempt(max_allowed)

    if leftover:
        names = ", ".join(sorted({s.label for s in leftover}))
        if requested == 1:
            _, two_leftover = attempt(2)
            if not two_leftover:
                return {
                    "status": "NOT_FEASIBLE",
                    "message": (
                        f"On a single storey these do not fit inside the "
                        f"{width:g}x{depth:g} ft buildable area: {names}."
                    ),
                    "suggestion": "A double-storey design fits everything you asked for.",
                }
        return {
            "status": "NOT_FEASIBLE",
            "message": (
                f"Even across {max_allowed} storey(s) these do not fit inside the "
                f"{width:g}x{depth:g} ft buildable area: {names}."
            ),
            "suggestion": "Reduce the number of rooms or use a larger plot "
                          f"(this module models a maximum of {MAX_STOREYS} storeys).",
        }

    # Drop a trailing storey holding nothing but its stairwell.
    while len(rows_per_floor) > 1 and (
        not rows_per_floor[-1]
        or all(s.room_type == "stairs" for row in rows_per_floor[-1] for s in row)
    ):
        rows_per_floor.pop()

    # The building only takes the depth its rooms need (plus a little slack);
    # whatever is left of the buildable area stays open as back garden.
    needed = max((natural_depth(rows) for rows in rows_per_floor if rows), default=0.0)
    building_depth = round(min(needed * DEPTH_SLACK, depth), 2)

    floors = [
        _materialize(rows, width, building_depth, level + 1,
                     is_top=(level == len(rows_per_floor) - 1))
        for level, rows in enumerate(rows_per_floor)
    ]

    return {
        "status": "FEASIBLE",
        "floors": floors,
        "building": {"width_ft": width, "depth_ft": building_depth},
    }
