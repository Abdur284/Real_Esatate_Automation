"""
Layer 2: the editable scene and the operations that change it.

Every edit is an explicit, validated operation, for example

    {"operation": "update_object", "object_id": "sofa_001", "changes": {"color": "#222222"}}
    {"operation": "transform_object", "object_id": "sofa_001",
     "changes": {"position": {"x": 0.42, "y": 0.67}, "scale": {"x": 1.2, "y": 1.0}}}

An operation touches only the object or surface it names (plus things resting
on a moved/removed piece, which go with it). It is checked before it is
applied: the target exists, the property is editable for that kind of
element, values are in range, and positions obey the room's constraints
(clamped, with a note, rather than rejected). The scene is plain JSON.
"""
import copy
import re
from typing import Dict, List, Optional, Tuple

from . import catalog, fit, geometry
from .library import Item, get_library

SCHEMA_VERSION = 1
HEX = re.compile(catalog.HEX_RE)


class OperationError(ValueError):
    """The operation is not allowed (-> HTTP 422)."""


# ---- building the editable scene ---------------------------------------------

def capabilities(obj: Dict) -> Dict:
    """What the editor may do with an object. `library_category` is the part
    of the object library offered when the user changes it."""
    lib = get_library()
    info = catalog.type_info(obj["type"])
    editable = info.get("editable", True)
    fixed = obj["placement"] == "fixed"
    lib_cat = lib.category_for_type(obj["type"], obj["placement"]) if editable else None
    if obj["source"] == "model" and (obj.get("library_item") or {}).get("id") in lib.items:
        materials = lib.materials_for(lib.get(obj["library_item"]["id"]))
    else:
        materials = catalog.materials_for("object", obj["type"]) if editable else []
    return {
        "move": editable and not fixed,
        "resize": editable and not fixed,
        "rotate": catalog.rotate_mode(obj["type"], obj["source"], obj["placement"]) if editable and not fixed else None,
        # a real 3D model keeps its real finish unless its upholstery is marked recolourable
        "color": editable and not (obj["source"] == "model" and (obj.get("model") or {}).get("kind") == "mesh"
                                   and not obj["model"].get("tintable")),
        "materials": materials,
        "replace": lib_cat is not None,
        "library_category": lib_cat,
        "remove": info["category"] != "structure",
    }


def _editable_object(det: Dict, parent: Optional[str]) -> Dict:
    obj = {k: det[k] for k in ("id", "kind", "type", "label", "category", "placement", "source", "instance",
                               "confidence", "area", "color", "material_guess")}
    obj["material_source"] = "assumed"
    obj["original"] = {k: copy.deepcopy(det[k]) for k in ("anchor", "bbox", "outline", "color", "dimensions_m")}
    obj["original"]["type"] = det["type"]
    obj["transform"] = {"position": dict(det["anchor"]), "scale": {"x": 1.0, "y": 1.0}, "rotation": 0.0,
                        "flip": False}
    obj["appearance"] = {"color": None, "material": "original"}
    obj["parent"] = parent
    obj["capabilities"] = capabilities(obj)
    obj["editable"] = catalog.type_info(det["type"]).get("editable", True)
    return obj


def _editable_surface(det: Dict) -> Dict:
    s = copy.deepcopy(det)
    s["appearance"] = {"color": None, "material": "original"}
    s["capabilities"] = {"color": True, "materials": catalog.materials_for("surface", s["type"])}
    s["editable"] = True
    return s


def initial_scene(scene_id: str, detections: Dict, info: Dict) -> Dict:
    parents = {r["subject"]: r["object"] for r in detections["relationships"] if r["type"] == "on"}
    scene = {
        "schema_version": SCHEMA_VERSION,
        "scene_id": scene_id,
        "version": 0,
        "image": {k: info[k] for k in ("width", "height", "original_width", "original_height")},
        "quality": info["quality"],
        "warnings": list(info["warnings"]),
        "camera": detections["camera"],
        "layout": detections["layout"],
        "floor_rows": detections["floor_rows"],
        "surfaces": [_editable_surface(s) for s in detections["surfaces"]],
        "objects": [_editable_object(o, parents.get(o["id"])) for o in detections["objects"]],
        "relationships": detections["relationships"],
        "removed": [],
        "last_operation": None,
    }
    geometry.refresh(scene)
    return scene


# ---- helpers -------------------------------------------------------------------

def _find(items: List[Dict], item_id: str, what: str) -> Dict:
    for it in items:
        if it["id"] == item_id:
            return it
    raise OperationError(f"There is no {what} '{item_id}' in this room.")


def _check_color(value) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str) or not HEX.match(value):
        raise OperationError("Colours must be written as #RRGGBB.")
    return value.lower()


def _check_changes(changes: Dict, allowed: set) -> None:
    if not isinstance(changes, dict) or not changes:
        raise OperationError("`changes` must list at least one property.")
    extra = set(changes) - allowed
    if extra:
        raise OperationError(f"These properties cannot be changed here: {', '.join(sorted(extra))}.")


def _new_id(scene: Dict, type_: str) -> str:
    """A fresh id (sofa_002...) never used before in this room."""
    used = {o["id"] for o in scene["objects"]} | {r["id"] for r in scene["removed"]}
    n = 1
    while f"{type_}_{n:03d}" in used:
        n += 1
    return f"{type_}_{n:03d}"


# Types that could be added before the library existed -> library item used now.
LEGACY_ITEMS = {"sectional_sofa": "sofa-l-shaped-sectional-sofa", "sofa": "sofa-modern-3-seater-sofa"}


def _resolve_item(spec: Dict, what: str = "object") -> Item:
    """The library item an add/replace refers to: by id, or (older clients)
    by a type, which picks that category's standard piece."""
    lib = get_library()
    if spec.get("library_item"):
        try:
            return lib.get(spec["library_item"])
        except KeyError:
            raise OperationError(f"There is no '{spec['library_item']}' in the object library.")
    type_ = spec.get("type")
    if type_ in LEGACY_ITEMS:
        return lib.get(LEGACY_ITEMS[type_])
    cat = lib.category_for_type(type_ or "")
    if not cat or cat not in lib.by_category:
        raise OperationError(f"'{type_}' is not in the object library.")
    return lib.default_item(cat)


def _position_for(old: Dict, placement: str) -> Dict[str, float]:
    """Where a replacement goes: the old object's anchor when both sit the
    same way; otherwise the matching point of the old object's outline (its
    centre on a wall, its top under a ceiling, its base on a table). A photo
    object's anchor is its base on the floor and its centre elsewhere."""
    floorish = ("floor", "floor_flat")
    same = old["placement"] == placement or (old["placement"] in floorish and placement in floorish)
    if same and (old["source"] == "model" or placement in floorish + ("wall",)):
        return dict(old["transform"]["position"])
    b = old["bounds"]
    y = {"wall": b["y"] + b["h"] / 2, "ceiling": b["y"]}.get(placement, b["y"] + b["h"])
    return {"x": b["x"] + b["w"] / 2, "y": y}


def _place(obj: Dict, scene: Dict, x: float, y: float) -> List[str]:
    """Puts a model at (x, y), keeping it where the room allows."""
    obj["transform"]["position"] = {"x": x, "y": y}
    geometry.settle(obj, scene)
    geometry.refresh(scene)
    cx, cy, note = geometry.clamp_position(obj, x, y, scene)
    obj["transform"]["position"] = {"x": cx, "y": cy}
    geometry.settle(obj, scene)
    return [note] if note else []


def _children(scene: Dict, parent_id: str) -> List[Dict]:
    return [o for o in scene["objects"] if o.get("parent") == parent_id]


def _default_spot(scene: Dict, placement: str) -> Tuple[float, float]:
    """Where a new piece appears: on the open floor, or the middle of the main wall."""
    if placement == "wall":
        walls = sorted((s for s in scene["surfaces"] if s["type"] == "wall"), key=lambda s: -s["area"])
        if walls:
            b = walls[0]["bbox"]
            return b["x"] + b["w"] / 2, b["y"] + b["h"] * 0.35
        return 0.5, 0.3
    rows = scene.get("floor_rows") or []
    if rows:
        r = rows[int(len(rows) * 0.55)]
        return (r[1] + r[2]) / 2, r[0]
    return 0.5, 0.8


# ---- operations ------------------------------------------------------------------

def apply_operation(scene: Dict, op: Dict) -> Tuple[Dict, List[str]]:
    """Returns (new scene, notes). The input scene is not modified."""
    if not isinstance(op, dict) or "operation" not in op:
        raise OperationError("An operation needs an `operation` name.")
    name = op["operation"]
    handler = HANDLERS.get(name)
    if handler is None:
        raise OperationError(f"Unknown operation '{name}'.")
    new = copy.deepcopy(scene)
    notes = handler(new, op)
    geometry.refresh(new)
    new["version"] = scene["version"] + 1
    new["last_operation"] = {k: v for k, v in op.items()}
    return new, notes


def op_update_object(scene: Dict, op: Dict) -> List[str]:
    obj = _find(scene["objects"], op.get("object_id"), "object")
    changes = op.get("changes") or {}
    _check_changes(changes, {"color", "material"})
    caps = obj["capabilities"]
    if "color" in changes:
        if not caps["color"]:
            raise OperationError(f"The colour of the {obj['label'].lower()} cannot be changed.")
        obj["appearance"]["color"] = _check_color(changes["color"])
    if "material" in changes:
        mat = changes["material"]
        allowed = caps["materials"] + (["original"] if obj["source"] == "detected" else [])
        if mat not in allowed:
            raise OperationError(f"'{mat}' is not a material for a {obj['label'].lower()}.")
        obj["appearance"]["material"] = mat
    return []


def op_update_surface(scene: Dict, op: Dict) -> List[str]:
    s = _find(scene["surfaces"], op.get("surface_id"), "surface")
    changes = op.get("changes") or {}
    _check_changes(changes, {"color", "material"})
    if "color" in changes:
        s["appearance"]["color"] = _check_color(changes["color"])
    if "material" in changes:
        mat = changes["material"]
        if mat != "original" and mat not in s["capabilities"]["materials"]:
            raise OperationError(f"'{mat}' is not a material for a {s['type']}.")
        s["appearance"]["material"] = mat
    return []


def op_transform_object(scene: Dict, op: Dict) -> List[str]:
    obj = _find(scene["objects"], op.get("object_id"), "object")
    changes = op.get("changes") or {}
    _check_changes(changes, {"position", "scale", "rotation", "flip"})
    caps = obj["capabilities"]
    t = obj["transform"]
    notes: List[str] = []
    if "scale" in changes:
        if not caps["resize"]:
            raise OperationError(f"The {obj['label'].lower()} cannot be resized.")
        sc = changes["scale"]
        keys = {"x", "y", "z"} if obj["source"] == "model" and obj["placement"] != "wall" else {"x", "y"}
        if not isinstance(sc, dict) or not sc or set(sc) - keys:
            raise OperationError(f"`scale` may set {', '.join(sorted(keys))}.")
        merged = {**t["scale"], **{k: float(v) if isinstance(v, (int, float)) else v for k, v in sc.items()}}
        try:
            notes += geometry.check_scale(obj, merged, scene)
        except ValueError as e:
            raise OperationError(str(e))
        t["scale"] = merged
    if "rotation" in changes:
        mode = caps["rotate"]
        r = changes["rotation"]
        if not isinstance(r, (int, float)):
            raise OperationError("`rotation` must be a number of degrees.")
        if mode == "yaw":
            t["rotation"] = round(float(r) % 360.0, 2)
        elif mode == "tilt":
            if not -45 <= r <= 45:
                raise OperationError("Wall items can be tilted by at most 45 degrees.")
            t["rotation"] = round(float(r), 2)
        else:
            raise OperationError(f"The {obj['label'].lower()} cannot be rotated. "
                                 + ("A piece from the photo can only be mirrored; replace it with a 3D "
                                    "model to turn it." if mode == "mirror" else ""))
    if "flip" in changes:
        if caps["rotate"] != "mirror" and obj["source"] == "detected":
            raise OperationError(f"The {obj['label'].lower()} cannot be mirrored.")
        t["flip"] = bool(changes["flip"])
    if "position" in changes:
        if not caps["move"]:
            raise OperationError(f"The {obj['label'].lower()} cannot be moved.")
        p = changes["position"]
        if not isinstance(p, dict) or not {"x", "y"} >= set(p) or not p:
            raise OperationError("`position` needs x and/or y (0 to 1).")
        x, y = p.get("x", t["position"]["x"]), p.get("y", t["position"]["y"])
        if not all(isinstance(v, (int, float)) for v in (x, y)):
            raise OperationError("Positions are numbers between 0 and 1.")
        geometry.refresh(scene)   # current bounds for the wall rule
        cx, cy, note = geometry.clamp_position(obj, float(x), float(y), scene)
        if note:
            notes.append(note)
        dx, dy = cx - t["position"]["x"], cy - t["position"]["y"]
        t["position"] = {"x": cx, "y": cy}
        geometry.settle(obj, scene)
        for child in _children(scene, obj["id"]):
            cp = child["transform"]["position"]
            child["transform"]["position"] = {"x": round(min(1, max(0, cp["x"] + dx)), 4),
                                              "y": round(min(1, max(0, cp["y"] + dy)), 4)}
            if child["source"] == "model" and child["placement"] == "surface":
                geometry.refresh(scene)
                geometry.settle(child, scene)
    return notes


def op_replace_object(scene: Dict, op: Dict) -> List[str]:
    """Swaps an object for a library item. The new piece gets a new id and
    takes the old one's place: same position, same turn (when both can
    turn) and, by default, about the same size -- the library item's real
    size is the starting point and fit.match scales it to fill the old one's
    space (`"fit": "catalogue"` keeps the real size). The old object is kept
    in `removed`, so reset or restore brings it back; nothing else in the
    room changes."""
    obj = _find(scene["objects"], op.get("object_id"), "object")
    changes = op.get("changes") or {}
    _check_changes(changes, {"library_item", "type", "color", "fit"})
    if not obj["capabilities"]["replace"]:
        raise OperationError(f"The {obj['label'].lower()} cannot be replaced.")
    mode = changes.get("fit", "match")
    if mode not in ("match", "catalogue"):
        raise OperationError("`fit` is 'match' (fill the original's space) or 'catalogue' (real size).")
    item = _resolve_item(changes)
    lib = get_library()
    new = lib.scene_object(item, _new_id(scene, item.category), _check_color(changes.get("color")))
    new["capabilities"] = capabilities(new)
    if obj["capabilities"]["rotate"] == new["capabilities"]["rotate"] and obj["capabilities"]["rotate"] in ("yaw", "tilt"):
        new["transform"]["rotation"] = obj["transform"].get("rotation", 0.0)
    new["replaces"] = {"id": obj["id"], "label": obj["label"]}
    pos = _position_for(obj, new["placement"])
    idx = scene["objects"].index(obj)
    scene["objects"][idx] = new
    for child in _children(scene, obj["id"]):
        child["parent"] = new["id"]
    scene["removed"].append({"id": obj["id"], "label": obj["label"], "source": obj["source"], "object": obj,
                             "replaced_by": new["id"]})
    new["transform"]["position"] = dict(pos)
    geometry.refresh(scene)
    if mode == "match" and new["capabilities"]["resize"]:
        new["fit"] = fit.match(new, obj, scene)
        fit.keep_off_wall(new, scene)
        pos = dict(new["transform"]["position"])
        notes = _place(new, scene, pos["x"], pos["y"])
        moved = new["transform"]["position"]
        if abs(moved["x"] - pos["x"]) + abs(moved["y"] - pos["y"]) > 0.004:
            # kept in the room somewhere else: fill the same part of the picture from there
            spot = dict(moved)
            new["fit"] = fit.match(new, obj, scene, align=False)
            fit.keep_off_wall(new, scene)
            notes = _place(new, scene, spot["x"], spot["y"])
    else:
        new["fit"] = {"mode": "library", "replaced": obj["label"], "library_size_m": fit.library_size(new)}
        notes = _place(new, scene, pos["x"], pos["y"])
    op["assigned_id"] = new["id"]
    how = "real size measured from the 3D model" if item.dimensions_source == "measured" else "typical size"
    return [f"Replaced with {item.name} ({how}). {fit.describe(new['fit'], new)}"] + notes


def op_fit_object(scene: Dict, op: Dict) -> List[str]:
    """Resizes a library piece to the size it was fitted to when it replaced
    something (`"size": "original"`) or back to its real catalogue size
    (`"size": "catalogue"`), where it stands now."""
    obj = _find(scene["objects"], op.get("object_id"), "object")
    changes = op.get("changes") or {}
    _check_changes(changes, {"size"})
    if obj["source"] != "model" or not obj["capabilities"]["resize"]:
        raise OperationError(f"The {obj['label'].lower()} cannot be resized this way.")
    size = changes["size"]
    record = obj.get("fit") or {}
    if size == "original":
        if record.get("mode") != "match" or not record.get("scale"):
            raise OperationError(f"The {obj['label'].lower()} did not replace anything it could match.")
        scale = dict(record["scale"])
    elif size == "catalogue":
        scale = {"x": 1.0, "y": 1.0, "z": 1.0}
    else:
        raise OperationError("`size` is 'original' or 'catalogue'.")
    obj["transform"]["scale"] = scale
    p = obj["transform"]["position"]
    notes = _place(obj, scene, p["x"], p["y"])
    Wm, Dm, Hm = geometry.model_dims(obj)
    what = f"the original {record['replaced'].lower()}'s size" if size == "original" else "its catalogue size"
    return [f"Back to {what}: {Wm:.2f} x {Dm:.2f} x {Hm:.2f} m."] + notes


def op_add_object(scene: Dict, op: Dict) -> List[str]:
    spec = op.get("object") or {}
    if not isinstance(spec, dict) or set(spec) - {"library_item", "type", "position", "color", "material"}:
        raise OperationError("`object` may set library_item, position, color and material.")
    item = _resolve_item(spec)
    lib = get_library()
    obj = lib.scene_object(item, _new_id(scene, item.category), _check_color(spec.get("color")))
    obj["capabilities"] = capabilities(obj)
    if "material" in spec:
        if spec["material"] not in obj["capabilities"]["materials"]:
            raise OperationError(f"'{spec['material']}' is not a material for {item.name}.")
        obj["appearance"]["material"] = spec["material"]
    scene["objects"].append(obj)
    geometry.refresh(scene)
    if "position" in spec:
        p = spec["position"]
        if not isinstance(p, dict) or not all(isinstance(p.get(k), (int, float)) for k in ("x", "y")):
            raise OperationError("`position` needs x and y (0 to 1).")
        x, y = float(p["x"]), float(p["y"])
    elif obj["placement"] == "floor_flat":
        x, y = _default_spot(scene, obj["placement"])
    else:
        x, y = geometry.free_spot(obj, scene)
    notes = _place(obj, scene, x, y)
    op["assigned_id"] = obj["id"]
    return notes


def op_remove_object(scene: Dict, op: Dict) -> List[str]:
    obj = _find(scene["objects"], op.get("object_id"), "object")
    if not obj["capabilities"]["remove"]:
        raise OperationError(f"The {obj['label'].lower()} is part of the building and cannot be removed.")
    gone = [obj] + _children(scene, obj["id"])
    ids = {o["id"] for o in gone}
    scene["objects"] = [o for o in scene["objects"] if o["id"] not in ids]
    scene["removed"] += [{"id": o["id"], "label": o["label"], "source": o["source"], "object": o} for o in gone]
    if len(gone) > 1:
        return [f"{', '.join(o['label'] for o in gone[1:])} on it went too."]
    return []


def op_restore_object(scene: Dict, op: Dict) -> List[str]:
    rid = op.get("object_id")
    entry = next((r for r in scene["removed"] if r["id"] == rid), None)
    if entry is None:
        raise OperationError(f"'{rid}' was not removed.")
    scene["removed"] = [r for r in scene["removed"] if r["id"] != rid]
    scene["objects"].append(entry["object"])
    return []


def op_reset_object(scene: Dict, op: Dict) -> List[str]:
    obj = _find(scene["objects"], op.get("object_id"), "object")
    if obj.get("replaces"):
        # undo a replacement: the original piece comes back as it was
        old_id = obj["replaces"]["id"]
        entry = next((r for r in scene["removed"] if r["id"] == old_id), None)
        if entry is None:
            raise OperationError("The original of this object is not available.")
        scene["removed"] = [r for r in scene["removed"] if r["id"] != old_id]
        idx = scene["objects"].index(obj)
        scene["objects"][idx] = entry["object"]
        for child in _children(scene, obj["id"]):
            child["parent"] = old_id
        return [f"The original {entry['label'].lower()} is back."]
    det = next((d for d in scene.get("_detections", []) if d["id"] == obj["id"]), None)
    if obj["source"] == "detected" or (det is not None and obj.get("instance") == det["instance"]):
        if det is None:
            raise OperationError("The original of this object is not available.")
        parents = {r["subject"]: r["object"] for r in scene["relationships"] if r["type"] == "on"}
        fresh = _editable_object(det, parents.get(det["id"]))
        scene["objects"] = [fresh if o["id"] == obj["id"] else o for o in scene["objects"]]
        return []
    obj["transform"]["scale"] = {"x": 1.0, "y": 1.0, "z": 1.0}
    obj["transform"]["rotation"] = 0.0
    lib = get_library()
    item_id = (obj.get("library_item") or {}).get("id")
    if item_id in lib.items:
        item = lib.get(item_id)
        obj["appearance"] = {"color": item.color, "material": item.material}
    else:
        defaults = catalog.MODEL_DEFAULTS.get(obj["type"], {"material": "painted", "color": None})
        obj["appearance"] = {"color": defaults.get("color"), "material": defaults["material"]}
    return []


HANDLERS = {
    "update_object": op_update_object,
    "update_surface": op_update_surface,
    "transform_object": op_transform_object,
    "replace_object": op_replace_object,
    "fit_object": op_fit_object,
    "add_object": op_add_object,
    "remove_object": op_remove_object,
    "restore_object": op_restore_object,
    "reset_object": op_reset_object,
}
