"""
Interior Design module: orchestration.

    upload -> validate (image_input) -> segment (segmentation, Layer 1)
      -> build scene (scene_builder -> operations.initial_scene, Layer 2)
      -> store (store) -> editor edits via operations, undo/redo in store
      -> render (renderer) -> final image (PNG or JPEG download)
      -> save/load (designs, Firestore)

Only the upload runs the AI model. Edits change the scene JSON and re-render
from the original photo; the render for a scene version is cached.
"""
import json
import logging
import secrets
import threading
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from . import catalog, designs, operations
from .image_input import RoomImageRejected, load_room_photo
from .renderer import object_sprite, render
from .scene_builder import build_scene
from .segmentation import get_segmenter
from .store import store

logger = logging.getLogger(__name__)

_analysis_slots = threading.BoundedSemaphore(2)      # CPU-heavy; keep the server responsive
_render_lock = threading.Lock()
_renders: "OrderedDict[Tuple[str, int, int], bytes]" = OrderedDict()
MAX_RENDERS = 32


class NotARoom(RoomImageRejected):
    pass


# ---- responses -------------------------------------------------------------------

def public_scene(scene: Dict) -> Dict:
    out = {k: v for k, v in scene.items() if not k.startswith("_")}
    out["removed"] = [{k: r[k] for k in ("id", "label", "source")} for r in scene.get("removed", [])]
    return out


def scene_response(scene: Dict, st: Dict, notes: Optional[List[str]] = None) -> Dict:
    sid, v = scene["scene_id"], scene["version"]
    return {
        "scene": public_scene(scene),
        "can_undo": st["position"] > 0,
        "can_redo": st["position"] < len(st["stack"]) - 1,
        "notes": notes or [],
        "render_url": f"/api/interior/scenes/{sid}/render?v={v}",
        "original_url": f"/api/interior/scenes/{sid}/original",
    }


def _with_detections(scene: Dict) -> Dict:
    scene = dict(scene)
    scene["_detections"] = store.detections(scene["scene_id"])["objects"]
    return scene


# ---- analysis --------------------------------------------------------------------

def analyze_room(data: bytes, owner_uid: Optional[str]) -> Dict:
    """Upload -> scene. Raises RoomImageRejected / SegmentationUnavailable."""
    img, info = load_room_photo(data)
    segmenter = get_segmenter()
    with _analysis_slots:
        cls_map, conf = segmenter.segment(img)
        detections, instances, alphas = build_scene(img, cls_map, conf, segmenter.labels)
    cov = detections["coverage"]
    if cov["wall"] + cov["floor"] + cov["ceiling"] < 0.12 and len(detections["objects"]) < 2:
        raise NotARoom("This does not look like a photo of a room's interior. Upload a photo taken "
                       "inside the room, showing its walls and floor.", "not_a_room", 422)
    warnings = info["warnings"]
    if not detections["objects"]:
        warnings.append("No furniture was recognised in this photo. You can still change the walls and "
                        "floor and add furniture.")
    if not any(s["type"] == "floor" for s in detections["surfaces"]):
        warnings.append("The floor is not visible, so moving and adding floor furniture is limited.")
    if detections["people_seen"]:
        warnings.append("People in the photo are left unchanged; a photo of the empty room works best.")
    if detections["camera"]["source"].startswith("default"):
        warnings.append("The room's perspective could not be measured precisely; sizes and depth are "
                        "approximate.")
    scene_id = secrets.token_hex(16)
    scene = operations.initial_scene(scene_id, detections, info)
    store.cleanup(settings.INTERIOR_SCENE_TTL_HOURS)
    store.create(scene_id, img, instances, alphas, detections, scene, owner_uid)
    return scene_response(scene, store.state(scene_id))


# ---- editing -----------------------------------------------------------------------

def get_scene(scene_id: str, uid: Optional[str]) -> Dict:
    store.check_access(scene_id, uid)
    scene, st = store.current(scene_id)
    return scene_response(scene, st)


def apply(scene_id: str, uid: Optional[str], base_version: Optional[int], op: Dict) -> Dict:
    store.check_access(scene_id, uid)

    def make(scene):
        new, notes = operations.apply_operation(_with_detections(scene), op)
        new.pop("_detections", None)
        return new, notes

    new, st, notes = store.commit(scene_id, base_version, make)
    return scene_response(new, st, notes)


def undo(scene_id: str, uid: Optional[str]) -> Dict:
    store.check_access(scene_id, uid)
    return scene_response(*store.move(scene_id, -1))


def redo(scene_id: str, uid: Optional[str]) -> Dict:
    store.check_access(scene_id, uid)
    return scene_response(*store.move(scene_id, +1))


def reset(scene_id: str, uid: Optional[str]) -> Dict:
    store.check_access(scene_id, uid)
    return scene_response(*store.reset(scene_id))


# ---- rendering ---------------------------------------------------------------------

def _encode_jpeg(img: np.ndarray, quality: int = 90) -> bytes:
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    return buf.tobytes()


def render_image(scene: Dict, quality: str = "2k") -> np.ndarray:
    """The rendered scene as a BGR array (no encoding, for lossless output)."""
    return render(_with_detections(scene), store.assets(scene["scene_id"]), quality)


def render_scene(scene: Dict, width: int = 0, quality: str = "1k") -> bytes:
    """JPEG of a scene version. quality "2k" = the final render: high-quality
    3D assets and finer anti-aliasing."""
    key = (scene["scene_id"], scene["version"], width, quality)
    with _render_lock:
        if key in _renders:
            _renders.move_to_end(key)
            return _renders[key]
    img = render(_with_detections(scene), store.assets(scene["scene_id"]), quality)
    if width and width < img.shape[1]:
        img = cv2.resize(img, (width, round(img.shape[0] * width / img.shape[1])), interpolation=cv2.INTER_AREA)
    data = _encode_jpeg(img, 95 if quality != "1k" else 90)
    with _render_lock:
        _renders[key] = data
        while len(_renders) > MAX_RENDERS:
            _renders.popitem(last=False)
    return data


def render_version(scene_id: str, uid: Optional[str], version: Optional[int], width: int = 0) -> bytes:
    """The requested version if it is still in the history, else the current one."""
    store.check_access(scene_id, uid)
    scene, st = store.current(scene_id)
    if version is not None and version != scene["version"] and version in st["stack"]:
        scene = store._read(scene_id, f"history/{version}.json")
    return render_scene(scene, width)


def original_image(scene_id: str, uid: Optional[str]) -> bytes:
    store.check_access(scene_id, uid)
    data = store.get_file(scene_id, "original.jpg")
    if data is None:
        raise KeyError(scene_id)
    return data


def sprite(scene_id: str, uid: Optional[str], object_id: str) -> Optional[Tuple[bytes, Dict]]:
    store.check_access(scene_id, uid)
    scene, _ = store.current(scene_id)
    out = object_sprite(_with_detections(scene), store.assets(scene_id), object_id)
    if out is None:
        return None
    img, bounds = out
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes(), bounds


JPEG_QUALITY = {"high": 95, "standard": 85}


def _final_bytes(scene: Dict, fmt: str, quality: str) -> bytes:
    img = render_image(scene, "2k")
    if fmt == "png":
        ok, buf = cv2.imencode(".png", img, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        if not ok:
            raise RuntimeError("PNG encoding failed")
        return buf.tobytes()
    return _encode_jpeg(img, JPEG_QUALITY[quality])


async def final_render(scene_id: str, uid: Optional[str], fmt: str = "jpg", quality: str = "high") -> Dict:
    """The final image of the current design, rendered from the scene with
    the high-quality assets: PNG (lossless) or JPEG (high = 95, standard = 85).
    The original photo is never changed; each version's final is its own file."""
    from starlette.concurrency import run_in_threadpool
    if fmt not in ("png", "jpg") or quality not in JPEG_QUALITY:
        raise ValueError("format is png or jpg; quality is high or standard")
    store.check_access(scene_id, uid)
    scene, _ = store.current(scene_id)
    v = scene["version"]
    name = f"final_v{v}.png" if fmt == "png" else f"final_v{v}_{quality}.jpg"
    data = store.get_file(scene_id, name)
    if data is None:
        data = await run_in_threadpool(_final_bytes, scene, fmt, quality)
        store.put_file(scene_id, name, data)
    return {"version": v, "format": fmt, "quality": quality if fmt == "jpg" else "lossless",
            "width": scene["image"]["width"], "height": scene["image"]["height"], "bytes": len(data),
            "filename": f"haven-design-v{v}.{fmt}",
            "url": f"/api/interior/scenes/{scene_id}/files/{name}"}


def final_file(scene_id: str, uid: Optional[str], name: str) -> Optional[bytes]:
    store.check_access(scene_id, uid)
    return store.get_file(scene_id, name)


# ---- saved designs -----------------------------------------------------------------

def save_design(repo, scene_id: str, uid: str, name: str) -> Dict:
    meta = store.check_access(scene_id, uid)
    scene, st = store.current(scene_id)
    record = {
        "name": name.strip()[:80] or "Untitled design",
        "scene_id": scene_id,
        "scene_json": json.dumps(public_scene(scene) | {"removed": scene.get("removed", [])}),
        "history_json": json.dumps(st["ops"][-200:]),
        "final_image": _latest_final(scene_id, scene["version"]),
        "updated_at": designs.now(),
    }
    design_id = meta.get("design_id")
    if design_id:
        try:
            existing = repo.get(design_id)
            if existing["user_id"] == uid:
                repo.update(design_id, record)
                store.set_owner(scene_id, uid, design_id)
                return designs.summary(existing | record)
        except designs.DesignNotFound:
            pass
    design_id = secrets.token_hex(12)
    record.update({"design_id": design_id, "user_id": uid, "created_at": designs.now()})
    repo.create(record)
    store.set_owner(scene_id, uid, design_id)
    return designs.summary(record)


def _latest_final(scene_id: str, version: int) -> Optional[str]:
    """URL of the final image generated for this exact version, if any."""
    for name in (f"final_v{version}.png", f"final_v{version}_high.jpg", f"final_v{version}_standard.jpg"):
        if store.get_file(scene_id, name) is not None:
            return f"/api/interior/scenes/{scene_id}/files/{name}"
    return None


def _owned(repo, design_id: str, uid: str) -> Dict:
    record = repo.get(design_id)
    if record["user_id"] != uid:
        raise designs.DesignNotFound(design_id)
    return record


def open_design(repo, design_id: str, uid: str) -> Dict:
    """Reopens a saved design exactly as it was saved (as a new undoable step
    if the room was edited after saving)."""
    record = _owned(repo, design_id, uid)
    scene_id = record["scene_id"]
    if not store.exists(scene_id):
        raise FileNotFoundError(scene_id)
    saved = json.loads(record["scene_json"])
    current, st = store.current(scene_id)
    if current["version"] != saved["version"]:
        saved = dict(saved, last_operation={"operation": "open_design", "design_id": design_id})
        current, st, _ = store.commit(scene_id, None, lambda _: (saved, []))
    resp = scene_response(current, st)
    resp["design"] = designs.summary(record)
    return resp


def delete_design(repo, design_id: str, uid: str) -> None:
    record = _owned(repo, design_id, uid)
    repo.delete(design_id)
    store.delete(record["scene_id"])


def catalog_response() -> Dict:
    return catalog.public_catalog()
