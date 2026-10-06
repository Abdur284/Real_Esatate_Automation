"""
Layer 2, final stage: structured 3D model -> binary glTF (GLB).

Input is the renderer-independent model produced by model_builder.py or
from_plan2d.py (walls with openings, slabs, roof, stairs, rooms, balconies,
all in plan feet). Output is a standard GLB 2.0 file that any glTF viewer,
Blender or the React Three Fiber page can load. No dependency beyond the
standard library: every piece of the building is an axis-aligned box, so the
mesh is written directly.

Scene graph (names are stable so the viewer can toggle layers):

    house                         extras.haven: units, axes, plot, totals
      site                        plot ground, boundary, road strip
      storey_<L>                  extras: level, label, elevation_ft
        L<L>_floors               one child node per room (extras: kind=room)
        L<L>_slab | _walls | _doors | _windows | _stairs | _furniture | _balconies
      roof_<L>                    roof pieces sitting on top of storey L

Coordinates: see arch_defaults.py (glTF X = plan x, Y = up, Z = -plan y, metres).
"""
import json
import struct
from typing import Any, Dict, List, Optional, Tuple

from .arch_defaults import FT_TO_M, STOREY_PITCH_FT, WALL_HEIGHT_FT
from .furniture import furnish_model

# ── Materials: key -> (display name, sRGB hex, alpha, roughness, metallic) ──
BASE_MATERIALS: Dict[str, Tuple[str, str, float, float, float]] = {
    "wall": ("wall", "#f1f5f9", 1.0, 0.92, 0.0),
    "parapet": ("parapet", "#e2e8f0", 1.0, 0.92, 0.0),
    "slab": ("slab", "#94a3b8", 1.0, 0.95, 0.0),
    "roof": ("roof", "#b0b8c4", 1.0, 0.9, 0.0),
    "stairs": ("stairs", "#d6bda2", 1.0, 0.8, 0.0),
    "glass": ("glass", "#9cc7e0", 0.42, 0.05, 0.1),
    "door": ("door", "#8b5e34", 1.0, 0.6, 0.0),
    "frame": ("frame", "#475569", 1.0, 0.5, 0.3),
    "railing": ("railing", "#cbd5e1", 1.0, 0.6, 0.2),
    "ground": ("ground", "#6b8f5e", 1.0, 1.0, 0.0),
    "road": ("road", "#475569", 1.0, 0.95, 0.0),
    "boundary": ("boundary", "#ffffff", 1.0, 1.0, 0.0),
    # Furniture (indicative)
    "fabric": ("furniture_fabric", "#f1f5f9", 1.0, 0.95, 0.0),
    "accent": ("furniture_accent", "#6d8fb3", 1.0, 0.9, 0.0),
    "wood": ("furniture_wood", "#a47148", 1.0, 0.65, 0.0),
    "upholstery": ("furniture_upholstery", "#64748b", 1.0, 0.95, 0.0),
    "cabinet": ("furniture_cabinet", "#e7e5e4", 1.0, 0.7, 0.0),
    "stone": ("furniture_stone", "#57534e", 1.0, 0.35, 0.0),
    "sanitary": ("furniture_sanitary", "#fafafa", 1.0, 0.25, 0.0),
}

# Floor finish per room type (matches the 2D plan legend's hues, muted).
FLOOR_COLORS = {
    "bedroom": "#86efac", "bathroom": "#c4b5fd", "kitchen": "#93c5fd",
    "drawing_room": "#fca5a5", "tv_lounge": "#fdba74", "family_hall": "#fcd34d",
    "store_room": "#d1d5db", "stairs": "#fde68a", "parking": "#cbd5e1",
    "corridor": "#e5e7eb", "terrace": "#a7f3d0", "dining_room": "#a5f3fc",
    "study": "#fbcfe8", "prayer_room": "#f5d0fe", "courtyard": "#6ee7b7", "lawn": "#4ade80",
}
DEFAULT_FLOOR = "#e5e7eb"

GLASS_THICKNESS_FT = 0.08
DOOR_LEAF_FT = 0.15
FRAME_FT = 0.22
ROAD_WIDTH_FT = 12.0

Box = Tuple[float, float, float, float, float, float]  # plan: x0, y0, h0, x1, y1, h1


def _srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _hex_rgb(hex_color: str) -> Optional[Tuple[float, float, float]]:
    h = str(hex_color or "").lstrip("#")
    if len(h) != 6:
        return None
    try:
        return tuple(_srgb_to_linear(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    except ValueError:
        return None


class _Mesh:
    """Triangle soup for one primitive, in glTF metres."""

    def __init__(self, mode: int = 4):
        self.mode = mode
        self.pos: List[float] = []
        self.nrm: List[float] = []
        self.uv: List[float] = []
        self.idx: List[int] = []

    @property
    def vertex_count(self) -> int:
        return len(self.pos) // 3

    def add_box(self, b: Box) -> None:
        """Axis-aligned box given in plan feet."""
        x0, y0, h0, x1, y1, h1 = b
        if x1 - x0 <= 1e-6 or y1 - y0 <= 1e-6 or h1 - h0 <= 1e-6:
            return
        lo = (x0 * FT_TO_M, h0 * FT_TO_M, -y1 * FT_TO_M)
        hi = (x1 * FT_TO_M, h1 * FT_TO_M, -y0 * FT_TO_M)
        c = [(lo[i] + hi[i]) / 2 for i in range(3)]
        half = [(hi[i] - lo[i]) / 2 for i in range(3)]
        for axis in range(3):
            a, b2 = (axis + 1) % 3, (axis + 2) % 3
            for sign in (1, -1):
                # u x v must equal the face normal for counter-clockwise winding.
                u, v = (a, b2) if sign > 0 else (b2, a)
                base = self.vertex_count
                for s, t in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    p = list(c)
                    p[axis] += sign * half[axis]
                    p[u] += s * half[u]
                    p[v] += t * half[v]
                    self.pos += p
                    n = [0.0, 0.0, 0.0]
                    n[axis] = float(sign)
                    self.nrm += n
                    # UVs in feet: vertical faces tile by (horizontal, height),
                    # horizontal faces by (x, z), so textures keep true scale.
                    if axis == 1:
                        self.uv += [p[0] / FT_TO_M, p[2] / FT_TO_M]
                    else:
                        self.uv += [(p[2] if axis == 0 else p[0]) / FT_TO_M, p[1] / FT_TO_M]
                self.idx += [base, base + 1, base + 2, base, base + 2, base + 3]

    def add_quad_up(self, x0: float, y0: float, x1: float, y1: float, h: float) -> None:
        """Horizontal rectangle facing up (+Y), in plan feet."""
        base = self.vertex_count
        for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1)):
            self.pos += [x * FT_TO_M, h * FT_TO_M, -y * FT_TO_M]
            self.nrm += [0.0, 1.0, 0.0]
            self.uv += [x, -y]
        # (x0,y0)->(x1,y0)->(x1,y1) is counter-clockwise seen from above in glTF.
        self.idx += [base, base + 1, base + 2, base, base + 2, base + 3]

    def add_line(self, p: Tuple[float, float, float], q: Tuple[float, float, float]) -> None:
        base = self.vertex_count
        for x, y, h in (p, q):
            self.pos += [x * FT_TO_M, h * FT_TO_M, -y * FT_TO_M]
        self.idx += [base, base + 1]


class GlbWriter:
    def __init__(self):
        self.bin = bytearray()
        self.gltf: Dict[str, Any] = {
            "asset": {"version": "2.0", "generator": "HAVEN AI 3D Design"},
            "scene": 0, "scenes": [{"name": "HavenHouse", "nodes": []}],
            "nodes": [], "meshes": [], "materials": [], "accessors": [], "bufferViews": [],
            "buffers": [{"byteLength": 0}],
        }
        self._materials: Dict[str, int] = {}
        self.triangles = 0

    # ── materials ──
    def material(self, key: str, name: str, color: str, alpha: float = 1.0,
                 roughness: float = 0.9, metallic: float = 0.0, extras: Optional[Dict] = None) -> int:
        if key in self._materials:
            return self._materials[key]
        rgb = _hex_rgb(color) or _hex_rgb(DEFAULT_FLOOR)
        mat: Dict[str, Any] = {
            "name": name,
            "pbrMetallicRoughness": {"baseColorFactor": [*rgb, alpha],
                                     "roughnessFactor": roughness, "metallicFactor": metallic},
        }
        if alpha < 1.0:
            mat["alphaMode"] = "BLEND"
            mat["doubleSided"] = True
        if extras:
            mat["extras"] = extras
        self.gltf["materials"].append(mat)
        self._materials[key] = len(self.gltf["materials"]) - 1
        return self._materials[key]

    # ── binary data ──
    def _view(self, data: bytes, target: Optional[int]) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        view = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target:
            view["target"] = target
        self.bin += data
        self.gltf["bufferViews"].append(view)
        return len(self.gltf["bufferViews"]) - 1

    def _accessor(self, values: List[float], comp: int, type_: str, target: int,
                  with_bounds: bool = False) -> int:
        size = {"SCALAR": 1, "VEC2": 2, "VEC3": 3}[type_]
        fmt = {5126: "f", 5123: "H", 5125: "I"}[comp]
        view = self._view(struct.pack(f"<{len(values)}{fmt}", *values), target)
        acc: Dict[str, Any] = {"bufferView": view, "componentType": comp,
                               "count": len(values) // size, "type": type_}
        if with_bounds:
            acc["min"] = [min(values[i::size]) for i in range(size)]
            acc["max"] = [max(values[i::size]) for i in range(size)]
        self.gltf["accessors"].append(acc)
        return len(self.gltf["accessors"]) - 1

    def mesh(self, name: str, parts: List[Tuple[_Mesh, int]]) -> Optional[int]:
        prims = []
        for m, material in parts:
            if not m.idx:
                continue
            attrs = {"POSITION": self._accessor(m.pos, 5126, "VEC3", 34962, with_bounds=True)}
            if m.mode == 4:
                attrs["NORMAL"] = self._accessor(m.nrm, 5126, "VEC3", 34962)
                attrs["TEXCOORD_0"] = self._accessor(m.uv, 5126, "VEC2", 34962)
                self.triangles += len(m.idx) // 3
            comp = 5123 if m.vertex_count <= 65535 else 5125
            prims.append({"attributes": attrs, "indices": self._accessor(m.idx, comp, "SCALAR", 34963),
                          "material": material, "mode": m.mode})
        if not prims:
            return None
        self.gltf["meshes"].append({"name": name, "primitives": prims})
        return len(self.gltf["meshes"]) - 1

    def node(self, name: str, mesh: Optional[int] = None, children: Optional[List[int]] = None,
             extras: Optional[Dict] = None) -> int:
        n: Dict[str, Any] = {"name": name}
        if mesh is not None:
            n["mesh"] = mesh
        if children:
            n["children"] = children
        if extras:
            n["extras"] = extras
        self.gltf["nodes"].append(n)
        return len(self.gltf["nodes"]) - 1

    def to_bytes(self, root: int) -> bytes:
        self.gltf["scenes"][0]["nodes"] = [root]
        while len(self.bin) % 4:
            self.bin.append(0)
        self.gltf["buffers"][0]["byteLength"] = len(self.bin)
        js = json.dumps(self.gltf, separators=(",", ":")).encode("utf-8")
        js += b" " * ((4 - len(js) % 4) % 4)
        total = 12 + 8 + len(js) + 8 + len(self.bin)
        return (struct.pack("<III", 0x46546C67, 2, total)
                + struct.pack("<II", len(js), 0x4E4F534A) + js
                + struct.pack("<II", len(self.bin), 0x004E4942) + bytes(self.bin))


class _Layer:
    """Collects boxes per material for one named layer node."""

    def __init__(self, writer: GlbWriter):
        self.w = writer
        self.parts: Dict[int, _Mesh] = {}

    def box(self, material: int, b: Box) -> None:
        self.parts.setdefault(material, _Mesh()).add_box(b)

    def build(self, name: str, extras: Dict) -> Optional[int]:
        mesh = self.w.mesh(name, [(m, mat) for mat, m in self.parts.items()])
        return None if mesh is None else self.w.node(name, mesh=mesh, extras=extras)


def _materials(w: GlbWriter, appearance: Optional[Dict]) -> Dict[str, int]:
    mats = {k: w.material(k, *v) for k, v in BASE_MATERIALS.items()}
    mats["facade"] = mats["wall"]
    if appearance:
        def flat(key, color, base):
            name, _, alpha, rough, metal = BASE_MATERIALS[base]
            return w.material(key, name, color or BASE_MATERIALS[base][1], alpha, rough, metal)
        mats["wall"] = flat("app_wall", appearance.get("walls"), "wall")
        mats["parapet"] = flat("app_trim", appearance.get("trim"), "parapet")
        mats["railing"] = mats["parapet"]
        mats["roof"] = flat("app_roof", appearance.get("roof"), "roof")
        mats["door"] = flat("app_door", appearance.get("door"), "door")
        mats["frame"] = flat("app_frame", appearance.get("window_frames"), "frame")
        cladding = appearance.get("cladding") if appearance.get("cladding") not in (None, "none") else None
        # The viewer tiles a procedural cladding texture over this material
        # using the feet-based UVs (see extras); the colour is the base tint.
        mats["facade"] = w.material("app_facade", "facade", appearance.get("facade") or "#f1f5f9", 1.0, 0.9, 0.0,
                                    extras={"cladding": cladding, "tint": appearance.get("facade")})
    return mats


def _add_wall(layers: Dict[str, _Layer], mats: Dict[str, int], wall: Dict, elevation: float,
              ox: float, oy: float, facade: bool) -> None:
    """Port of the original viewer's wall builder: solid runs between openings,
    sill and lintel around each one, a glass pane or door leaf in the hole."""
    horizontal = abs(wall["y1"] - wall["y2"]) < 1e-6
    length = abs(wall["x2"] - wall["x1"]) if horizontal else abs(wall["y2"] - wall["y1"])
    start = (min(wall["x1"], wall["x2"]) + ox) if horizontal else (min(wall["y1"], wall["y2"]) + oy)
    fixed = (wall["y1"] + oy) if horizontal else (wall["x1"] + ox)
    t, height = wall["thickness"], wall["height"]
    wall_mat = mats["parapet"] if wall.get("parapet") else mats["facade"] if facade else mats["wall"]

    def box(layer: str, material: int, off: float, along: float, bottom: float, h: float, depth: float) -> None:
        if along <= 1e-6 or h <= 1e-6:
            return
        a0, a1 = start + off, start + off + along
        c0, c1 = fixed - depth / 2, fixed + depth / 2
        h0, h1 = elevation + bottom, elevation + bottom + h
        b = (a0, c0, h0, a1, c1, h1) if horizontal else (c0, a0, h0, c1, a1, h1)
        layers[layer].box(material, b)

    cursor = 0.0
    for op in sorted(wall.get("openings") or [], key=lambda o: o["center"]):
        o0 = max(op["center"] - op["width"] / 2, cursor)
        o1 = min(op["center"] + op["width"] / 2, length)
        if o1 <= o0:
            continue
        ow, sill = o1 - o0, op["sill"]
        top = min(sill + op["height"], height)
        box("walls", wall_mat, cursor, o0 - cursor, 0, height, t)
        if sill > 0:
            box("walls", wall_mat, o0, ow, 0, sill, t)
        if top < height:
            box("walls", wall_mat, o0, ow, top, height - top, t)
        fd = t + 0.1  # frames stand slightly proud of both wall faces
        if op["type"] == "window":
            box("windows", mats["glass"], o0, ow, sill, top - sill, GLASS_THICKNESS_FT)
            box("windows", mats["frame"], o0, ow, top - FRAME_FT, FRAME_FT, fd)
            box("windows", mats["frame"], o0, ow, sill, FRAME_FT, fd)
            box("windows", mats["frame"], o0, FRAME_FT, sill, top - sill, fd)
            box("windows", mats["frame"], o1 - FRAME_FT, FRAME_FT, sill, top - sill, fd)
            if ow > 3.2:
                box("windows", mats["frame"], o0 + ow / 2 - 0.08, 0.16, sill, top - sill, fd * 0.6)
        else:
            box("doors", mats["frame"], o0, FRAME_FT, 0, top, fd)
            box("doors", mats["frame"], o1 - FRAME_FT, FRAME_FT, 0, top, fd)
            box("doors", mats["frame"], o0, ow, top - FRAME_FT, FRAME_FT, fd)
            box("doors", mats["door"], o0 + FRAME_FT, ow - 2 * FRAME_FT, 0.02, top - FRAME_FT - 0.02, DOOR_LEAF_FT)
        cursor = o1
    box("walls", wall_mat, cursor, length - cursor, 0, height, t)


def _add_stairs(layer: _Layer, mat: int, s: Dict, ox: float, oy: float) -> None:
    steps = max(int(s["steps"]), 1)
    rise, run = s["total_rise"] / steps, s["depth"] / steps
    for i in range(steps):
        y0 = s["y"] + oy + run * i
        layer.box(mat, (s["x"] + ox, y0, s["base_elevation"], s["x"] + ox + s["width"], y0 + run,
                        s["base_elevation"] + rise * (i + 1)))


def _add_balcony(layer: _Layer, mats: Dict[str, int], b: Dict, ox: float, oy: float) -> None:
    bx, by, top = b["x"] + ox, b["y"] + oy, b["elevation"]
    w, d, st, rh, t = b["width"], b["depth"], b["slab_thickness"], b["railing_height"], 0.15
    layer.box(mats["parapet"], (bx, by, top - st, bx + w, by + d, top))
    panel = mats["glass"] if b.get("railing") == "glass" else mats["railing"]
    layer.box(panel, (bx, by, top, bx + w, by + t, top + rh))
    layer.box(panel, (bx, by, top, bx + t, by + d, top + rh))
    layer.box(panel, (bx + w - t, by, top, bx + w, by + d, top + rh))
    if b.get("railing") == "glass":
        layer.box(mats["railing"], (bx, by, top + rh - 0.075, bx + w, by + 0.2, top + rh + 0.075))


def _room_extras(room: Dict, level: int, ox: float, oy: float) -> Dict:
    extras = {
        "kind": "room", "id": str(room.get("id")), "label": str(room.get("label") or room.get("type")),
        "type": str(room.get("type")), "level": level,
        "x_ft": round(room["x"] + ox, 2), "y_ft": round(room["y"] + oy, 2),
        "width_ft": round(room["width"], 2), "depth_ft": round(room["depth"], 2),
        "area_sqft": round(room["width"] * room["depth"], 1),
        "enclosed": bool(room.get("enclosed", True)),
    }
    if room.get("group"):
        extras["group"] = str(room["group"])
    if isinstance(room.get("detection"), dict):
        extras["detection"] = room["detection"]
    return extras


def export_glb(model: Dict[str, Any], furniture: bool = True) -> Tuple[bytes, Dict[str, Any]]:
    """Returns (glb_bytes, metadata)."""
    w = GlbWriter()
    mats = _materials(w, model.get("appearance"))
    plot, fp, roof = model["plot"], model["footprint"], model["roof"]
    ox, oy = fp.get("origin_x_ft", 0.0), fp.get("origin_y_ft", 0.0)
    pw, pl = float(plot["width_ft"]), float(plot["length_ft"])
    storeys = model["storeys"]
    top_level = max((s["level"] for s in storeys), default=1)
    pieces = furnish_model(model) if furniture else {}

    # ── Site: plot ground, boundary line, and a road strip marking the front ──
    site = _Layer(w)
    site.box(mats["ground"], (0, 0, -0.3, pw, pl, -0.02))
    site.box(mats["road"], (-6, -ROAD_WIDTH_FT - 2, -0.3, pw + 6, -2, -0.05))
    boundary = _Mesh(mode=1)
    corners = [(0, 0), (pw, 0), (pw, pl), (0, pl)]
    for (x0, y0), (x1, y1) in zip(corners, corners[1:] + corners[:1]):
        boundary.add_line((x0, y0, 0.02), (x1, y1, 0.02))
    site_mesh = w.mesh("site", [(m, mat) for mat, m in site.parts.items()] + [(boundary, mats["boundary"])])
    children = [w.node("site", mesh=site_mesh, extras={"kind": "site"})]

    room_count = 0
    for storey in storeys:
        level, elev = storey["level"], storey["elevation_ft"]
        layers = {k: _Layer(w) for k in ("slab", "walls", "doors", "windows", "stairs", "furniture", "balconies")}
        for slab in storey.get("slabs") or [storey["slab"]]:
            layers["slab"].box(mats["slab"], (slab["x"] + ox, slab["y"] + oy, slab["elevation"] - slab["thickness"],
                                              slab["x"] + ox + slab["width"], slab["y"] + oy + slab["depth"],
                                              slab["elevation"]))
        for wall in storey["walls"]:
            facade = bool(model.get("appearance")) and wall["exterior"] \
                and abs(wall["y1"]) < 1e-6 and abs(wall["y2"]) < 1e-6
            _add_wall(layers, mats, wall, elev, ox, oy, facade)
        if storey.get("stairs"):
            _add_stairs(layers["stairs"], mats["stairs"], storey["stairs"], ox, oy)
        for b in model.get("balconies") or []:
            if b["level"] == level:
                _add_balcony(layers["balconies"], mats, b, ox, oy)
        for _, mat_key, box in pieces.get(level, []):
            layers["furniture"].box(mats[mat_key], box)

        # Room floors: one pickable node per room, just above the slab.
        room_nodes = []
        for room in storey["rooms"]:
            rtype = str(room.get("type"))
            mat = w.material(f"floor_{rtype}", f"floor_{rtype}", FLOOR_COLORS.get(rtype, DEFAULT_FLOOR), 1.0, 0.85)
            quad = _Mesh()
            inset = 0.1
            quad.add_quad_up(room["x"] + ox + inset, room["y"] + oy + inset,
                             room["x"] + ox + room["width"] - inset, room["y"] + oy + room["depth"] - inset,
                             elev + 0.03)
            name = f"room_{level}_{len(room_nodes) + 1}"
            room_nodes.append(w.node(name, mesh=w.mesh(name, [(quad, mat)]),
                                     extras=_room_extras(room, level, ox, oy)))
        room_count += len(room_nodes)

        kids = [w.node(f"L{level}_floors", children=room_nodes,
                       extras={"kind": "layer", "layer": "floors", "level": level})]
        for key, layer in layers.items():
            n = layer.build(f"L{level}_{key}", {"kind": "layer", "layer": key, "level": level})
            if n is not None:
                kids.append(n)
        children.append(w.node(f"storey_{level}", children=kids, extras={
            "kind": "storey", "level": level, "label": storey["label"], "elevation_ft": elev,
            "wall_height_ft": storey.get("wall_height_ft", WALL_HEIGHT_FT)}))

    # ── Roof, grouped by the storey it sits on ──
    roof_layers: Dict[int, _Layer] = {}
    if roof.get("pieces") is not None:
        for p in roof["pieces"]:
            level = max(1, min(top_level, round(p["elevation"] / STOREY_PITCH_FT)))
            roof_layers.setdefault(level, _Layer(w)).box(
                mats["roof"], (p["x"] + ox, p["y"] + oy, p["elevation"],
                               p["x"] + ox + p["width"], p["y"] + oy + p["depth"], p["elevation"] + roof["thickness"]))
    else:
        layer = roof_layers.setdefault(top_level, _Layer(w))
        x0, y0 = roof["x"] + ox, roof["y"] + oy
        x1, y1 = x0 + roof["width"], y0 + roof["depth"]
        e, rt = roof["elevation"], roof["thickness"]
        layer.box(mats["roof"], (x0, y0, e, x1, y1, e + rt))
        t, ph = roof["parapet_thickness"], roof["parapet_height"]
        for b in ((x0, y0, e + rt, x1, y0 + t, e + rt + ph), (x0, y1 - t, e + rt, x1, y1, e + rt + ph),
                  (x0, y0, e + rt, x0 + t, y1, e + rt + ph), (x1 - t, y0, e + rt, x1, y1, e + rt + ph)):
            layer.box(mats["parapet"], b)
    for level, layer in sorted(roof_layers.items()):
        n = layer.build(f"roof_{level}", {"kind": "roof", "level": level})
        if n is not None:
            children.append(n)

    metadata = {
        "schema": "haven-3d/1",
        "units": "m", "source_units": "ft", "ft_to_m": FT_TO_M,
        "axes": {"x": "plan x (left to right seen from the road)", "y": "up", "z": "-plan y (road at +z)"},
        "source": model.get("source", "generated"),
        "plot": {"width_ft": pw, "length_ft": pl},
        "footprint": {k: fp.get(k) for k in ("width_ft", "depth_ft", "origin_x_ft", "origin_y_ft")},
        "totals": model.get("totals", {}),
        "levels": [{"level": s["level"], "label": s["label"], "elevation_ft": s["elevation_ft"],
                    "wall_height_ft": s.get("wall_height_ft", WALL_HEIGHT_FT)} for s in storeys],
        "rooms": room_count,
        "furniture_pieces": sum(len(v) for v in pieces.values()),
        "furniture_indicative": True,
    }
    root = w.node("house", children=children, extras={"haven": metadata})
    data = w.to_bytes(root)
    metadata.update({"triangles": w.triangles, "nodes": len(w.gltf["nodes"]), "size_bytes": len(data)})
    return data, metadata


def read_glb(data: bytes) -> Tuple[Dict[str, Any], bytes]:
    """Parses a GLB into (json, bin). Used by tests and for sanity checks."""
    magic, version, length = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or length != len(data):
        raise ValueError("Not a valid GLB 2.0 file.")
    jlen, jtype = struct.unpack_from("<II", data, 12)
    if jtype != 0x4E4F534A:
        raise ValueError("GLB JSON chunk missing.")
    js = json.loads(data[20:20 + jlen].decode("utf-8"))
    off = 20 + jlen
    blen, btype = struct.unpack_from("<II", data, off)
    if btype != 0x004E4942:
        raise ValueError("GLB BIN chunk missing.")
    return js, data[off + 8: off + 8 + blen]
