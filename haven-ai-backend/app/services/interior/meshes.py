"""
Real-world 3D models (glTF 2.0) for the object library.

The models are photoscanned / artist-made reproductions of real furniture
and decor with physically based materials (Poly Haven, CC0), stored under
INTERIOR_ASSET_DIR/models/<asset>/<quality>/ by scripts/fetch_interior_assets.py.

A loaded Mesh is normalised to the renderer's object frame: metres, +y up,
x centred, z centred, the lowest point at y = 0 and the front facing -z
(towards the camera at yaw 0). Its real size is therefore simply its
bounding box, which the library uses as the item's dimensions.

Quality levels: "1k" textures for interactive editing (standard), "2k" for
the final render (high quality) when it has been downloaded; previews are
the library thumbnails rendered from the standard asset.
"""
import json
import math
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
QUALITIES = ("1k", "2k")
_COMPONENTS = {5120: np.int8, 5121: np.uint8, 5122: np.int16, 5123: np.uint16, 5125: np.uint32, 5126: np.float32}
_WIDTH = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}


def asset_root() -> str:
    d = settings.INTERIOR_ASSET_DIR
    return d if os.path.isabs(d) else os.path.join(BACKEND_ROOT, d)


def model_dir(asset: str, quality: str = "1k") -> str:
    return os.path.join(asset_root(), "models", asset, quality)


def gltf_path(asset: str, quality: str = "1k") -> Optional[str]:
    """The .gltf file of an asset at a quality level, falling back to the
    standard level when the high-quality files were not downloaded."""
    if not asset or any(c in asset for c in "/\\.") or asset.startswith("_"):
        return None
    for q in ((quality, "1k") if quality != "1k" else ("1k",)):
        p = os.path.join(model_dir(asset, q), f"{asset}.gltf")
        if os.path.isfile(p):
            return p
    return None


def available(asset: str) -> bool:
    return gltf_path(asset) is not None


@dataclass
class MeshMaterial:
    name: str
    base_factor: np.ndarray                    # RGBA linear multipliers
    base: Optional[np.ndarray] = None          # sRGB colour texture, float32 0..1, RGB(A)
    normal: Optional[np.ndarray] = None        # tangent-space normal map, float32 -1..1
    mr: Optional[np.ndarray] = None            # G roughness, B metallic, float32 0..1
    occlusion: Optional[np.ndarray] = None     # R ambient occlusion, float32 0..1
    rough: float = 1.0
    metal: float = 1.0
    alpha_mode: str = "OPAQUE"
    alpha_cutoff: float = 0.5
    double_sided: bool = False
    emissive: Tuple[float, float, float] = (0.0, 0.0, 0.0)


@dataclass
class Mesh:
    asset: str
    quality: str
    positions: np.ndarray                      # (V, 3) float32, object frame (see module doc)
    normals: np.ndarray                        # (V, 3) float32
    uvs: np.ndarray                            # (V, 2) float32
    tris: np.ndarray                           # (T, 3) int32
    tri_mat: np.ndarray                        # (T,) int16 index into materials
    materials: List[MeshMaterial] = field(default_factory=list)

    @property
    def dims(self) -> Tuple[float, float, float]:
        """(width, depth, height) in metres."""
        span = self.positions.max(0) - self.positions.min(0)
        return float(span[0]), float(span[2]), float(span[1])


# ---- glTF -------------------------------------------------------------------

def _node_matrix(node: Dict) -> np.ndarray:
    if "matrix" in node:
        return np.array(node["matrix"], np.float64).reshape(4, 4).T
    T = np.eye(4)
    T[:3, 3] = node.get("translation", [0, 0, 0])
    x, y, z, w = node.get("rotation", [0, 0, 0, 1])
    R = np.eye(4)
    R[:3, :3] = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                 [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                 [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    S = np.diag(list(node.get("scale", [1, 1, 1])) + [1])
    return T @ R @ S


class _Gltf:
    def __init__(self, path: str):
        self.path = path
        self.dir = os.path.dirname(path)
        with open(path, encoding="utf-8") as f:
            self.doc = json.load(f)
        self._buffers: Dict[int, bytes] = {}

    def _safe(self, uri: str) -> str:
        p = os.path.normpath(os.path.join(self.dir, uri.replace("%20", " ")))
        if not p.startswith(os.path.normpath(self.dir)):
            raise ValueError(f"asset file outside its folder: {uri}")
        return p

    def buffer(self, i: int) -> bytes:
        if i not in self._buffers:
            with open(self._safe(self.doc["buffers"][i]["uri"]), "rb") as f:
                self._buffers[i] = f.read()
        return self._buffers[i]

    def accessor(self, i: int) -> np.ndarray:
        acc = self.doc["accessors"][i]
        dtype = np.dtype(_COMPONENTS[acc["componentType"]])
        width = _WIDTH[acc["type"]]
        count = acc["count"]
        if "bufferView" not in acc:
            return np.zeros((count, width), np.float32)
        view = self.doc["bufferViews"][acc["bufferView"]]
        data = self.buffer(view["buffer"])
        start = view.get("byteOffset", 0) + acc.get("byteOffset", 0)
        stride = view.get("byteStride") or dtype.itemsize * width
        arr = np.ndarray((count, width), dtype, buffer=data, offset=start,
                         strides=(stride, dtype.itemsize)).copy()
        if acc.get("normalized") and dtype != np.float32:
            return arr.astype(np.float32) / float(np.iinfo(dtype).max)
        return arr

    def image(self, tex_index: Optional[int], mode=cv2.IMREAD_UNCHANGED) -> Optional[np.ndarray]:
        if tex_index is None:
            return None
        tex = self.doc["textures"][tex_index]
        src = tex.get("source")
        if src is None:
            return None
        uri = self.doc["images"][src].get("uri")
        if not uri:
            return None
        img = cv2.imread(self._safe(uri), mode)
        if img is None:
            return None
        if img.ndim == 2:
            img = img[..., None]
        if img.shape[2] == 1:                 # grey -> RGB
            img = np.repeat(img, 3, axis=2)
        elif img.shape[2] == 2:               # grey + alpha -> RGBA
            img = np.dstack([img[..., :1]] * 3 + [img[..., 1:]])
        # BGR(A) -> RGB(A)
        if img.shape[2] >= 3:
            img = img[..., [2, 1, 0] + ([3] if img.shape[2] == 4 else [])]
        return img.astype(np.float32) / (65535.0 if img.dtype == np.uint16 else 255.0)

    def world_primitives(self):
        """(primitive, world matrix) for every mesh primitive in the default scene."""
        doc = self.doc
        if doc.get("scenes"):
            scene = doc["scenes"][doc.get("scene", 0)]
        else:
            scene = {"nodes": list(range(len(doc.get("nodes", []))))}
        out = []

        def visit(i, parent):
            node = doc["nodes"][i]
            M = parent @ _node_matrix(node)
            if "mesh" in node:
                for prim in doc["meshes"][node["mesh"]]["primitives"]:
                    out.append((prim, M))
            for c in node.get("children", []):
                visit(c, M)
        for n in scene.get("nodes", []):
            visit(n, np.eye(4))
        return out


def _material(g: _Gltf, i: Optional[int], textures: bool) -> MeshMaterial:
    if i is None:
        return MeshMaterial("default", np.ones(4, np.float32), rough=0.8, metal=0.0)
    m = g.doc["materials"][i]
    pbr = m.get("pbrMetallicRoughness", {})
    mat = MeshMaterial(
        name=m.get("name", f"material_{i}"),
        base_factor=np.array(pbr.get("baseColorFactor", [1, 1, 1, 1]), np.float32),
        rough=float(pbr.get("roughnessFactor", 1.0)), metal=float(pbr.get("metallicFactor", 1.0)),
        alpha_mode=m.get("alphaMode", "OPAQUE"), alpha_cutoff=float(m.get("alphaCutoff", 0.5)),
        double_sided=bool(m.get("doubleSided", False)),
        emissive=tuple(m.get("emissiveFactor", [0, 0, 0])))
    if textures:
        mat.base = g.image(pbr.get("baseColorTexture", {}).get("index"))
        nrm = g.image((m.get("normalTexture") or {}).get("index"), cv2.IMREAD_COLOR)
        if nrm is not None:
            mat.normal = nrm[..., :3] * 2.0 - 1.0
        mat.mr = g.image(pbr.get("metallicRoughnessTexture", {}).get("index"), cv2.IMREAD_COLOR)
        mat.occlusion = g.image((m.get("occlusionTexture") or {}).get("index"), cv2.IMREAD_COLOR)
    return mat


def _vertex_normals(pos: np.ndarray, tris: np.ndarray) -> np.ndarray:
    fn = np.cross(pos[tris[:, 1]] - pos[tris[:, 0]], pos[tris[:, 2]] - pos[tris[:, 0]])
    n = np.zeros_like(pos)
    for k in range(3):
        np.add.at(n, tris[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def load_gltf(path: str, asset: str = "", quality: str = "1k", textures: bool = True,
              yaw_deg: float = 0.0) -> Mesh:
    g = _Gltf(path)
    P, N, UV, T, TM = [], [], [], [], []
    mats: List[MeshMaterial] = []
    mat_index: Dict[Optional[int], int] = {}
    offset = 0
    for prim, M in g.world_primitives():
        if prim.get("mode", 4) != 4 or "POSITION" not in prim["attributes"]:
            continue
        a = prim["attributes"]
        pos = g.accessor(a["POSITION"]).astype(np.float64)
        n = len(pos)
        idx = (g.accessor(prim["indices"]).reshape(-1).astype(np.int64) if "indices" in prim
               else np.arange(n, dtype=np.int64))
        tris = idx[: len(idx) // 3 * 3].reshape(-1, 3)
        world = pos @ M[:3, :3].T + M[:3, 3]
        if "NORMAL" in a:
            nrm = g.accessor(a["NORMAL"]).astype(np.float64) @ np.linalg.inv(M[:3, :3])
            nrm /= np.maximum(np.linalg.norm(nrm, axis=1, keepdims=True), 1e-12)
        else:
            nrm = _vertex_normals(world, tris)
        uv = g.accessor(a["TEXCOORD_0"]) if "TEXCOORD_0" in a else np.zeros((n, 2), np.float32)
        if np.linalg.det(M[:3, :3]) < 0:              # mirrored node: keep the winding outward
            tris = tris[:, ::-1]
        key = prim.get("material")
        if key not in mat_index:
            mat_index[key] = len(mats)
            mats.append(_material(g, key, textures))
        P.append(world)
        N.append(nrm)
        UV.append(uv[:, :2])
        T.append(tris + offset)
        TM.append(np.full(len(tris), mat_index[key], np.int16))
        offset += n
    if not P:
        raise ValueError(f"{path} contains no triangle meshes")
    pos = np.vstack(P)
    nrm = np.vstack(N)
    # glTF: +y up, front +z  ->  object frame: front -z (turn half way round), plus any per-asset fix
    a = math.radians(180.0 + yaw_deg)
    c, s = math.cos(a), math.sin(a)
    R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    pos = pos @ R.T
    nrm = nrm @ R.T
    lo, hi = pos.min(0), pos.max(0)
    pos -= [(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2]
    return Mesh(asset=asset, quality=quality, positions=pos.astype(np.float32), normals=nrm.astype(np.float32),
                uvs=np.vstack(UV).astype(np.float32), tris=np.vstack(T).astype(np.int32),
                tri_mat=np.concatenate(TM), materials=mats)


# ---- cache --------------------------------------------------------------------

_cache: "OrderedDict[tuple, Mesh]" = OrderedDict()
_lock = threading.Lock()
_CACHE_SIZE = 10


def load(asset: str, quality: str = "1k", yaw_deg: float = 0.0, textures: bool = True) -> Mesh:
    path = gltf_path(asset, quality)
    if path is None:
        raise FileNotFoundError(f"3D asset '{asset}' is not installed; run scripts/fetch_interior_assets.py")
    real_q = os.path.basename(os.path.dirname(path))
    key = (asset, real_q, float(yaw_deg), textures)
    with _lock:
        if key in _cache:
            _cache.move_to_end(key)
            return _cache[key]
    mesh = load_gltf(path, asset, real_q, textures, yaw_deg)
    k = _unit_fix(asset, mesh.dims)
    if k != 1.0:
        mesh.positions *= k
    with _lock:
        _cache[key] = mesh
        while len(_cache) > _CACHE_SIZE:
            _cache.popitem(last=False)
    return mesh


def _published_mm(asset: str) -> Optional[List[float]]:
    try:
        with open(os.path.join(asset_root(), "models", asset, "info.json"), encoding="utf-8") as f:
            dims = json.load(f).get("dimensions_mm")
        return [float(d) for d in dims] if dims and len(dims) == 3 else None
    except (OSError, ValueError):
        return None


def _unit_fix(asset: str, dims: Tuple[float, float, float]) -> float:
    """A few source files are authored in the wrong unit (e.g. 10x too big);
    the publisher's measured size tells which, so the model is shown at its
    real size."""
    pub = _published_mm(asset)
    if not pub:
        return 1.0
    ratio = max(pub) / 1000.0 / max(max(dims), 1e-6)
    return ratio if not 0.7 <= ratio <= 1.4 else 1.0


def asset_info(asset: str, yaw_deg: float = 0.0) -> Dict:
    """Real size (metres), typical colour and material names of an installed
    asset; cached next to the files so the library starts quickly."""
    path = gltf_path(asset)
    if path is None:
        raise FileNotFoundError(asset)
    cache = os.path.join(asset_root(), "models", asset, "index.json")
    stamp = f"{os.path.getmtime(path):.0f}-{yaw_deg:g}-2"
    try:
        with open(cache, encoding="utf-8") as f:
            data = json.load(f)
        if data.get("stamp") == stamp:
            return data
    except (OSError, ValueError):
        pass
    mesh = load(asset, "1k", yaw_deg, textures=True)
    counts = np.bincount(mesh.tri_mat, minlength=len(mesh.materials))
    main = mesh.materials[int(np.argmax(counts))]
    if main.base is not None:
        rgb = main.base[..., :3].reshape(-1, 3)
        if main.base.shape[2] == 4:
            rgb = rgb[main.base[..., 3].reshape(-1) > 0.5] if (main.base[..., 3] > 0.5).any() else rgb
        c = np.median(rgb, 0) * main.base_factor[:3]
    else:
        c = main.base_factor[:3]
    w, d, h = mesh.dims
    data = {"stamp": stamp, "width_m": round(w, 3), "depth_m": round(d, 3), "height_m": round(h, 3),
            "color": "#%02x%02x%02x" % tuple(int(round(float(np.clip(v, 0, 1)) * 255)) for v in c),
            "materials": [m.name for m in mesh.materials], "triangles": int(len(mesh.tris))}
    try:
        with open(cache, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=1)
    except OSError:
        pass
    return data
