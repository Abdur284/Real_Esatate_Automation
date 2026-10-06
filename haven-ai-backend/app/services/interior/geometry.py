"""
Layer 2: where every object is right now.

Objects keep their transform in the scene (normalised position, scale,
rotation, flip); this module turns that into pixels for the renderer and
into the current bounds/outline the editor draws, and enforces the spatial
rules: floor pieces stay on the floor (and shrink as they move away), wall
pieces stay on the wall, ceiling pieces slide along the ceiling.

Photo objects (cut out of the photo) move as 2D layers with perspective
scaling; model objects (added or swapped-in 3D furniture) are projected from
the floor plane through the camera, so they can turn about their own axis.
"""
import math
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from . import catalog
from .camera import Camera
from .furniture3d import BASE_DIMS, WALL_GENERATORS, build_parts, part_faces

SCALE_MIN, SCALE_MAX = 0.3, 3.0
MIN_MODEL_DEPTH_M = 0.8
DEFAULT_CEILING_M = 2.6


def size(scene: Dict) -> Tuple[int, int]:
    return scene["image"]["width"], scene["image"]["height"]


def camera(scene: Dict) -> Camera:
    W, H = size(scene)
    return Camera.from_dict(scene["camera"], W, H)


def _interp(scene: Dict, key: str, x_px: float) -> float:
    W, H = size(scene)
    lay = scene["layout"]
    return float(np.interp(x_px / W, lay["columns"], lay[key])) * H


def seam_row(scene: Dict, x_px: float) -> float:
    """Row where the floor meets the wall at this column."""
    return _interp(scene, "floor_y", x_px)


def ceiling_row(scene: Dict, x_px: float) -> float:
    W, H = size(scene)
    lay = scene["layout"]
    vals = [v for v in lay["ceiling_y"]]
    if all(v < 0 for v in vals):
        return 0.0
    cols = [c for c, v in zip(lay["columns"], vals) if v >= 0]
    return float(np.interp(x_px / W, cols, [v for v in vals if v >= 0])) * H


def wall_depth(scene: Dict, cam: Camera, x_px: float) -> float:
    return cam.depth_at_row(seam_row(scene, x_px))


# ---- photo objects -------------------------------------------------------

def perspective_factor(obj: Dict, cam: Camera, H: int) -> Tuple[float, float]:
    """How much bigger a floor object looks at its new spot than where it
    was photographed (1/distance); rugs also foreshorten in depth."""
    if obj["placement"] not in ("floor", "floor_flat"):
        return 1.0, 1.0
    y0 = obj["original"]["anchor"]["y"] * H - cam.horizon
    y1 = obj["transform"]["position"]["y"] * H - cam.horizon
    if y0 <= 1 or y1 <= 1:
        return 1.0, 1.0
    k = y1 / y0
    return (k, k * k) if obj["placement"] == "floor_flat" else (k, k)


def photo_matrix(obj: Dict, cam: Camera, W: int, H: int) -> np.ndarray:
    """2x3 affine: pixel in the original photo -> pixel now."""
    t = obj["transform"]
    kx, ky = perspective_factor(obj, cam, H)
    sx = t["scale"]["x"] * kx * (-1 if t.get("flip") else 1)
    sy = t["scale"]["y"] * ky
    ax, ay = obj["original"]["anchor"]["x"] * W, obj["original"]["anchor"]["y"] * H
    px, py = t["position"]["x"] * W, t["position"]["y"] * H
    th = math.radians(t.get("rotation", 0.0) if catalog.rotate_mode(obj["type"], "detected") == "tilt" else 0.0)
    c, s = math.cos(th), math.sin(th)
    # Only wall pieces tilt, and their anchor is their centre.
    A = np.array([[c * sx, -s * sy], [s * sx, c * sy]])
    return np.hstack([A, (np.array([px, py]) - A @ np.array([ax, ay]))[:, None]])


def is_displaced(obj: Dict) -> bool:
    """True when the object's original pixels are no longer where they were."""
    if obj["source"] != "detected":
        return True
    t, o = obj["transform"], obj["original"]["anchor"]
    return (abs(t["position"]["x"] - o["x"]) > 1e-4 or abs(t["position"]["y"] - o["y"]) > 1e-4
            or abs(t["scale"]["x"] - 1) > 1e-4 or abs(t["scale"]["y"] - 1) > 1e-4
            or bool(t.get("flip")) or abs(t.get("rotation", 0.0)) > 1e-3)


# ---- model objects -------------------------------------------------------

def model_dims(obj: Dict) -> Tuple[float, float, float]:
    m = obj["model"]
    s = obj["transform"]["scale"]
    return m["width_m"] * s["x"], m["depth_m"] * s.get("z", 1.0), m["height_m"] * s["y"]


def model_spec(obj: Dict) -> Tuple[str, Dict]:
    """(generator, parameters) of a model object. Objects created before the
    library existed have only a type, which is also a generator name."""
    m = obj.get("model") or {}
    return m.get("generator") or obj["type"], m.get("params") or {}


def is_wall_item(obj: Dict) -> bool:
    return obj["source"] == "model" and model_spec(obj)[0] in WALL_GENERATORS


def is_mesh_item(obj: Dict) -> bool:
    """A real 3D model (glTF asset) rather than a parametric one."""
    return obj["source"] == "model" and (obj.get("model") or {}).get("kind") == "mesh"


def is_image_item(obj: Dict) -> bool:
    """A 2D asset (cut-out picture) rather than a parametric model."""
    return obj["source"] == "model" and (obj.get("model") or {}).get("kind") == "image"


def image_quad(obj: Dict, cam: Camera, scene: Dict) -> np.ndarray:
    """Corners of a 2D asset standing upright, facing the camera, at real size
    (on the wall for wall pieces)."""
    if obj["placement"] == "wall":
        return wall_panel(obj, cam, scene)
    W, H = size(scene)
    Wm, Dm, Hm = model_dims(obj)
    X0, Z0, _, base = model_world(obj, cam, W, H)
    z = max(0.3, Z0 - Dm / 2) if obj["placement"] in ("floor", "floor_flat") else Z0
    return np.array([cam.project(X0 - Wm / 2, base + Hm, z), cam.project(X0 + Wm / 2, base + Hm, z),
                     cam.project(X0 + Wm / 2, base, z), cam.project(X0 - Wm / 2, base, z)])


def ceiling_height(scene: Dict, cam: Camera) -> float:
    """Ceiling height (m) measured where both the ceiling line and the
    wall/floor seam are known in the same column; else a typical 2.6 m."""
    lay = scene["layout"]
    W, H = size(scene)
    vals = []
    for c, fy, cy in zip(lay["columns"], lay["floor_y"], lay["ceiling_y"]):
        if cy is None or cy < 0:
            continue
        z = cam.depth_at_row(fy * H)
        vals.append(cam.eye_height_m + (cam.horizon - cy * H) * z / cam.f)
    if not vals:
        return max(DEFAULT_CEILING_M, cam.eye_height_m + 0.6)
    return float(np.clip(np.median(vals), max(2.1, cam.eye_height_m + 0.4), 4.5))


def model_world(obj: Dict, cam: Camera, W: int, H: int) -> Tuple[float, float, float, float]:
    """(X, Z, yaw radians, base height) of the model's centre.

    floor   : position = front-centre point where it meets the floor
    ceiling : position = where it hangs from the ceiling plane
    surface : position = the middle of its base, resting on something whose
              distance was worked out when it was placed (support_depth)"""
    t = obj["transform"]
    p = t["position"]
    px, py = p["x"] * W, p["y"] * H
    yaw = math.radians(t.get("rotation", 0.0))
    _, D, Hm = model_dims(obj)
    placement = obj["placement"]
    if placement == "ceiling":
        hc = t.get("ceiling_m") or DEFAULT_CEILING_M
        rise = max(0.3, hc - cam.eye_height_m)
        z = float(np.clip(cam.f * rise / max(2.0, cam.horizon - py), MIN_MODEL_DEPTH_M, 20.0))
        return (px - cam.vx) * z / cam.f, z, yaw, hc - Hm
    if placement == "wall":
        # position = the centre of the piece on the wall; it hangs with its back on the wall
        zw = float(t.get("wall_depth") or 3.0)
        yc = cam.eye_height_m - (py - cam.horizon) * zw / cam.f
        return (px - cam.vx) * zw / cam.f, zw - D / 2 - 0.004, 0.0, yc - Hm / 2
    if placement == "surface":
        z = float(t.get("support_depth") or 2.5)
        base = max(0.0, cam.eye_height_m - (py - cam.horizon) * z / cam.f)
        return (px - cam.vx) * z / cam.f, z, yaw, base
    Xf, Zf = cam.floor_point(px, py)
    # centre is half a depth behind the front point, along the model's axis
    return Xf + math.sin(yaw) * D / 2, Zf + math.cos(yaw) * D / 2, yaw, 0.0


def model_faces(obj: Dict, cam: Camera, W: int, H: int) -> List[Dict]:
    """Visible faces projected to the image, far to near."""
    dims = model_dims(obj)
    X0, Z0, yaw, base = model_world(obj, cam, W, H)
    c, s = math.cos(yaw), math.sin(yaw)
    faces = []
    generator, params = model_spec(obj)
    for part in build_parts(generator, dims, params):
        if part["shape"] == "foliage":
            fx, fy, fz = part["c"]
            fy += base
            wx, wz = X0 + fx * c + fz * s, Z0 - fx * s + fz * c
            if wz < 0.1:
                continue
            px, py = cam.project(wx, fy, wz)
            rpx = part["r"] * cam.f / wz
            ang = np.linspace(0, 2 * np.pi, 16, endpoint=False)
            pts = np.stack([px + rpx * np.cos(ang), py + rpx * np.sin(ang)], 1)
            dist = math.sqrt(wx ** 2 + (cam.eye_height_m - fy) ** 2 + wz ** 2) - part["r"] * 0.3
            faces.append({"pts": pts, "local": [], "normal": (0.0, 0.0, -1.0), "role": part["role"], "dist": dist,
                          "center": (px, py), "radius": rpx, "seed": part["seed"], "foliage": True})
            continue
        for verts, n in part_faces(part):
            world = [(X0 + x * c + z * s, y + base, Z0 - x * s + z * c) for x, y, z in verts]
            nw = (n[0] * c + n[2] * s, n[1], -n[0] * s + n[2] * c)
            cen = np.mean(world, axis=0)
            # camera at (0, eye, 0); the face is visible if it points at it
            to_cam = (-cen[0], cam.eye_height_m - cen[1], -cen[2])
            if nw[0] * to_cam[0] + nw[1] * to_cam[1] + nw[2] * to_cam[2] <= 0:
                continue
            if min(p[2] for p in world) < 0.05:
                continue
            pts = np.array([cam.project(X, y, Z) for X, y, Z in world], dtype=np.float64)
            dist = math.sqrt(cen[0] ** 2 + (cam.eye_height_m - cen[1]) ** 2 + cen[2] ** 2)
            faces.append({"pts": pts, "local": verts, "normal": nw, "role": part["role"], "dist": dist})
    faces.sort(key=lambda f: -f["dist"])
    return faces


def mesh_world(obj: Dict, mesh, cam: Camera, W: int, H: int) -> Tuple[np.ndarray, np.ndarray]:
    """World positions (x right, y up, z away) and normals of a 3D asset's
    vertices, scaled to the object's current size. Floor, ceiling and
    surface pieces turn about the vertical axis; wall pieces turn in the
    wall's plane."""
    Wm, Dm, Hm = model_dims(obj)
    w0, d0, h0 = mesh.dims
    sc = np.array([Wm / max(w0, 1e-6), Hm / max(h0, 1e-6), Dm / max(d0, 1e-6)], np.float32)
    P = mesh.positions * sc
    N = mesh.normals / sc
    X0, Z0, yaw, base = model_world(obj, cam, W, H)
    if obj["placement"] == "wall":
        roll = math.radians(obj["transform"].get("rotation", 0.0))
        c, s = math.cos(roll), math.sin(roll)
        R = np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], np.float32)
        P = (P - [0, Hm / 2, 0]) @ R.T + [0, Hm / 2, 0]
        N = N @ R.T
    else:
        c, s = math.cos(yaw), math.sin(yaw)
        R = np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]], np.float32)
        P = P @ R.T
        N = N @ R.T
    P = P + np.array([X0, base, Z0], np.float32)
    N = N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-9)
    return P.astype(np.float32), N.astype(np.float32)


def project_points(P: np.ndarray, cam: Camera) -> np.ndarray:
    z = np.maximum(P[:, 2], 1e-3)
    return np.stack([cam.vx + cam.f * P[:, 0] / z, cam.horizon + cam.f * (cam.eye_height_m - P[:, 1]) / z], 1)


def _mesh_points(obj: Dict, cam: Camera, W: int, H: int) -> Optional[np.ndarray]:
    from . import meshes
    m = obj["model"]
    try:
        mesh = meshes.load(m["asset"], "1k", m.get("yaw", 0.0), textures=False)
    except (FileNotFoundError, ValueError):
        return None
    P, _ = mesh_world(obj, mesh, cam, W, H)
    P = P[P[:, 2] > 0.05]
    if not len(P):
        return None
    # every vertex counts (a thin leg is a few vertices); the hull keeps it light
    return cv2.convexHull(project_points(P, cam).astype(np.float32))[:, 0].astype(np.float64)


def model_footprint(obj: Dict, cam: Camera, W: int, H: int) -> Tuple[np.ndarray, float]:
    """Projected floor footprint polygon and the depth of its nearest corner."""
    Wm, Dm, _ = model_dims(obj)
    X0, Z0, yaw, base = model_world(obj, cam, W, H)
    c, s = math.cos(yaw), math.sin(yaw)
    corners = [(X0 + x * c + z * s, Z0 - x * s + z * c)
               for x, z in ((-Wm / 2, -Dm / 2), (Wm / 2, -Dm / 2), (Wm / 2, Dm / 2), (-Wm / 2, Dm / 2))]
    pts = np.array([cam.project(X, base, Z) for X, Z in corners])
    return pts, min(Z for _, Z in corners)


def model_back_depth(obj: Dict, cam: Camera, W: int, H: int) -> float:
    Wm, Dm, _ = model_dims(obj)
    X0, Z0, yaw, _ = model_world(obj, cam, W, H)
    c, s = math.cos(yaw), math.sin(yaw)
    return max(Z0 - x * s + z * c for x in (-Wm / 2, Wm / 2) for z in (-Dm / 2, Dm / 2))


def spot_against_wall(obj: Dict, scene: Dict) -> Tuple[float, float]:
    """Normalised front-centre position that puts a new floor piece in the
    middle of the room with its back near the far wall."""
    W, H = size(scene)
    cam = camera(scene)
    rows = scene.get("floor_rows") or []
    x = 0.5
    if rows:
        near_seam = rows[: max(1, len(rows) // 4)]
        x = float(np.mean([(r[1] + r[2]) / 2 for r in near_seam]))
    _, Dm, _ = model_dims(obj)
    z_front = max(1.2, wall_depth(scene, cam, x * W) - 0.15 - Dm)
    y = min(0.97, cam.row_at_depth(z_front) / H)
    return x, y


# ---- where a new floor piece goes ---------------------------------------------

SEATING = {"sofa", "sectional_sofa", "armchair", "recliner", "bed", "bench"}
IN_FRONT_OF_SEATING = {"coffee_table", "ottoman"}
BESIDE_SEATING = {"side_table", "floor_lamp", "plant", "bedside_table", "table_lamp"}


def floor_footprints(scene: Dict, cam: Camera, exclude: str = "") -> List[Dict]:
    """Rough floor rectangles (metres: x0, x1, z0 near, z1 far) of the pieces
    standing on the floor, from the models' real sizes or, for photographed
    pieces, from where they meet the floor and how wide they look."""
    W, H = size(scene)
    out = []
    for o in scene["objects"]:
        if o["id"] == exclude or o["placement"] != "floor" or not o.get("bounds"):
            continue
        if o["source"] == "model":
            Wm, Dm, _ = model_dims(o)
            X0, Z0, yaw, _ = model_world(o, cam, W, H)
            c, s_ = abs(math.cos(yaw)), abs(math.sin(yaw))
            hw, hd = (Wm * c + Dm * s_) / 2, (Wm * s_ + Dm * c) / 2
            out.append({"obj": o, "x0": X0 - hw, "x1": X0 + hw, "z0": Z0 - hd, "z1": Z0 + hd})
        else:
            b = o["bounds"]
            bottom = (b["y"] + b["h"]) * H
            if bottom <= cam.horizon + 2:
                continue
            z = cam.depth_at_row(bottom)
            xa, xb = (b["x"] * W - cam.vx) * z / cam.f, ((b["x"] + b["w"]) * W - cam.vx) * z / cam.f
            depth = float(np.clip(0.8 * (xb - xa), 0.4, 1.0))
            out.append({"obj": o, "x0": xa, "x1": xb, "z0": z, "z1": z + depth})
    return out


def companion_spot(obj: Dict, scene: Dict) -> Optional[Tuple[float, float]]:
    """Where a designer would put this piece relative to the room's main
    seating: a coffee table or ottoman in front of the sofa (a 45 cm walkway),
    a side table, lamp or plant beside it. None when the rule does not apply
    or every such spot collides with something."""
    if obj["source"] != "model" or obj["placement"] != "floor":
        return None
    kind = obj["type"]
    if kind not in IN_FRONT_OF_SEATING and kind not in BESIDE_SEATING:
        return None
    W, H = size(scene)
    cam = camera(scene)
    feet = floor_footprints(scene, cam, obj["id"])
    seats = [f for f in feet if f["obj"]["type"] in SEATING]
    if not seats:
        return None
    main = max(seats, key=lambda f: f["x1"] - f["x0"])
    Wm, Dm, _ = model_dims(obj)
    cx = (main["x0"] + main["x1"]) / 2
    cands = []
    if kind in IN_FRONT_OF_SEATING:
        for gap in (0.45, 0.35, 0.6, 0.75):
            cands.append((cx, main["z0"] - gap - Dm / 2))
    else:
        zc = min(main["z1"] - Dm / 2 - 0.02, (main["z0"] + main["z1"]) / 2)
        for side in (1, -1):
            edge = main["x1"] if side > 0 else main["x0"]
            for gap in (0.08, 0.2):
                cands.append((edge + side * (gap + Wm / 2), zc))
    for Xc, Zc in cands:
        zf = Zc - Dm / 2
        if zf < MIN_MODEL_DEPTH_M:
            continue
        if Zc + Dm / 2 > wall_depth(scene, cam, float(cam.vx + cam.f * Xc / max(Zc, 0.1))) + 0.05:
            continue
        clash = any(Xc + Wm / 2 > f["x0"] - 0.05 and Xc - Wm / 2 < f["x1"] + 0.05 and
                    Zc + Dm / 2 > f["z0"] - 0.05 and Zc - Dm / 2 < f["z1"] + 0.05 for f in feet)
        if clash:
            continue
        px, py = cam.vx + cam.f * Xc / zf, cam.row_at_depth(zf)
        if not (0.02 * W <= px <= 0.98 * W and py <= H):
            continue
        return round(float(px / W), 4), round(float(min(py / H, 1.0)), 4)
    return None


def free_spot(obj: Dict, scene: Dict) -> Tuple[float, float]:
    """A spot for a new piece: next to the seating where a designer would put
    it (companion_spot), else where it overlaps the existing furniture as
    little as possible: on the floor from the far wall forwards, or on the wall."""
    spot = companion_spot(obj, scene)
    if spot is not None:
        return spot
    W, H = size(scene)
    others = [o["bounds"] for o in scene["objects"]
              if o["id"] != obj["id"] and o.get("bounds") and o["placement"] != "floor_flat"]

    def overlap(b):
        area = 0.0
        for q in others:
            ix = max(0.0, min(b[2], q["x"] + q["w"]) - max(b[0], q["x"]))
            iy = max(0.0, min(b[3], q["y"] + q["h"]) - max(b[1], q["y"]))
            area += ix * iy
        outside = (max(0.0, -b[0]) + max(0.0, b[2] - 1) + max(0.0, -b[1]) + max(0.0, b[3] - 1))
        return area / max(1e-6, (b[2] - b[0]) * (b[3] - b[1])) + outside * 4

    cam = camera(scene)
    if obj["placement"] == "ceiling":
        # hang it near the top of the picture: the nearest part of the ceiling in view
        top = max(0.03, min(0.12, cam.horizon / H - 0.08))
        cands = [(x, y) for y in np.linspace(0.02, top, 3) for x in np.linspace(0.2, 0.8, 7)]
        base = (0.5, 0.02)
    elif obj["placement"] == "surface":
        tops = [o for o in scene["objects"] if o["id"] != obj["id"] and o.get("bounds")
                and o["type"] in SURFACE_HOSTS]
        cands = [(o["bounds"]["x"] + o["bounds"]["w"] * fx, o["bounds"]["y"] + o["bounds"]["h"] * 0.08)
                 for o in tops for fx in (0.25, 0.5, 0.75)] or [(0.5, 0.6)]
        base = cands[0]
    elif obj["placement"] == "wall":
        walls = sorted((s for s in scene["surfaces"] if s["type"] == "wall"), key=lambda s: -s["area"])
        wb = walls[0]["bbox"] if walls else {"x": 0.1, "y": 0.05, "w": 0.8, "h": 0.5}
        cands = [(wb["x"] + wb["w"] * fx, wb["y"] + wb["h"] * fy)
                 for fy in (0.3, 0.2, 0.4) for fx in np.linspace(0.2, 0.8, 7)]
        base = (wb["x"] + wb["w"] / 2, wb["y"] + wb["h"] * 0.3)
    else:
        sx, sy = spot_against_wall(obj, scene)
        cands = [(x, y) for y in np.linspace(sy, 0.97, 6) for x in np.linspace(0.1, 0.9, 17)]
        base = (sx, sy)
    best, best_score = base, float("inf")
    for x, y in cands:
        trial = dict(obj, transform=dict(obj["transform"], position={"x": float(x), "y": float(y)}))
        settle(trial, scene)
        pts = _points(trial, scene, cam)
        box = (pts[:, 0].min() / W, pts[:, 1].min() / H, pts[:, 0].max() / W, pts[:, 1].max() / H)
        score = overlap(box) + 0.15 * abs(x - base[0]) + 0.3 * abs(y - base[1])
        if score < best_score - 1e-9:
            best, best_score = (float(x), float(y)), score
    return best


def wall_panel(obj: Dict, cam: Camera, scene: Dict) -> np.ndarray:
    """Corners (4x2 px) of a flat wall piece: real size at the wall's distance."""
    W, H = size(scene)
    p = obj["transform"]["position"]
    cx, cy = p["x"] * W, p["y"] * H
    Wm, _, Hm = model_dims(obj)
    mpp = wall_depth(scene, cam, cx) / cam.f
    w, h = Wm / mpp, Hm / mpp
    th = math.radians(obj["transform"].get("rotation", 0.0))
    c, s = math.cos(th), math.sin(th)
    return np.array([(cx + x * c - y * s, cy + x * s + y * c)
                     for x, y in ((-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2))])


# ---- current state for the editor ------------------------------------------

def _points(obj: Dict, scene: Dict, cam: Camera) -> np.ndarray:
    W, H = size(scene)
    if obj["source"] == "detected":
        M = photo_matrix(obj, cam, W, H)
        pts = np.array([[x * W, y * H] for x, y in obj["original"]["outline"]] or [[0, 0]], dtype=np.float64)
        return pts @ M[:, :2].T + M[:, 2]
    if is_image_item(obj):
        return image_quad(obj, cam, scene)
    if is_wall_item(obj):
        return wall_panel(obj, cam, scene)
    if is_mesh_item(obj):
        pts = _mesh_points(obj, cam, W, H)
        return pts if pts is not None else model_footprint(obj, cam, W, H)[0]
    faces = model_faces(obj, cam, W, H)
    if not faces:
        return model_footprint(obj, cam, W, H)[0]
    return np.vstack([f["pts"] for f in faces])


def depth_of(obj: Dict, scene: Dict, cam: Camera, by_id: Dict[str, Dict]) -> float:
    """Sort key: larger = further away = drawn first."""
    W, H = size(scene)
    p = obj["transform"]["position"]
    if obj["placement"] == "floor_flat":
        return 1000.0 + cam.depth_at_row(p["y"] * H)
    if obj["placement"] == "floor":
        # compare pieces by the middle of their footprint: a photo object's
        # anchor is its front edge, so add a typical half depth
        if obj["source"] == "model":
            return model_world(obj, cam, W, H)[1]
        return cam.depth_at_row(p["y"] * H) + 0.3
    if obj["source"] == "model" and obj["placement"] == "ceiling":
        return model_world(obj, cam, W, H)[1]
    if obj["source"] == "model" and obj["placement"] == "surface":
        return model_world(obj, cam, W, H)[1] - 0.05
    if obj["placement"] in ("wall", "ceiling", "fixed"):
        b = obj["bounds"]
        return wall_depth(scene, cam, (b["x"] + b["w"] / 2) * W) + 0.05
    parent = obj.get("parent")
    if parent and parent in by_id:
        return by_id[parent].get("depth", 5.0) - 0.01
    bottom = (obj["bounds"]["y"] + obj["bounds"]["h"]) * H
    return cam.depth_at_row(bottom) if bottom > cam.horizon + 2 else wall_depth(scene, cam, p["x"] * W)


def refresh(scene: Dict) -> None:
    """Recomputes each object's current bounds, outline, size and draw depth."""
    W, H = size(scene)
    cam = camera(scene)
    for obj in scene["objects"]:
        pts = _points(obj, scene, cam)
        x0, y0 = pts.min(0)
        x1, y1 = pts.max(0)
        obj["bounds"] = {"x": round(float(x0) / W, 4), "y": round(float(y0) / H, 4),
                         "w": round(float(x1 - x0) / W, 4), "h": round(float(y1 - y0) / H, 4)}
        if obj["source"] == "detected":
            obj["outline"] = [[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in pts]
        else:
            hull = cv2.convexHull(pts.astype(np.float32))[:, 0]
            obj["outline"] = [[round(float(x) / W, 4), round(float(y) / H, 4)] for x, y in hull]
        obj["dimensions_m"] = current_dimensions(obj, scene, cam)
    by_id = {o["id"]: o for o in scene["objects"]}
    for obj in sorted(scene["objects"], key=lambda o: 0 if o.get("parent") is None else 1):
        obj["depth"] = round(float(depth_of(obj, scene, cam, by_id)), 3)


def current_dimensions(obj: Dict, scene: Dict, cam: Camera) -> Optional[Dict]:
    if obj["source"] == "model":
        Wm, Dm, Hm = model_dims(obj)
        return {"width": round(Wm, 2), "depth": round(Dm, 2), "height": round(Hm, 2), "source": "model"}
    orig = obj["original"].get("dimensions_m")
    if not orig:
        return None
    s = obj["transform"]["scale"]
    out = {"width": round(orig["width"] * s["x"], 2), "source": "estimated"}
    if "height" in orig:
        out["height"] = round(orig["height"] * s["y"], 2)
    if obj["placement"] == "floor":
        # a single photo does not show depth: the typical depth-to-width ratio of the category
        from .library import get_library
        lib = get_library()
        cat = lib.category_for_type(obj["type"], obj["placement"])
        if cat in lib.by_category:
            d = lib.default_item(cat).dimensions
            out["depth"] = round(out["width"] * min(1.2, d["depth"] / max(d["width"], 1)), 2)
            out["depth_source"] = "typical"
    return out


# ---- constraints -----------------------------------------------------------

def clamp_position(obj: Dict, x: float, y: float, scene: Dict) -> Tuple[float, float, Optional[str]]:
    """Nearest allowed position (normalised) and a note when it was moved."""
    W, H = size(scene)
    cam = camera(scene)
    placement = obj["placement"]
    note = None
    x = min(1.0, max(0.0, x))
    y = min(1.0, max(0.0, y))
    if placement in ("floor", "floor_flat"):
        rows = scene.get("floor_rows") or []
        min_y = max(cam.horizon / H + 0.02, rows[0][0] if rows else 0.0)
        if y < min_y:
            y, note = min_y, "It was kept on the floor."
        if rows:
            band = min(rows, key=lambda r: abs(r[0] - y))
            if not band[1] <= x <= band[2]:
                x = min(band[2], max(band[1], x))
                note = "It was kept inside the room."
        if obj["source"] == "model" and placement == "floor":
            # the whole piece stays in front of the camera and in front of the wall
            for _ in range(40):
                obj_try = dict(obj, transform=dict(obj["transform"], position={"x": x, "y": y}))
                pts, near = model_footprint(obj_try, cam, W, H)
                back = model_back_depth(obj_try, cam, W, H)
                wall = wall_depth(scene, cam, float(np.clip(pts[:, 0].mean(), 0, W - 1)))
                if near < MIN_MODEL_DEPTH_M and y > min_y:
                    y, note = max(min_y, y - 0.01), "It was moved back so it stays in the room."
                elif back > wall + 0.05 and y < 1.0:
                    y, note = min(1.0, y + 0.01), "It was kept in front of the wall."
                else:
                    break
    elif placement == "wall":
        half_h = obj["bounds"]["h"] / 2 if obj.get("bounds") else 0.0
        seam = seam_row(scene, x * W) / H
        top = max(0.0, ceiling_row(scene, x * W) / H)
        hi = seam - half_h
        lo = top + half_h
        if hi > lo and not lo <= y <= hi:
            y, note = min(hi, max(lo, y)), "It was kept on the wall."
    elif placement == "ceiling":
        if obj["source"] == "detected":
            y = obj["original"]["anchor"]["y"]
        elif y > cam.horizon / H - 0.03:
            y, note = max(0.0, cam.horizon / H - 0.03), "It was kept on the ceiling."
    return round(x, 4), round(y, 4), note


# What small things can stand on.
SURFACE_HOSTS = {"table", "coffee_table", "side_table", "dining_table", "console_table", "bedside_table", "desk",
                 "cabinet", "sideboard", "tv_unit", "chest_of_drawers", "dresser", "dressing_table", "bookshelf",
                 "shelf", "counter", "kitchen_island"}


def _support_depth(obj: Dict, scene: Dict, cam: Camera) -> float:
    """Distance of whatever the object's base rests on: the nearest piece of
    furniture under that point, else the floor there, else the wall."""
    W, H = size(scene)
    p = obj["transform"]["position"]
    px, py = p["x"] * W, p["y"] * H
    best = None
    for o in scene["objects"]:
        b = o.get("bounds")
        if o["id"] == obj["id"] or not b or o.get("parent") == obj["id"] or o["placement"] in ("ceiling", "surface"):
            continue
        if b["x"] <= p["x"] <= b["x"] + b["w"] and b["y"] - 0.02 <= p["y"] <= b["y"] + b["h"]:
            if o["source"] == "model" and o["placement"] == "floor":
                d = model_world(o, cam, W, H)[1]
            elif o["placement"] in ("floor", "fixed"):
                d = cam.depth_at_row((o["transform"]["position"]["y"] if o["placement"] == "floor"
                                      else b["y"] + b["h"]) * H) + 0.25
            else:
                d = wall_depth(scene, cam, px) - 0.2
            if best is None or d < best:
                best = d
    if best is not None:
        return float(best)
    if py > seam_row(scene, px):
        return cam.depth_at_row(py)
    return max(0.8, wall_depth(scene, cam, px) - 0.2)


def settle(obj: Dict, scene: Dict) -> None:
    """Records what a model hangs from or rests on at its current position."""
    if obj["source"] != "model":
        return
    cam = camera(scene)
    if obj["placement"] == "ceiling":
        obj["transform"]["ceiling_m"] = round(ceiling_height(scene, cam), 3)
    elif obj["placement"] == "surface":
        obj["transform"]["support_depth"] = round(_support_depth(obj, scene, cam), 3)
    elif obj["placement"] == "wall":
        x = obj["transform"]["position"]["x"] * size(scene)[0]
        obj["transform"]["wall_depth"] = round(wall_depth(scene, cam, x), 3)


def check_scale(obj: Dict, scale: Dict[str, float], scene: Dict) -> List[str]:
    """Raises ValueError outside hard limits; returns warnings for unusual sizes."""
    for k, v in scale.items():
        if not (isinstance(v, (int, float)) and math.isfinite(v)):
            raise ValueError(f"Scale '{k}' must be a number.")
        if not SCALE_MIN <= v <= SCALE_MAX:
            raise ValueError(f"Scale must be between {SCALE_MIN} and {SCALE_MAX} (got {v:g}).")
    rng = catalog.type_info(obj["type"]).get("width_m")
    warnings = []
    if rng:
        if obj["source"] == "model":
            width = obj["model"]["width_m"] * scale.get("x", 1.0)
        else:
            dims = obj["original"].get("dimensions_m") or {}
            width = dims.get("width", 0) * scale.get("x", 1.0) if dims.get("width") else None
        if width is not None and not rng[0] <= width <= rng[1]:
            warnings.append(f"A {obj['label'].lower()} {width:.1f} m wide is unusual "
                            f"(typically {rng[0]:g}-{rng[1]:g} m).")
    return warnings


def default_model(type_: str) -> Dict[str, float]:
    W, D, Hh = BASE_DIMS[type_]
    return {"width_m": W, "depth_m": D, "height_m": Hh, "generator": type_, "params": {}}
