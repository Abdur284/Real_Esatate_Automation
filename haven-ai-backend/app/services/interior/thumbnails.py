"""
Previews for the object library and the material swatches.

A preview is the item's actual model drawn by the same renderer the room
uses, in a small neutral "studio" (pale wall, floor, soft shadow) seen at a
three-quarter angle, so what the user picks is what appears in the room.
Previews are made on first request and cached on disk (keyed by the item's
data, so editing an item refreshes its picture) and in memory.
"""
import hashlib
import json
import os
import threading
from collections import OrderedDict
from typing import Dict, Optional

import cv2
import numpy as np

from app.core.config import settings
from . import geometry
from .camera import Camera
from .library import Item, Library
from .materials import texture
from .renderer import draw_model

THUMB_W, THUMB_H = 320, 240
SS = 2    # rendered at twice the size, then reduced, for smooth edges

_mem: "OrderedDict[str, bytes]" = OrderedDict()
_lock = threading.Lock()


def _studio(W: int, H: int, seam_y: float) -> np.ndarray:
    img = np.zeros((H, W, 3), np.float32)
    s = int(seam_y)
    wall = np.linspace(236, 222, max(1, s))[:, None, None] * np.array([1.0, 1.0, 1.02])
    img[:s] = wall
    floor = np.linspace(214, 196, max(1, H - s))[:, None, None] * np.array([0.93, 0.97, 1.0])
    img[s:] = floor
    return img


def _scene(W: int, H: int, cam: Camera, seam_y: float, obj: Dict) -> Dict:
    return {"image": {"width": W, "height": H}, "camera": cam.to_dict(),
            "layout": {"columns": [0.0, 1.0], "floor_y": [seam_y / H] * 2, "ceiling_y": [-1, -1]},
            "floor_rows": [[round(seam_y / H, 4), 0.0, 1.0], [1.0, 0.0, 1.0]], "surfaces": [], "objects": [obj]}


def render_preview(lib: Library, it: Item) -> np.ndarray:
    W, H = THUMB_W * SS, THUMB_H * SS
    cat = lib.categories[it.category]
    obj = lib.scene_object(it, "preview")
    Wm, Dm, Hm = it.dimensions["width"] / 100, it.dimensions["depth"] / 100, it.dimensions["height"] / 100

    placement = it.placement or cat.placement
    if placement == "wall":
        # a wall far enough away that the piece fills ~72% of the frame
        cam = Camera(W, H, horizon=0.5 * H, vx=W / 2, fov_deg=45, eye_height_m=1.4)
        z = max(0.3, cam.f * max(Wm / (0.72 * W), Hm / (0.72 * H)))
        cam.eye_height_m = 0.9 * H * z / cam.f          # puts the wall/floor seam at 1.4 x H (out of frame)
        seam = cam.row_at_depth(z)
        obj["transform"]["position"] = {"x": 0.5, "y": 0.5}
        obj["transform"]["wall_depth"] = z
        img = _studio(W, H, H)
        scene = _scene(W, H, cam, seam, obj)
    else:
        # everything else stands on the studio floor, turned a little; lights
        # that hang from the ceiling are shown hanging from their canopy
        flat = placement == "floor_flat"
        cam = Camera(W, H, horizon=0.4 * H, vx=W / 2, fov_deg=40,
                     eye_height_m=float(np.clip(Hm * 1.3 + 0.15, 0.4, 1.4)) if not flat else 1.4)
        obj["placement"] = "floor_flat" if flat else "floor"
        obj["transform"]["rotation"] = -12.0 if flat else (-28.0 if placement != "ceiling" else 0.0)
        z = max(0.6, cam.f * max(Wm, Hm, Dm) / (0.6 * W)) + Dm
        p = obj["transform"]["position"]
        p["x"] = 0.5
        p["y"] = cam.row_at_depth(z) / H
        for _ in range(5):
            pts = geometry._points(obj, _scene(W, H, cam, 0.3 * H, obj), cam)
            bw, bh = np.ptp(pts[:, 0]) / W, np.ptp(pts[:, 1]) / H
            z = float(np.clip(z * max(bw / 0.76, bh / 0.76), 0.3, 200.0))
            cx = (pts[:, 0].min() + pts[:, 0].max()) / 2 / W
            cy = (pts[:, 1].min() + pts[:, 1].max()) / 2 / H
            cam.horizon += (0.53 - cy) * H          # moving the horizon moves the whole picture
            p["x"] = float(p["x"] + (0.5 - cx))
            p["y"] = cam.row_at_depth(z) / H
        seam = cam.row_at_depth(z + Dm + 0.6)
        img = _studio(W, H, float(np.clip(seam, 0, H)))
        if placement == "ceiling":
            img[: int(H * 0.05)] = 212
        scene = _scene(W, H, cam, seam, obj)
    draw_model(img, obj, scene, cam, 1.0, np.ones(3, np.float32))
    return cv2.resize(np.clip(img, 0, 255).astype(np.uint8), (THUMB_W, THUMB_H), interpolation=cv2.INTER_AREA)


def _key(it: Item) -> str:
    return it.id + "-" + hashlib.sha1(json.dumps(it.raw, sort_keys=True).encode()).hexdigest()[:10]


def thumbnail_png(lib: Library, it: Item) -> bytes:
    key = _key(it)
    with _lock:
        if key in _mem:
            _mem.move_to_end(key)
            return _mem[key]
    folder = os.path.join(settings.INTERIOR_STORAGE_DIR, "thumbs")
    path = os.path.join(folder, f"{key}.png")
    data: Optional[bytes] = None
    if os.path.isfile(path):
        with open(path, "rb") as f:
            data = f.read()
    if data is None:
        ok, buf = cv2.imencode(".png", render_preview(lib, it))
        data = buf.tobytes()
        os.makedirs(folder, exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    with _lock:
        _mem[key] = data
        while len(_mem) > 256:
            _mem.popitem(last=False)
    return data


def swatch_png(material: str, color: Optional[str] = None, size: int = 96) -> bytes:
    """A square sample of a material (about 0.6 m across)."""
    uu, vv = np.meshgrid(np.linspace(0, 0.6, size), np.linspace(0, 0.6, size))
    tex = texture(material, uu, vv, color)
    shade = np.linspace(1.04, 0.92, size)[:, None, None]
    ok, buf = cv2.imencode(".png", np.clip(tex * shade, 0, 255).astype(np.uint8))
    return buf.tobytes()


_warming = threading.Event()


def warm_up(lib: Library) -> None:
    """Renders every missing preview once, in the background, the first time
    the library is opened, so browsing never waits on a cold picture."""
    if _warming.is_set():
        return
    _warming.set()

    def run():
        for it in list(lib.items.values()):
            try:
                thumbnail_png(lib, it)
            except Exception:       # a broken item must not stop the others
                continue
    threading.Thread(target=run, name="interior-thumbnails", daemon=True).start()


def item_etag(it: Item) -> str:
    return '"' + _key(it) + '"'


