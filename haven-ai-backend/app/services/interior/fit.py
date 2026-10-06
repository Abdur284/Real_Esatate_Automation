"""
Size matching for replacements.

"Replace this sofa with that one" means the new sofa takes the old one's
place: same spot, same turn, and about the same size, not the catalogue
piece dropped in at its own size. The catalogue (real) size is the starting
point; the scale is worked out from the size of what is being replaced:

- a 3D piece added earlier: its size in metres is known exactly;
- a piece from the photo: its outline in the picture. The new piece is
  projected through the same camera at the same spot, so matching the
  picture size also matches the physical size the photo implies, including
  perspective. A few rounds settle it (a deeper piece reaches further back
  and looks a little smaller).

Real furniture is scaled uniformly by its dominant dimension (the width of a
sofa, the height of a wardrobe or a lamp), so it keeps its real proportions;
a tall floor piece may then be made at most 15% wider or narrower toward the
target, which does not visibly distort it. Rugs, curtains and blinds are soft, so width and
length (or drop) are fitted independently. A side cut off by the edge of the
photo says nothing about size and is not used; a piece whose real size would
change by more than half or double is kept within those limits.
"""
import math
from typing import Dict, Optional, Tuple

from . import geometry

# soft pieces: (image width axis, image height axis) fitted independently
FREE_FIT = {"rug": ("x", "z"), "curtains": ("x", "y"), "blinds": ("x", "y")}
STRETCH = 1.15                  # most one axis may differ from the uniform scale
REAL_MIN, REAL_MAX = 0.5, 2.0   # how far a real piece is scaled from its real size
EDGE = 0.004                    # bounds this close to the picture edge are cut off


def library_size(obj: Dict) -> Dict[str, float]:
    m = obj["model"]
    return {"width": m["width_m"], "depth": m["depth_m"], "height": m["height_m"]}


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _box(obj: Dict, scene: Dict, cam) -> Tuple[float, float]:
    """Picture width and height (px) of a model at its current transform."""
    geometry.settle(obj, scene)
    pts = geometry._points(obj, scene, cam)
    (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
    return max(1.0, float(x1 - x0)), max(1.0, float(y1 - y0))


def _edges(obj: Dict, scene: Dict, cam) -> Tuple[float, float, float, float]:
    geometry.settle(obj, scene)
    pts = geometry._points(obj, scene, cam)
    (x0, y0), (x1, y1) = pts.min(0), pts.max(0)
    return float(x0), float(y0), float(x1), float(y1)


def _align(new: Dict, b: Dict, scene: Dict, cam) -> None:
    """Moves the piece so its outline sits where the old one was: same
    middle across, and the same bottom (floor, table), middle (wall) or top
    (ceiling). A model's position is its front-centre point on the floor,
    which is not the middle of its outline once perspective pulls the far
    side toward the vanishing point, so this is measured, not assumed."""
    W, H = geometry.size(scene)
    tx0, ty0, tx1, ty1 = b["x"] * W, b["y"] * H, (b["x"] + b["w"]) * W, (b["y"] + b["h"]) * H
    p = new["transform"]["position"]
    for _ in range(3):
        x0, y0, x1, y1 = _edges(new, scene, cam)
        dx = (tx0 + tx1) / 2 - (x0 + x1) / 2
        dy = {"wall": (ty0 + ty1) / 2 - (y0 + y1) / 2, "ceiling": ty0 - y0}.get(new["placement"], ty1 - y1)
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            break
        p["x"] = round(min(1.0, max(0.0, p["x"] + dx / W)), 4)
        p["y"] = round(min(1.0, max(0.0, p["y"] + dy / H)), 4)


def _cut_off(b: Dict) -> Dict[str, bool]:
    return {"w": b["x"] <= EDGE or b["x"] + b["w"] >= 1 - EDGE,
            "h": b["y"] <= EDGE or b["y"] + b["h"] >= 1 - EDGE}


def _limits(free: bool) -> Tuple[float, float]:
    return (geometry.SCALE_MIN, geometry.SCALE_MAX) if free else (REAL_MIN, REAL_MAX)


def _fit_picture(new: Dict, scale: Dict, tw: float, th: float, cut: Dict, free, lo: float, hi: float,
                 scene: Dict, cam) -> str:
    """Scales `new` in place (scale is its transform's scale) until its
    outline is tw x th px. Returns which size it was matched on."""
    if free:
        for _ in range(4):
            nw, nh = _box(new, scene, cam)
            if not cut["w"]:
                scale[free[0]] = _clamp(scale[free[0]] * tw / nw, lo, hi)
            if not cut["h"]:
                scale[free[1]] = _clamp(scale[free[1]] * th / nh, lo, hi)
        return "free"
    dom = "h" if cut["w"] or (th > tw and not cut["h"]) else "w"
    u = scale["y"] if dom == "w" else scale["z"]       # the axes never nudged below
    for _ in range(5):
        nw, nh = _box(new, scene, cam)
        r = (tw / nw) if dom == "w" else (th / nh)
        u = _clamp(u * r, lo, hi)
        for a in scale:
            scale[a] = u
        if abs(r - 1) < 0.01:
            break
    # only a width may be nudged: a floor piece's picture height mixes its
    # height with its depth, and stretching a mirror or a picture shows
    if dom == "h" and not cut["w"] and new["placement"] in ("floor", "surface"):
        nw, _ = _box(new, scene, cam)
        scale["x"] = _clamp(scale["x"] * _clamp(tw / nw, 1 / STRETCH, STRETCH), geometry.SCALE_MIN, geometry.SCALE_MAX)
    return "width" if dom == "w" else "height"


def match(new: Dict, old: Dict, scene: Dict, align: bool = True) -> Dict:
    """Sets `new`'s scale so it fills the space `old` filled, at `new`'s
    current position and rotation (for a piece from the photo, also lines
    its outline up with the old one when `align`). Returns the fit record
    kept on the object."""
    lib = library_size(new)
    free = FREE_FIT.get(new["type"])
    lo, hi = _limits(bool(free))
    scale = {"x": 1.0, "y": 1.0, "z": 1.0}
    new["transform"]["scale"] = scale
    record = {"mode": "match", "replaced": old["label"], "library_size_m": lib}

    if old["source"] == "model" and old.get("model"):
        tw, td, th = geometry.model_dims(old)
        ratio = {"x": tw / lib["width"], "z": td / lib["depth"], "y": th / lib["height"]}
        record["target_m"] = {"width": round(tw, 3), "depth": round(td, 3), "height": round(th, 3)}
        if free:
            for a in free:
                scale[a] = _clamp(ratio[a], lo, hi)
            record.update(basis="free", uniform=False)
        else:
            dom = max(ratio, key=lambda a: {"x": tw, "z": td, "y": th}[a])
            u = _clamp(ratio[dom], lo, hi)
            for a in scale:
                scale[a] = u * (1.0 if a == dom else _clamp(ratio[a] / u, 1 / STRETCH, STRETCH))
            record.update(basis={"x": "width", "y": "height", "z": "depth"}[dom], uniform=True)
    else:
        b = old.get("bounds") or old["original"]["bbox"]
        W, H = geometry.size(scene)
        cam = geometry.camera(scene)
        tw, th = b["w"] * W, b["h"] * H
        cut = _cut_off(b)
        record["target_bounds"] = dict(b)
        if cut["w"] and cut["h"]:
            new["transform"]["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}
            return {"mode": "library", "replaced": old["label"], "library_size_m": lib,
                    "reason": "cut_off"}
        for _ in range(2 if align else 1):
            basis = _fit_picture(new, scale, tw, th, cut, free, lo, hi, scene, cam)
            if align:
                _align(new, b, scene, cam)
        record.update(basis=basis, uniform=not free)
        if cut["w"] or cut["h"]:
            record["note"] = "cut_off"

    scale = {a: round(v, 3) for a, v in scale.items()}
    new["transform"]["scale"] = scale
    record["scale"] = dict(scale)
    record["clamped"] = any(math.isclose(scale[a], lo, abs_tol=1e-3) or math.isclose(scale[a], hi, abs_tol=1e-3)
                            for a in scale) and not free
    return record


def keep_off_wall(obj: Dict, scene: Dict) -> None:
    """A fitted floor piece whose back would go through the wall is made a
    little shallower first (within the same 15% limit) rather than pushed
    forward, which would make it look bigger than what it replaces."""
    if obj["placement"] != "floor" or obj["source"] != "model":
        return
    W, H = geometry.size(scene)
    cam = geometry.camera(scene)
    pts, near = geometry.model_footprint(obj, cam, W, H)
    back = geometry.model_back_depth(obj, cam, W, H)
    wall = geometry.wall_depth(scene, cam, float(min(W - 1, max(0, pts[:, 0].mean()))))
    over = back - (wall + 0.04)
    if over <= 0:
        return
    sc = obj["transform"]["scale"]
    D = geometry.model_dims(obj)[1]
    u = max(sc["x"], sc["y"])
    z = max(sc["z"] * (D - over) / D, u / STRETCH, geometry.SCALE_MIN)
    sc["z"] = round(min(sc["z"], z), 3)
    if obj.get("fit", {}).get("scale"):
        obj["fit"]["scale"]["z"] = sc["z"]


def describe(record: Optional[Dict], obj: Dict) -> str:
    """One sentence for the editor about how the replacement was sized."""
    lib = library_size(obj)
    cat = f"{lib['width']:.2f} x {lib['depth']:.2f} x {lib['height']:.2f} m"
    Wm, Dm, Hm = geometry.model_dims(obj)
    now = f"{Wm:.2f} x {Dm:.2f} x {Hm:.2f} m"
    if not record or record.get("mode") != "match":
        if record and record.get("reason") == "cut_off":
            return (f"The original {record['replaced'].lower()} is cut off by the edge of the photo, so the "
                    f"catalogue size is used ({cat}).")
        return f"Shown at its catalogue size ({cat})."
    what = record["replaced"].lower()
    text = f"Sized to fill the space of the original {what}: {now} (catalogue size {cat})."
    if record.get("clamped"):
        text += " It was kept within a realistic size for this piece."
    return text + " You can still resize it."
