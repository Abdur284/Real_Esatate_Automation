"""
Parametric 3D models for furniture the user adds or swaps in.

A model is a list of simple solids (boxes, vertical and horizontal
cylinders/frusta, leafy clusters) in metres, built by a *generator* from the
piece's width/depth/height and a few style parameters. The object library
(library.py, library_data/*.json) describes each catalogue item as
generator + parameters + real dimensions, so one generator serves many
distinct pieces: a sofa generator makes 2-/3-/4-seaters, L- and U-shapes,
recliners, with track/rolled/slim arms, tapered/metal/hidden legs, etc.

Local axes: x to the right, y up from the item's base, z away from the camera
(the front of the piece is at -depth/2). Every solid has a role that decides
its material in the renderer: "main" takes the user's colour/material,
"cushion" is the same fabric slightly lighter, "leg" follows the legs
parameter, the rest are fixed accents (glass, metal, shade, bulb, pot...).

Flat wall items (art, mirrors, clocks, curtains, blinds, wall lights) are
drawn in 2D by wall2d.py instead; their generators are listed in
WALL_GENERATORS.
"""
import math
from typing import Dict, List, Optional, Tuple

Part = Dict

# Legacy scene types (added before the library existed) -> (W, D, H) in metres.
BASE_DIMS: Dict[str, Tuple[float, float, float]] = {
    "sofa": (2.0, 0.9, 0.85), "sectional_sofa": (2.8, 1.6, 0.85), "armchair": (0.85, 0.85, 0.85),
    "chair": (0.48, 0.52, 0.9), "ottoman": (0.7, 0.7, 0.42), "bench": (1.3, 0.4, 0.46),
    "bed": (1.7, 2.1, 1.0), "coffee_table": (1.1, 0.6, 0.42), "table": (1.4, 0.8, 0.75),
    "dining_table": (1.6, 0.9, 0.75), "side_table": (0.5, 0.5, 0.55), "desk": (1.3, 0.65, 0.75),
    "cabinet": (1.2, 0.45, 0.85), "sideboard": (1.6, 0.45, 0.8), "wardrobe": (1.5, 0.6, 2.1),
    "chest_of_drawers": (1.0, 0.5, 1.0), "bookshelf": (1.0, 0.35, 1.9), "tv_unit": (1.8, 0.45, 0.5),
    "tv": (1.2, 0.25, 1.15), "floor_lamp": (0.4, 0.4, 1.6), "plant": (0.55, 0.55, 1.2),
    "rug": (2.0, 1.4, 0.012), "painting": (0.8, 0.03, 0.6), "mirror": (0.6, 0.03, 1.0),
}

WALL_GENERATORS = {"painting", "wall_art", "mirror", "clock", "curtains", "blinds", "wall_light"}
# Kept for older imports: types whose models are flat wall panels.
WALL_MODELS = WALL_GENERATORS


# ---- solids ------------------------------------------------------------------

def box(x0, x1, y0, y1, z0, z1, role="main") -> Part:
    return {"shape": "box", "x": (min(x0, x1), max(x0, x1)), "y": (min(y0, y1), max(y0, y1)),
            "z": (min(z0, z1), max(z0, z1)), "role": role}


def prism(cx, cz, r, y0, y1, role="main", n=12, r_top=None, sx=1.0) -> Part:
    """Vertical cylinder / frustum; `sx` stretches it along x (ovals)."""
    return {"shape": "prism", "c": (cx, cz), "r": r, "r_top": r if r_top is None else r_top,
            "y": (y0, y1), "n": n, "role": role, "sx": sx}


def cyl_x(cy, cz, r, x0, x1, role="main", n=10) -> Part:
    """Horizontal cylinder along x (bolsters, rolled arms, rails)."""
    return {"shape": "cylx", "c": (cy, cz), "r": r, "x": (x0, x1), "n": n, "role": role}


def cyl_z(cx, cy, r, z0, z1, role="main", n=10) -> Part:
    """Horizontal cylinder along z (rolled arm running front to back)."""
    return {"shape": "cylz", "c": (cx, cy), "r": r, "z": (z0, z1), "n": n, "role": role}


def sphere(cx, cy, cz, r, role="main", n=12, rings=5) -> List[Part]:
    """A ball made of stacked frusta."""
    out = []
    for i in range(rings):
        a0 = -math.pi / 2 + math.pi * i / rings
        a1 = -math.pi / 2 + math.pi * (i + 1) / rings
        out.append(prism(cx, cz, max(0.002, r * math.cos(a0)), cy + r * math.sin(a0), cy + r * math.sin(a1),
                         role, n, r_top=max(0.002, r * math.cos(a1))))
    return out


def foliage(cx, cy, cz, r, seed, role="foliage") -> Part:
    return {"shape": "foliage", "c": (cx, cy, cz), "r": r, "role": role, "seed": seed}


def _legs(W, D, h, style="taper", inset=0.05, role="leg", y0=0.0) -> List[Part]:
    """Four legs under a W x D footprint. style: taper, straight, metal,
    hairpin, bun, hidden (a recessed plinth), none."""
    if style == "none" or h <= 0.005:
        return []
    if style == "hidden":
        return [box(-W / 2 + 0.06, W / 2 - 0.06, y0, y0 + h, -D / 2 + 0.06, D / 2 - 0.06, "detail")]
    t = {"taper": 0.045, "straight": 0.05, "metal": 0.022, "hairpin": 0.012, "bun": 0.08}.get(style, 0.045)
    out = []
    for sx in (-1, 1):
        for sz in (-1, 1):
            x = sx * (W / 2 - inset - t / 2)
            z = sz * (D / 2 - inset - t / 2)
            if style == "taper":
                out.append(prism(x, z, t / 2, y0, y0 + h, role, 8, r_top=t * 0.75))
            elif style == "bun":
                out += sphere(x, y0 + h / 2, z, max(h / 2, 0.03), role, 10, 4)
            elif style == "hairpin":
                out.append(box(x - t / 2, x + t / 2, y0, y0 + h, z - t * 2, z + t * 2, "metal"))
            else:
                out.append(box(x - t / 2, x + t / 2, y0, y0 + h, z - t / 2, z + t / 2,
                               "metal" if style == "metal" else role))
    return out


# ---- seating --------------------------------------------------------------------

def sofa(W, D, H, p) -> List[Part]:
    seats = int(p.get("seats", max(1, min(4, round(W / 0.7)))))
    arm_style = p.get("arm", "track")
    back = p.get("back", "cushion")
    legs = p.get("legs", "taper")
    shape = p.get("shape", "straight")
    recliner = bool(p.get("recliner"))
    leg_h = 0.0 if legs in ("hidden", "none") else float(p.get("leg_height", 0.12))
    base_top = max(leg_h + 0.2, 0.34)
    seat_top = base_top + 0.1
    arm_w = {"track": min(0.18, W * 0.09), "rolled": min(0.2, W * 0.1), "slim": 0.07, "none": 0.0,
             "wide": min(0.26, W * 0.12)}.get(arm_style, 0.16)
    if recliner:
        arm_w = max(arm_w, 0.2)
    arm_h = min(H - 0.05, seat_top + (0.26 if not recliner else 0.3))
    back_d = min(0.22, D * 0.25)
    back_h = H if back != "low" else seat_top + 0.3
    parts: List[Part] = []

    main_d = D
    chaise_d = 0.0
    if shape in ("L", "U"):
        main_d = min(0.95, D * 0.58)
        chaise_d = D - main_d
    z_back = D / 2
    z_front = z_back - main_d

    def run(x0, x1, zf, zb, n):
        """Seat base, cushions and backrest for one straight run."""
        out = [box(x0, x1, leg_h, base_top, zf, zb)]
        if leg_h > 0:
            out += [p_ for p_ in _legs(x1 - x0, zb - zf, leg_h, legs, inset=0.04)]
            for q in out[1:]:
                _shift(q, (x0 + x1) / 2, (zf + zb) / 2)
        seat_d = zb - zf - back_d
        for i in range(n):
            sx0 = x0 + i * (x1 - x0) / n
            sx1 = x0 + (i + 1) * (x1 - x0) / n
            if back == "tight" and n > 1 and p.get("bench_seat"):
                continue
            out.append(box(sx0 + 0.008, sx1 - 0.008, base_top, seat_top, zf + 0.01, zf + seat_d, "cushion"))
            if recliner:
                out.append(box(sx0 + 0.03, sx1 - 0.03, base_top - 0.12, base_top - 0.1, zf - 0.005, zf, "detail"))
        if p.get("bench_seat"):
            out.append(box(x0 + 0.01, x1 - 0.01, base_top, seat_top, zf + 0.01, zf + seat_d, "cushion"))
        out.append(box(x0, x1, base_top, back_h, zb - back_d, zb))
        if back in ("cushion", "high"):
            top = back_h - 0.05 if back == "cushion" else back_h + 0.08
            for i in range(n):
                sx0 = x0 + i * (x1 - x0) / n
                sx1 = x0 + (i + 1) * (x1 - x0) / n
                out.append(box(sx0 + 0.02, sx1 - 0.02, seat_top, top, zb - back_d - 0.13, zb - back_d, "cushion"))
        if p.get("tufted"):
            for i in range(1, 2 * n):
                x = x0 + i * (x1 - x0) / (2 * n)
                for y in (seat_top + 0.12, seat_top + 0.25):
                    out.append(box(x - 0.012, x + 0.012, y - 0.012, y + 0.012, zb - back_d - 0.005, zb - back_d,
                                   "detail"))
        return out

    inner_x0, inner_x1 = -W / 2 + arm_w, W / 2 - arm_w
    if shape == "straight":
        parts += run(inner_x0, inner_x1, z_front, z_back, seats)
    else:
        # the long run along the back, and chaise/return runs coming forward
        parts += run(inner_x0, inner_x1, z_front, z_back, seats)
        ret_w = min(0.95, W * 0.34)
        sides = (-1,) if shape == "L" else (-1, 1)
        for s in sides:
            x0 = -W / 2 + arm_w if s < 0 else W / 2 - arm_w - ret_w
            x1 = x0 + ret_w
            zf = z_front - chaise_d
            parts.append(box(x0, x1, leg_h, base_top, zf, z_front))
            parts.append(box(x0 + 0.01, x1 - 0.01, base_top, seat_top, zf + 0.01, z_front + 0.02, "cushion"))
            if leg_h > 0:
                for x in (x0 + 0.05, x1 - 0.05):
                    parts.append(prism(x, zf + 0.05, 0.022, 0, leg_h, "leg", 8))
    # arms
    if arm_w > 0:
        arm_zf = z_front - (chaise_d if shape in ("L", "U") else 0)
        for s in (-1, 1):
            if shape == "L" and s > 0:
                arm_zf_s = z_front
            else:
                arm_zf_s = arm_zf
            x0 = -W / 2 if s < 0 else W / 2 - arm_w
            parts.append(box(x0, x0 + arm_w, leg_h, arm_h, arm_zf_s, z_back))
            if arm_style == "rolled":
                parts.append(cyl_z(x0 + arm_w / 2, arm_h, arm_w * 0.62, arm_zf_s, z_back, "main", 10))
    if p.get("pillows"):
        for i, s in enumerate((-1, 1)):
            x = s * (W / 2 - arm_w - 0.22)
            parts.append(box(x - 0.2, x + 0.2, seat_top, seat_top + 0.36, z_back - back_d - 0.22,
                             z_back - back_d - 0.1, "pillow"))
    return parts


def _shift(part: Part, dx: float, dz: float) -> None:
    if part["shape"] == "box":
        part["x"] = (part["x"][0] + dx, part["x"][1] + dx)
        part["z"] = (part["z"][0] + dz, part["z"][1] + dz)
    elif part["shape"] == "prism":
        part["c"] = (part["c"][0] + dx, part["c"][1] + dz)


def armchair(W, D, H, p) -> List[Part]:
    parts = sofa(W, D, H, dict(p, seats=1, shape="straight"))
    if p.get("wings"):
        for s in (-1, 1):
            x = s * (W / 2 - 0.06)
            parts.append(box(x - 0.06, x + 0.06, H * 0.6, H, D / 2 - 0.35, D / 2))
    return parts


def chair(W, D, H, p) -> List[Part]:
    """Dining / accent / office chairs and stools."""
    kind = p.get("kind", "dining")
    back = p.get("back", "solid")
    legs = p.get("legs", "straight")
    seat = float(p.get("seat_height", 0.46 if kind != "bar" else 0.75))
    parts: List[Part] = []
    if kind == "office":
        for i in range(5):
            a = 2 * math.pi * i / 5
            parts.append(box(-0.02, 0.02, 0.05, 0.08, -0.02, W * 0.45, "metal"))
            _rotate_y(parts[-1], a)
            parts += sphere(math.sin(a) * W * 0.45, 0.03, math.cos(a) * W * 0.45, 0.03, "metal", 8, 3)
        parts.append(prism(0, 0, 0.03, 0.08, seat - 0.08, "metal", 10))
        parts.append(box(-W / 2 + 0.03, W / 2 - 0.03, seat - 0.08, seat, -D / 2, D / 2 - 0.05, "cushion"))
        parts.append(box(-W / 2 + 0.05, W / 2 - 0.05, seat + 0.05, H, D / 2 - 0.1, D / 2 - 0.04, "main"))
        parts.append(box(-0.03, 0.03, seat - 0.02, seat + 0.1, D / 2 - 0.08, D / 2 - 0.04, "metal"))
        if p.get("arms", True):
            for s in (-1, 1):
                parts.append(box(s * (W / 2 - 0.02) - 0.02, s * (W / 2 - 0.02) + 0.02, seat, seat + 0.22,
                                 -0.05, 0.12, "metal"))
                parts.append(box(s * (W / 2 - 0.02) - 0.04, s * (W / 2 - 0.02) + 0.04, seat + 0.22, seat + 0.25,
                                 -0.15, 0.15, "detail"))
        return parts
    if kind in ("stool", "bar"):
        round_seat = p.get("round", True)
        if round_seat:
            parts.append(prism(0, 0, W / 2, seat - 0.04, seat, "cushion", 18))
        else:
            parts.append(box(-W / 2, W / 2, seat - 0.04, seat, -D / 2, D / 2, "cushion"))
        parts += _legs(W * 0.85, D * 0.85, seat - 0.04, legs, inset=0.02)
        rail = seat * 0.35
        parts.append(box(-W * 0.38, W * 0.38, rail, rail + 0.02, -D * 0.38, -D * 0.36, "leg"))
        if kind == "bar" and back != "none":
            parts.append(box(-W / 2 + 0.02, W / 2 - 0.02, seat + 0.18, H, D / 2 - 0.04, D / 2, "main"))
            parts += [box(s * (W / 2 - 0.04) - 0.015, s * (W / 2 - 0.04) + 0.015, seat, seat + 0.2,
                          D / 2 - 0.04, D / 2, "leg") for s in (-1, 1)]
        return parts
    # dining / accent
    parts += _legs(W, D, seat - 0.05, legs, inset=0.025)
    upholstered = p.get("upholstered", False)
    parts.append(box(-W / 2, W / 2, seat - 0.05, seat, -D / 2, D / 2, "cushion" if upholstered else "main"))
    if back == "slat":
        for s in (-1, 1):
            parts.append(box(s * (W / 2 - 0.03) - 0.018, s * (W / 2 - 0.03) + 0.018, seat, H, D / 2 - 0.04, D / 2, "main"))
        for i in range(3):
            y = seat + 0.18 + i * (H - seat - 0.22) / 3
            parts.append(box(-W / 2 + 0.03, W / 2 - 0.03, y, y + 0.04, D / 2 - 0.035, D / 2 - 0.01, "main"))
    elif back == "spindle":
        parts.append(box(-W / 2 + 0.02, W / 2 - 0.02, H - 0.06, H, D / 2 - 0.04, D / 2, "main"))
        for i in range(6):
            x = -W / 2 + 0.05 + i * (W - 0.1) / 5
            parts.append(prism(x, D / 2 - 0.02, 0.009, seat, H - 0.06, "main", 6))
    elif back == "curved":
        for i in range(5):
            a = math.pi * (0.15 + 0.7 * i / 4)
            x, z = -math.cos(a) * W / 2, D / 2 - math.sin(a) * 0.14
            parts.append(box(x - W / 10, x + W / 10, seat + 0.12, H, z - 0.02, z + 0.02,
                             "cushion" if upholstered else "main"))
    elif back != "none":
        parts.append(box(-W / 2 + 0.02, W / 2 - 0.02, seat + 0.05, H, D / 2 - 0.05, D / 2,
                         "cushion" if upholstered else "main"))
        parts += [box(s * (W / 2 - 0.035) - 0.018, s * (W / 2 - 0.035) + 0.018, seat, seat + 0.06, D / 2 - 0.05, D / 2,
                      "leg") for s in (-1, 1)]
    if p.get("arms"):
        for s in (-1, 1):
            x = s * (W / 2 - 0.02)
            parts.append(box(x - 0.02, x + 0.02, seat, seat + 0.22, -D / 2 + 0.05, D / 2, "main"))
    return parts


def _rotate_y(part: Part, a: float) -> None:
    """Rotates a box about the vertical axis (stored as its 8 corners)."""
    (x0, x1), (y0, y1), (z0, z1) = part["x"], part["y"], part["z"]
    c, s = math.cos(a), math.sin(a)
    corners = [(x * c + z * s, y, -x * s + z * c) for y in (y0, y1) for x, z in ((x0, z0), (x1, z0), (x1, z1), (x0, z1))]
    part.clear()
    part.update({"shape": "hexa", "v": corners, "role": "metal"})


def ottoman(W, D, H, p) -> List[Part]:
    legs = p.get("legs", "hidden")
    leg_h = 0.0 if legs in ("hidden", "none") else 0.06
    if p.get("round"):
        return [prism(0, 0, W / 2, leg_h, H, "cushion", 24)] + _legs(W * 0.7, D * 0.7, leg_h, legs)
    parts = [box(-W / 2, W / 2, leg_h, H, -D / 2, D / 2, "cushion")] + _legs(W, D, leg_h, legs)
    if p.get("tufted"):
        for i in (-1, 0, 1):
            for j in (-1, 1):
                parts.append(box(i * W / 4 - 0.015, i * W / 4 + 0.015, H, H + 0.004, j * D / 4 - 0.015,
                                 j * D / 4 + 0.015, "detail"))
    return parts


def bench(W, D, H, p) -> List[Part]:
    parts = [box(-W / 2, W / 2, H - 0.05, H, -D / 2, D / 2, "main")]
    if p.get("cushion"):
        parts.append(box(-W / 2 + 0.02, W / 2 - 0.02, H, H + 0.06, -D / 2 + 0.02, D / 2 - 0.02, "cushion"))
    legs = p.get("legs", "panel")
    if legs == "panel":
        parts += [box(s * (W / 2 - 0.05) - 0.025, s * (W / 2 - 0.05) + 0.025, 0, H - 0.05, -D / 2 + 0.02, D / 2 - 0.02,
                      "main") for s in (-1, 1)]
    else:
        parts += _legs(W, D, H - 0.05, legs)
    if p.get("back"):
        parts.append(box(-W / 2, W / 2, H + 0.1, H + 0.42, D / 2 - 0.05, D / 2, "main"))
    return parts


# ---- tables ---------------------------------------------------------------------

def table(W, D, H, p) -> List[Part]:
    """Coffee, side, dining, console, bedside tables and desks."""
    top_shape = p.get("top", "rect")
    legs = p.get("legs", "four")
    top_t = float(p.get("top_thickness", 0.035))
    top_role = "glass" if p.get("glass_top") else "main"
    parts: List[Part] = []
    if top_shape in ("round", "oval"):
        parts.append(prism(0, 0, D / 2, H - top_t, H, top_role, 28, sx=W / D))
    else:
        parts.append(box(-W / 2, W / 2, H - top_t, H, -D / 2, D / 2, top_role))
    under = H - top_t
    if legs == "pedestal":
        parts.append(prism(0, 0, min(W, D) * 0.07, 0.03, under, "leg", 12))
        parts.append(prism(0, 0, min(W, D) * 0.3, 0, 0.03, "leg", 20))
    elif legs == "trestle":
        for s in (-1, 1):
            x = s * (W / 2 - 0.15)
            parts.append(box(x - 0.04, x + 0.04, 0.05, under, -0.04, 0.04, "leg"))
            parts.append(box(x - 0.05, x + 0.05, 0, 0.05, -D / 2 + 0.06, D / 2 - 0.06, "leg"))
        parts.append(box(-W / 2 + 0.15, W / 2 - 0.15, under * 0.35, under * 0.35 + 0.05, -0.025, 0.025, "leg"))
    elif legs == "panel":
        for s in (-1, 1):
            x = s * (W / 2 - 0.02)
            parts.append(box(x - 0.02, x + 0.02, 0, under, -D / 2, D / 2, top_role if top_role == "main" else "leg"))
    elif legs == "x_base":
        for s in (-1, 1):
            x = s * (W / 2 - 0.12)
            parts.append(box(x - 0.02, x + 0.02, 0, under, -D / 2 + 0.05, D / 2 - 0.05, "metal"))
    elif legs == "sled":
        for s in (-1, 1):
            x = s * (W / 2 - 0.08)
            parts.append(box(x - 0.015, x + 0.015, 0, under, -D / 2 + 0.05, -D / 2 + 0.08, "metal"))
            parts.append(box(x - 0.015, x + 0.015, 0, under, D / 2 - 0.08, D / 2 - 0.05, "metal"))
            parts.append(box(x - 0.015, x + 0.015, 0, 0.02, -D / 2 + 0.05, D / 2 - 0.05, "metal"))
    else:
        style = {"four": "straight", "taper": "taper", "metal": "metal", "hairpin": "hairpin"}.get(legs, "straight")
        inset = 0.04 if top_shape == "rect" else min(W, D) * 0.18
        parts += _legs(W, D, under, style, inset=inset)
    if p.get("shelf"):
        parts.append(box(-W / 2 + 0.06, W / 2 - 0.06, 0.1, 0.13, -D / 2 + 0.06, D / 2 - 0.06, "main"))
    drawers = int(p.get("drawers", 0))
    if drawers:
        dw = min(0.45, W * 0.9 / drawers) if not p.get("drawer_block") else W * 0.35
        dh = min(0.16, under * 0.3) if not p.get("drawer_block") else under - 0.1
        for i in range(drawers if not p.get("drawer_block") else 1):
            x0 = -W / 2 + 0.05 + i * (dw + 0.02) if not p.get("drawer_block") else W / 2 - 0.05 - dw
            parts.append(box(x0, x0 + dw, under - dh, under, -D / 2 + 0.03, D / 2 - 0.05, "main"))
            parts.append(box(x0 + dw / 2 - 0.05, x0 + dw / 2 + 0.05, under - dh / 2 - 0.008, under - dh / 2 + 0.008,
                             -D / 2 + 0.015, -D / 2 + 0.03, "handle"))
            if p.get("drawer_block"):
                n = int(p.get("drawers", 3))
                for k in range(1, n):
                    y = under - k * dh / n
                    parts.append(box(x0 + 0.01, x0 + dw - 0.01, y - 0.004, y + 0.004, -D / 2 + 0.025, -D / 2 + 0.03,
                                     "detail"))
    if p.get("mirror"):
        mh = float(p.get("mirror_height", 0.8))
        mw = min(W * 0.7, 0.8)
        parts.append(box(-mw / 2 - 0.03, mw / 2 + 0.03, H, H + mh + 0.03, D / 2 - 0.05, D / 2 - 0.02, "main"))
        parts.append(box(-mw / 2, mw / 2, H + 0.03, H + mh, D / 2 - 0.055, D / 2 - 0.05, "mirror"))
    return parts


# ---- storage --------------------------------------------------------------------

def storage(W, D, H, p) -> List[Part]:
    """Cabinets, sideboards, wardrobes, dressers, TV units, bedside tables."""
    legs = p.get("legs", "straight")
    leg_h = 0.0 if legs in ("none", "plinth") else float(p.get("leg_height", 0.12))
    parts: List[Part] = []
    if legs == "plinth":
        parts.append(box(-W / 2 + 0.03, W / 2 - 0.03, 0, 0.08, -D / 2 + 0.03, D / 2 - 0.02, "detail"))
        leg_h = 0.08
    else:
        parts += _legs(W, D, leg_h, legs, inset=0.04)
    body_y0 = leg_h
    parts.append(box(-W / 2, W / 2, body_y0, H, -D / 2, D / 2))
    front = -D / 2 - 0.004
    layout = p.get("front", [["doors", 2]])      # list of [kind, count, share?] columns left to right
    shares = [float(c[2]) if len(c) > 2 else 1.0 for c in layout]
    total = sum(shares)
    x = -W / 2
    handle = p.get("handles", "bar")
    for col, share in zip(layout, shares):
        cw = W * share / total
        kind, n = col[0], int(col[1])
        x0, x1 = x + 0.015, x + cw - 0.015
        y0, y1 = body_y0 + 0.02, H - 0.02
        if kind == "open":
            parts.append(box(x0, x1, y0, y1, front, -D / 2 + 0.02, "back"))      # recess
            for k in range(1, n + 1):
                yy = y0 + k * (y1 - y0) / (n + 1)
                parts.append(box(x0, x1, yy - 0.01, yy + 0.01, front - 0.002, -D / 2 + 0.2, "main"))
        elif kind == "glass":
            for k in range(n):
                gx0 = x0 + k * (x1 - x0) / n
                gx1 = gx0 + (x1 - x0) / n
                parts.append(box(gx0 + 0.03, gx1 - 0.03, y0 + 0.03, y1 - 0.03, front - 0.002, front, "glass"))
                parts.append(_handle(handle, (gx1 - 0.05) if k % 2 == 0 else (gx0 + 0.05), (y0 + y1) / 2, front, True))
        elif kind == "drawers":
            for k in range(1, n):
                yy = y0 + k * (y1 - y0) / n
                parts.append(box(x0, x1, yy - 0.005, yy + 0.005, front, -D / 2, "detail"))
            for k in range(n):
                yy = y0 + (k + 0.5) * (y1 - y0) / n
                parts.append(_handle(handle, (x0 + x1) / 2, yy, front, False))
        else:   # doors
            for k in range(1, n):
                xx = x0 + k * (x1 - x0) / n
                parts.append(box(xx - 0.004, xx + 0.004, y0, y1, front, -D / 2, "detail"))
            for k in range(n):
                dx0 = x0 + k * (x1 - x0) / n
                dx1 = dx0 + (x1 - x0) / n
                hx = dx1 - 0.05 if k % 2 == 0 else dx0 + 0.05
                parts.append(_handle(handle, hx, y0 + (y1 - y0) * (0.5 if H < 1.2 else 0.45), front, True))
        if x + cw < W / 2 - 0.01:
            parts.append(box(x + cw - 0.006, x + cw + 0.006, body_y0, H, front, -D / 2, "detail"))
        x += cw
    if p.get("top") == "marble":
        parts.append(box(-W / 2 - 0.01, W / 2 + 0.01, H, H + 0.025, -D / 2 - 0.01, D / 2, "stone"))
    if p.get("books"):
        parts += _books(W, D, H, body_y0)
    return parts


def _handle(style, x, y, front, vertical) -> Part:
    if style == "knob":
        return prism(x, front - 0.01, 0.012, y - 0.012, y + 0.012, "handle", 8)
    if style == "none":
        return box(x - 0.001, x + 0.001, y - 0.001, y + 0.001, front - 0.001, front, "detail")
    if vertical:
        return box(x - 0.008, x + 0.008, y - 0.1, y + 0.1, front - 0.02, front, "handle")
    return box(x - 0.08, x + 0.08, y - 0.008, y + 0.008, front - 0.02, front, "handle")


def _books(W, D, H, y0) -> List[Part]:
    parts = []
    shelves = max(2, round((H - y0) / 0.38))
    for i in range(0, shelves, 2):
        y = y0 + 0.02 + i * (H - y0) / shelves
        x = -W / 2 + 0.05
        k = 0
        while x < W / 2 - 0.25:
            bw = 0.03 + 0.01 * ((k * 7 + i) % 3)
            bh = min(0.26, (H - y0) / shelves - 0.05) * (0.8 + 0.1 * ((k * 5 + i) % 3))
            parts.append(box(x, x + bw, y, y + bh, -D / 2 + 0.03, D / 2 - 0.03, f"book{(k + i) % 4}"))
            x += bw + 0.004
            k += 1
            if k % 9 == 0:
                x += 0.12
    return parts


def bookshelf(W, D, H, p) -> List[Part]:
    t = 0.025
    open_back = p.get("open_back", False)
    frame = "metal" if p.get("frame") == "metal" else "main"
    parts = [box(-W / 2, -W / 2 + t, 0, H, -D / 2, D / 2, frame), box(W / 2 - t, W / 2, 0, H, -D / 2, D / 2, frame),
             box(-W / 2, W / 2, H - t, H, -D / 2, D / 2), box(-W / 2, W / 2, 0, 0.06, -D / 2, D / 2)]
    if not open_back:
        parts.append(box(-W / 2 + t, W / 2 - t, 0.06, H - t, D / 2 - 0.012, D / 2, "back"))
    shelves = int(p.get("shelves", max(2, round(H / 0.38))))
    for i in range(1, shelves):
        y = 0.06 + i * (H - 0.06) / shelves
        parts.append(box(-W / 2 + t, W / 2 - t, y - t / 2, y + t / 2, -D / 2, D / 2 - 0.012))
    if p.get("books", True):
        parts += _books(W, D, H, 0.06)
    return parts


# ---- bedroom ----------------------------------------------------------------------

def bed(W, D, H, p) -> List[Part]:
    head = p.get("headboard", "panel")
    frame = p.get("frame", "platform")
    frame_top = 0.32 if frame != "low" else 0.2
    leg_h = 0.1 if frame == "legs" else 0.0
    parts: List[Part] = []
    parts.append(box(-W / 2, W / 2, leg_h if frame == "legs" else 0.0, frame_top, -D / 2, D / 2 - 0.08, "frame"))
    if frame == "legs":
        parts += _legs(W, D - 0.08, leg_h, p.get("legs", "taper"), inset=0.05, role="frame_leg")
        for q in parts[-4:]:
            _shift(q, 0, -0.04)
    if frame == "storage":
        for s in (-1, 1):
            parts.append(box(s * W / 4 - W / 5, s * W / 4 + W / 5, 0.06, frame_top - 0.04, -D / 2 - 0.004, -D / 2,
                             "detail"))
    mt = frame_top + float(p.get("mattress", 0.22))
    parts.append(box(-W / 2 + 0.03, W / 2 - 0.03, frame_top, mt, -D / 2 + 0.03, D / 2 - 0.1, "mattress"))
    parts.append(box(-W / 2 + 0.01, W / 2 - 0.01, mt - 0.04, mt + 0.03, -D / 2 + 0.01, D / 2 - 0.6, "main"))
    if p.get("throw", True):
        parts.append(box(-W / 2, W / 2, mt + 0.03, mt + 0.045, -D / 2 + 0.05, -D / 2 + 0.55, "throw"))
    n_p = 1 if W < 1.2 else 2
    pw = (W - 0.2) / n_p - (0.06 if n_p > 1 else 0)
    for i in range(n_p):
        x0 = -W / 2 + 0.1 + i * (pw + 0.06)
        parts.append(box(x0, x0 + pw, mt, mt + 0.14, D / 2 - 0.62, D / 2 - 0.14, "pillow"))
    hb_h = {"panel": H, "tall": max(H, 1.3), "low": frame_top + 0.45, "none": frame_top}.get(head, H)
    if head == "slatted":
        for i in range(9):
            x = -W / 2 + 0.04 + i * (W - 0.08) / 8
            parts.append(box(x - 0.03, x + 0.03, frame_top, H, D / 2 - 0.08, D / 2 - 0.04, "frame"))
        parts.append(box(-W / 2, W / 2, H - 0.06, H, D / 2 - 0.09, D / 2 - 0.03, "frame"))
    elif head in ("upholstered", "tufted", "wingback"):
        parts.append(box(-W / 2 - 0.03, W / 2 + 0.03, 0, hb_h, D / 2 - 0.1, D / 2, "main"))
        if head == "tufted":
            for i in range(1, 8):
                for y in (mt + 0.25, mt + 0.45):
                    x = -W / 2 + i * W / 8
                    parts.append(box(x - 0.012, x + 0.012, y - 0.012, y + 0.012, D / 2 - 0.105, D / 2 - 0.1, "detail"))
        if head == "wingback":
            for s in (-1, 1):
                x = s * (W / 2 + 0.03)
                parts.append(box(x - 0.08 if s > 0 else x, x if s > 0 else x + 0.08, mt, hb_h, D / 2 - 0.3, D / 2, "main"))
    elif head != "none":
        parts.append(box(-W / 2, W / 2, 0, hb_h, D / 2 - 0.08, D / 2, "frame"))
    if p.get("footboard"):
        parts.append(box(-W / 2, W / 2, 0, frame_top + 0.2, -D / 2 - 0.04, -D / 2 + 0.02, "frame"))
    return parts


# ---- lighting -----------------------------------------------------------------------

def floor_lamp(W, D, H, p) -> List[Part]:
    style = p.get("style", "drum")
    r = W / 2
    if style == "tripod":
        parts = []
        for i in range(3):
            a = 2 * math.pi * i / 3
            parts.append(box(-0.012, 0.012, 0, H * 0.72, -0.012, 0.012, "leg"))
            parts[-1] = {"shape": "hexa", "role": "leg", "v": _slanted(math.cos(a) * r * 0.8, math.sin(a) * r * 0.8,
                                                                         0, 0, 0, H * 0.72, 0.015)}
        parts.append(prism(0, 0, r * 0.9, H * 0.65, H, "shade", 20, r_top=r * 0.7))
        return parts
    if style == "arc":
        parts = [box(-0.14, 0.14, 0, 0.05, -0.14, 0.14, "stone")]
        steps = 8
        for i in range(steps):
            a0, a1 = math.pi * i / (2 * steps), math.pi * (i + 1) / (2 * steps)
            x0, y0 = (1 - math.cos(a0)) * W * 0.9, math.sin(a0) * (H - 0.3) + 0.05
            x1, y1 = (1 - math.cos(a1)) * W * 0.9, math.sin(a1) * (H - 0.3) + 0.05
            parts.append({"shape": "hexa", "role": "metal", "v": _slanted(x0 - W * 0.45, 0, x1 - W * 0.45, 0, y0, y1, 0.012)})
        parts.append(prism(W * 0.45, 0, 0.18, H - 0.45, H - 0.25, "shade", 20, r_top=0.08))
        return parts
    parts = [prism(0, 0, r * 0.6, 0, 0.03, "metal", 18), prism(0, 0, 0.012, 0.03, H - 0.3, "metal", 8)]
    if style == "globe":
        parts += sphere(0, H - 0.18, 0, r * 0.55, "bulb", 14, 6)
    elif style == "torchiere":
        parts.append(prism(0, 0, 0.04, H - 0.3, H - 0.1, "metal", 12, r_top=r * 0.9))
    else:
        parts.append(prism(0, 0, r, H - 0.34, H, "shade", 20, r_top=r * (0.75 if style == "tapered" else 1.0)))
    return parts


def _slanted(x0, z0, x1, z1, y0, y1, t) -> List[Tuple[float, float, float]]:
    """8 corners of a thin rod from (x0, y0, z0) to (x1, y1, z1)."""
    return [(x0 - t, y0, z0 - t), (x0 + t, y0, z0 - t), (x0 + t, y0, z0 + t), (x0 - t, y0, z0 + t),
            (x1 - t, y1, z1 - t), (x1 + t, y1, z1 - t), (x1 + t, y1, z1 + t), (x1 - t, y1, z1 + t)]


def table_lamp(W, D, H, p) -> List[Part]:
    style = p.get("style", "drum")
    r = W / 2
    base = p.get("base", "column")
    parts: List[Part] = []
    if base == "ceramic":
        parts += sphere(0, H * 0.25, 0, min(r * 0.55, H * 0.25), "base", 14, 5)
        parts.append(prism(0, 0, 0.01, H * 0.5, H * 0.62, "metal", 6))
    else:
        parts += [prism(0, 0, r * 0.45, 0, 0.025, "base", 16), prism(0, 0, 0.012, 0.025, H * 0.62, "metal", 8)]
    if style == "globe":
        parts += sphere(0, H - r * 0.6, 0, r * 0.6, "bulb", 14, 6)
    elif style == "bell":
        parts.append(prism(0, 0, r, H * 0.6, H * 0.66, "shade", 20, r_top=r * 0.9))
        parts.append(prism(0, 0, r * 0.9, H * 0.66, H, "shade", 20, r_top=r * 0.25))
    else:
        parts.append(prism(0, 0, r, H * 0.6, H, "shade", 20, r_top=r * (0.72 if style == "tapered" else 1.0)))
    return parts


def pendant(W, D, H, p) -> List[Part]:
    """Hangs from the ceiling: y = H is the ceiling attachment."""
    style = p.get("style", "dome")
    r = W / 2
    count = int(p.get("count", 1))
    parts: List[Part] = [prism(0, 0, 0.05, H - 0.02, H, "metal", 12)]
    xs = [0.0] if count == 1 else [(-W / 2 + r / count + i * (W - 2 * r / count) / (count - 1)) for i in range(count)]
    rr = r if count == 1 else min(r / count * 1.6, 0.18)
    for i, x in enumerate(xs):
        drop = H - (0.45 + 0.25 * (i % 2) if count > 1 else float(p.get("drop", 0.6)))
        top = {"globe": rr, "cone": rr * 0.6, "drum": rr * 0.4}.get(style, rr * 0.5)   # where the shade starts
        parts.append(prism(x, 0, 0.005, drop + top - 0.005, H, "metal", 5))
        if style == "globe":
            parts += sphere(x, drop, 0, rr, "bulb", 14, 6)
        elif style == "cone":
            parts.append(prism(x, 0, rr, drop - rr * 0.6, drop + rr * 0.6, "shade_dark", 18, r_top=0.03))
        elif style == "drum":
            parts.append(prism(x, 0, rr, drop - rr * 0.4, drop + rr * 0.4, "shade", 20))
        else:   # dome
            parts.append(prism(x, 0, rr, drop - rr * 0.3, drop, "shade_dark", 20, r_top=rr * 0.85))
            parts.append(prism(x, 0, rr * 0.85, drop, drop + rr * 0.5, "shade_dark", 20, r_top=0.04))
    return parts


def chandelier(W, D, H, p) -> List[Part]:
    style = p.get("style", "branch")
    r = W / 2
    parts: List[Part] = [prism(0, 0, 0.06, H - 0.03, H, "metal", 12), prism(0, 0, 0.012, H * 0.45, H, "metal", 6)]
    tiers = 2 if style == "tiered" else 1
    for t in range(tiers):
        rr = r * (1 - 0.35 * t)
        y = H * (0.35 + 0.25 * t)
        arms = int(p.get("arms", 6)) - 2 * t
        if style == "ring":
            parts.append(prism(0, 0, rr, y - 0.02, y + 0.02, "metal", 36))
            parts.append(prism(0, 0, rr - 0.03, y - 0.021, y + 0.021, "bulb", 36))
            continue
        for i in range(arms):
            a = 2 * math.pi * i / arms
            x, z = math.cos(a) * rr, math.sin(a) * rr
            parts.append({"shape": "hexa", "role": "metal", "v": _slanted(0, 0, x, z, y + 0.08, y, 0.008)})
            parts.append(prism(x, z, 0.02, y, y + 0.05, "metal", 8))
            parts.append(prism(x, z, 0.035 if style != "crystal" else 0.02, y + 0.05, y + 0.14,
                               "shade" if style != "crystal" else "bulb", 10, r_top=0.02))
    return parts


def ceiling_light(W, D, H, p) -> List[Part]:
    style = p.get("style", "flush")
    r = W / 2
    if style == "square":
        return [box(-W / 2, W / 2, 0, H * 0.4, -D / 2, D / 2, "metal"), box(-W / 2 + 0.01, W / 2 - 0.01, H * 0.4, H,
                                                                           -D / 2 + 0.01, D / 2 - 0.01, "bulb")]
    if style == "disc":
        return [prism(0, 0, r, 0, H * 0.3, "bulb", 32), prism(0, 0, r, H * 0.3, H, "metal", 32)]
    return sphere(0, H, 0, r, "bulb", 20, 6)[:3] + [prism(0, 0, r * 0.95, H * 0.9, H, "metal", 24)]


# ---- decoration -----------------------------------------------------------------------

def plant(W, D, H, p) -> List[Part]:
    kind = p.get("kind", "bush")
    pot = p.get("pot", "round")
    r = W / 2
    pot_h = H * float(p.get("pot_share", 0.3))
    parts: List[Part] = []
    if pot == "square":
        parts.append(box(-r * 0.6, r * 0.6, 0, pot_h, -r * 0.6, r * 0.6, "pot"))
    elif pot == "basket":
        parts.append(prism(0, 0, r * 0.62, 0, pot_h, "basket", 16, r_top=r * 0.68))
    elif pot == "tapered":
        parts.append(prism(0, 0, r * 0.4, 0, pot_h, "pot", 16, r_top=r * 0.62))
    else:
        parts.append(prism(0, 0, r * 0.55, 0, pot_h, "pot", 16, r_top=r * 0.6))
    if kind == "tall":
        parts.append(prism(0, 0, 0.02, pot_h, H * 0.75, "stem", 6))
        for i, (fy, fr) in enumerate(((0.95, 0.45), (0.8, 0.55), (0.65, 0.5))):
            parts.append(foliage((i - 1) * r * 0.2, fy * H - fr * r, 0, fr * r * 1.4, i))
    elif kind == "palm":
        for i in range(7):
            a = 2 * math.pi * i / 7
            parts.append(foliage(math.cos(a) * r * 0.55, H * (0.62 + 0.05 * (i % 3)), math.sin(a) * r * 0.3,
                                 r * 0.42, i, "frond"))
        parts.append(prism(0, 0, 0.03, pot_h, H * 0.6, "stem", 6))
    elif kind == "succulent":
        for i in range(5):
            a = 2 * math.pi * i / 5
            parts.append(foliage(math.cos(a) * r * 0.25, pot_h + r * 0.25, math.sin(a) * r * 0.2, r * 0.4, i,
                                 "succulent"))
    elif kind == "flowering":
        parts.append(prism(0, 0, 0.015, pot_h, H * 0.6, "stem", 6))
        for i, (fx, fy, fr) in enumerate(((0, 0.7, 0.55), (-0.35, 0.58, 0.4), (0.38, 0.6, 0.4))):
            parts.append(foliage(fx * r, fy * H, 0, fr * r * 1.3, i))
            parts.append(foliage(fx * r, fy * H + fr * r * 0.3, -0.05, fr * r * 0.8, i + 10, "flower"))
    else:   # bush
        parts.append(prism(0, 0, 0.015, pot_h, H * 0.6, "stem", 6))
        for i, (fx, fy, fz, fr) in enumerate(((0.0, 0.62, 0.0, 0.55), (-0.35, 0.52, 0.1, 0.42),
                                               (0.38, 0.55, -0.05, 0.4), (0.1, 0.8, 0.1, 0.45),
                                               (-0.15, 0.4, -0.2, 0.35))):
            parts.append(foliage(fx * r, fy * H, fz * r, fr * r * 1.3, i))
    return parts


def vase(W, D, H, p) -> List[Part]:
    shape = p.get("shape", "tall")
    r = W / 2
    if shape == "round":
        parts = sphere(0, H * 0.45, 0, min(r, H * 0.45), "main", 16, 6)
        parts.append(prism(0, 0, r * 0.35, H * 0.85, H, "main", 14, r_top=r * 0.4))
    elif shape == "bottle":
        parts = [prism(0, 0, r, 0, H * 0.55, "main", 16, r_top=r * 0.9), prism(0, 0, r * 0.9, H * 0.55, H * 0.7, "main",
                                                                                16, r_top=r * 0.25),
                 prism(0, 0, r * 0.22, H * 0.7, H, "main", 12)]
    else:
        parts = [prism(0, 0, r * 0.7, 0, H, "main", 16, r_top=r)]
    if p.get("stems"):
        for i in range(3):
            parts.append(prism((i - 1) * r * 0.3, 0, 0.004, H, H * 1.6, "stem", 5))
            parts.append(foliage((i - 1) * r * 0.5, H * (1.5 + 0.1 * (i % 2)), 0, r * 0.6, i, "flower"))
    return parts


def decor(W, D, H, p) -> List[Part]:
    kind = p.get("kind", "bowl")
    if kind == "sphere":
        return sphere(0, H / 2, 0, H / 2, "main", 16, 6)
    if kind == "books":
        return [box(-W / 2, W / 2, i * H / 3, (i + 1) * H / 3 - 0.004, -D / 2 + 0.01 * i, D / 2 - 0.01 * i, f"book{i}")
                for i in range(3)]
    if kind == "candles":
        return [prism((i - 1) * W / 3, 0, W / 8, 0, H * (0.6 + 0.2 * i), "main", 12) for i in range(3)]
    return [prism(0, 0, W / 2 * 0.55, 0, H * 0.3, "main", 20, r_top=W / 2)]   # bowl


def tv(W, D, H, p) -> List[Part]:
    screen_h = W * 0.565 + 0.03
    stand = p.get("stand", "feet")
    lift = H - screen_h
    parts = [box(-W / 2, W / 2, lift, H, -0.025, 0.025, "screen_frame"),
             box(-W / 2 + 0.012, W / 2 - 0.012, lift + 0.012, H - 0.012, -0.03, -0.025, "screen")]
    if stand == "pedestal":
        parts += [box(-0.03, 0.03, 0.02, lift, -0.02, 0.02, "screen_frame"),
                  box(-W * 0.18, W * 0.18, 0, 0.02, -D / 2, D / 2, "screen_frame")]
    else:
        for s in (-1, 1):
            x = s * W * 0.38
            parts.append({"shape": "hexa", "role": "screen_frame", "v": _slanted(x, -D / 2, x, 0, 0, lift, 0.012)})
    return parts


def rug(W, D, H, p) -> List[Part]:
    if p.get("shape") == "round":
        return [prism(0, 0, D / 2, 0, H, "rug", 48, sx=W / D)]
    return [box(-W / 2, W / 2, 0, H, -D / 2, D / 2, "rug")]


GENERATORS = {
    "sofa": sofa, "armchair": armchair, "chair": chair, "ottoman": ottoman, "bench": bench, "table": table,
    "storage": storage, "bookshelf": bookshelf, "bed": bed, "floor_lamp": floor_lamp, "table_lamp": table_lamp,
    "pendant": pendant, "chandelier": chandelier, "ceiling_light": ceiling_light, "plant": plant, "vase": vase,
    "decor": decor, "tv": tv, "rug": rug,
}

# Legacy scene types -> (generator, parameters).
LEGACY = {
    "sofa": ("sofa", {}), "sectional_sofa": ("sofa", {"shape": "L"}), "armchair": ("armchair", {}),
    "chair": ("chair", {"kind": "dining", "back": "slat", "legs": "taper"}),
    "ottoman": ("ottoman", {"legs": "straight"}), "bench": ("bench", {"legs": "straight"}),
    "bed": ("bed", {"frame": "legs"}), "coffee_table": ("table", {"shelf": True}), "table": ("table", {}),
    "dining_table": ("table", {}), "side_table": ("table", {"shelf": True}), "desk": ("table", {}),
    "cabinet": ("storage", {}), "sideboard": ("storage", {"front": [["doors", 3]]}),
    "wardrobe": ("storage", {"front": [["doors", 3]], "legs": "plinth"}),
    "chest_of_drawers": ("storage", {"front": [["drawers", 4]]}),
    "tv_unit": ("storage", {"front": [["doors", 1], ["open", 1, 1.2], ["doors", 1]], "leg_height": 0.08}),
    "bookshelf": ("bookshelf", {}), "tv": ("tv", {}), "floor_lamp": ("floor_lamp", {}), "plant": ("plant", {}),
    "rug": ("rug", {}),
}


def build_parts(generator: str, dims: Tuple[float, float, float], params: Optional[Dict] = None) -> List[Part]:
    """Solids for a model. `generator` may also be a legacy scene type."""
    params = dict(params or {})
    if generator not in GENERATORS and generator in LEGACY:
        generator, legacy = LEGACY[generator]
        params = {**legacy, **params}
    fn = GENERATORS.get(generator)
    if fn is None:
        raise KeyError(generator)
    W, D, H = dims
    return fn(W, D, H, params)


# ---- faces -----------------------------------------------------------------------

def _quad_faces_hexa(v) -> List:
    """Faces of an 8-corner solid: v[0:4] bottom ring, v[4:8] top ring."""
    b, t = v[:4], v[4:]
    faces = []
    for i in range(4):
        j = (i + 1) % 4
        faces.append([b[i], b[j], t[j], t[i]])
    faces.append([t[0], t[1], t[2], t[3]])
    faces.append([b[3], b[2], b[1], b[0]])
    return faces


def _normal(face) -> Tuple[float, float, float]:
    """Outward normal from the face's winding (counter-clockwise seen from outside)."""
    ax, ay, az = (face[1][k] - face[0][k] for k in range(3))
    bx, by, bz = (face[-1][k] - face[0][k] for k in range(3))
    nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
    L = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
    return nx / L, ny / L, nz / L


def part_faces(part: Part) -> List[Tuple[List[Tuple[float, float, float]], Tuple[float, float, float]]]:
    """Faces of one solid as (vertices in local metres, outward normal).
    Box faces are quads whose first edge runs along the face's width, so a
    texture can be laid on them at real scale."""
    shape = part["shape"]
    if shape == "foliage":
        return []
    if shape == "box":
        (x0, x1), (y0, y1), (z0, z1) = part["x"], part["y"], part["z"]
        return [
            ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),   # front
            ([(x1, y0, z1), (x0, y0, z1), (x0, y1, z1), (x1, y1, z1)], (0, 0, 1)),    # back
            ([(x0, y0, z1), (x0, y0, z0), (x0, y1, z0), (x0, y1, z1)], (-1, 0, 0)),   # left
            ([(x1, y0, z0), (x1, y0, z1), (x1, y1, z1), (x1, y1, z0)], (1, 0, 0)),    # right
            ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),    # top
            ([(x0, y0, z1), (x1, y0, z1), (x1, y0, z0), (x0, y0, z0)], (0, -1, 0)),   # bottom
        ]
    if shape == "hexa":
        faces = _quad_faces_hexa(part["v"])
        cx = sum(p[0] for p in part["v"]) / 8
        cy = sum(p[1] for p in part["v"]) / 8
        cz = sum(p[2] for p in part["v"]) / 8
        out = []
        for f in faces:
            n = _normal(f)
            fc = [sum(p[k] for p in f) / 4 for k in range(3)]
            if n[0] * (fc[0] - cx) + n[1] * (fc[1] - cy) + n[2] * (fc[2] - cz) < 0:
                f = f[::-1]
                n = (-n[0], -n[1], -n[2])
            out.append((f, n))
        return out
    n = part["n"]
    ang = [2 * math.pi * i / n for i in range(n)]
    faces = []
    if shape == "prism":
        cx, cz = part["c"]
        r0, r1 = part["r"], part["r_top"]
        sx = part.get("sx", 1.0)
        y0, y1 = part["y"]
        bot = [(cx + sx * r0 * math.cos(a), y0, cz + r0 * math.sin(a)) for a in ang]
        top = [(cx + sx * r1 * math.cos(a), y1, cz + r1 * math.sin(a)) for a in ang]
        for i in range(n):
            j = (i + 1) % n
            am = ang[i] + math.pi / n
            slope = (r0 - r1) / max(1e-6, y1 - y0)
            nx, ny, nz = math.cos(am) / max(sx, 1e-3), slope, math.sin(am)
            L = math.sqrt(nx * nx + ny * ny + nz * nz)
            faces.append(([bot[i], bot[j], top[j], top[i]], (nx / L, ny / L, nz / L)))
        if r1 > 0.003:
            faces.append((top[::-1], (0, 1, 0)))
        if r0 > 0.003:
            faces.append((bot, (0, -1, 0)))
        return faces
    # horizontal cylinders
    r = part["r"]
    if shape == "cylx":
        cy, cz = part["c"]
        x0, x1 = part["x"]
        ring = [(cy + r * math.cos(a), cz + r * math.sin(a)) for a in ang]
        for i in range(n):
            j = (i + 1) % n
            am = ang[i] + math.pi / n
            faces.append(([(x0, ring[i][0], ring[i][1]), (x0, ring[j][0], ring[j][1]), (x1, ring[j][0], ring[j][1]),
                           (x1, ring[i][0], ring[i][1])], (0, math.cos(am), math.sin(am))))
        faces.append(([(x1, y, z) for y, z in ring], (1, 0, 0)))
        faces.append(([(x0, y, z) for y, z in ring[::-1]], (-1, 0, 0)))
        return faces
    cx, cy = part["c"]
    z0, z1 = part["z"]
    ring = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in ang]
    for i in range(n):
        j = (i + 1) % n
        am = ang[i] + math.pi / n
        faces.append(([(ring[i][0], ring[i][1], z0), (ring[j][0], ring[j][1], z0), (ring[j][0], ring[j][1], z1),
                       (ring[i][0], ring[i][1], z1)], (math.cos(am), math.sin(am), 0)))
    faces.append(([(x, y, z1) for x, y in ring[::-1]], (0, 0, 1)))
    faces.append(([(x, y, z0) for x, y in ring], (0, 0, -1)))
    return faces
