"""
Disk storage for rooms being edited.

One folder per room, named by an unguessable id:

    original.jpg        the uploaded photo at working size (never modified)
    instances.png       which detected element each pixel belongs to
    alphas.npz          soft outline of each detected object
    detections.json     what the analysis found (the Original State)
    history/<v>.json    every scene version (Scene + User State)
    state.json          undo/redo stack, operation log
    meta.json           owner, timestamps, saved design id
    final_*.png|jpg     generated final images

Rooms that are never saved are deleted after INTERIOR_SCENE_TTL_HOURS.
Saved designs keep their folder; their record lives in Firestore
(designs.py). Loaded images are cached in memory for fast re-renders.
"""
import json
import os
import re
import shutil
import threading
import time
from collections import OrderedDict
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from .renderer import Assets

ID_RE = re.compile(r"^[0-9a-f]{32}$")
MAX_HISTORY = 100
ASSET_CACHE = 6


class SceneNotFound(KeyError):
    pass


class SceneForbidden(PermissionError):
    pass


class HistoryConflict(ValueError):
    """The client edited an older version than the current one (-> 409)."""


class SceneStore:
    def __init__(self, root: str):
        self.root = root
        self._locks: Dict[str, threading.RLock] = {}
        self._global = threading.Lock()
        self._assets: "OrderedDict[str, Assets]" = OrderedDict()

    # ---- paths and locks ----
    def _dir(self, scene_id: str) -> str:
        if not ID_RE.match(scene_id or ""):
            raise SceneNotFound(scene_id)
        return os.path.join(self.root, "scenes", scene_id)

    def lock(self, scene_id: str) -> threading.RLock:
        with self._global:
            return self._locks.setdefault(scene_id, threading.RLock())

    def exists(self, scene_id: str) -> bool:
        try:
            return os.path.isfile(os.path.join(self._dir(scene_id), "meta.json"))
        except SceneNotFound:
            return False

    def _read(self, scene_id: str, name: str):
        path = os.path.join(self._dir(scene_id), name)
        if not os.path.isfile(path):
            raise SceneNotFound(scene_id)
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _write(self, scene_id: str, name: str, data) -> None:
        path = os.path.join(self._dir(scene_id), name)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, separators=(",", ":"))
        os.replace(tmp, path)

    # ---- creation ----
    def create(self, scene_id: str, original: np.ndarray, instances: np.ndarray,
               alphas: Dict[int, np.ndarray], detections: Dict, scene: Dict, owner_uid: Optional[str]) -> None:
        d = self._dir(scene_id)
        os.makedirs(os.path.join(d, "history"), exist_ok=True)
        cv2.imwrite(os.path.join(d, "original.jpg"), original, [cv2.IMWRITE_JPEG_QUALITY, 95])
        cv2.imwrite(os.path.join(d, "instances.png"), instances)
        crops, meta = {}, []
        for idx, a in alphas.items():
            ys, xs = np.where(a > 0)
            if len(ys) == 0:
                continue
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            crops[f"a{idx}"] = a[y0:y1, x0:x1]
            meta.append([idx, int(y0), int(x0)])
        np.savez_compressed(os.path.join(d, "alphas.npz"), meta=np.array(meta, np.int32).reshape(-1, 3), **crops)
        self._write(scene_id, "detections.json", detections)
        self._write(scene_id, f"history/{scene['version']}.json", scene)
        self._write(scene_id, "state.json", {"stack": [scene["version"]], "position": 0,
                                              "next_version": scene["version"] + 1, "ops": []})
        now = time.time()
        self._write(scene_id, "meta.json", {"scene_id": scene_id, "owner_uid": owner_uid, "created_at": now,
                                             "updated_at": now, "design_id": None})

    # ---- access ----
    def meta(self, scene_id: str) -> Dict:
        return self._read(scene_id, "meta.json")

    def check_access(self, scene_id: str, uid: Optional[str]) -> Dict:
        """Rooms uploaded while signed in belong to that user; guest rooms are
        reachable only through their unguessable id."""
        meta = self.meta(scene_id)
        owner = meta.get("owner_uid")
        if owner and owner != uid:
            raise SceneForbidden(scene_id)
        return meta

    def set_owner(self, scene_id: str, uid: str, design_id: Optional[str] = None) -> None:
        with self.lock(scene_id):
            meta = self.meta(scene_id)
            meta["owner_uid"] = uid
            if design_id is not None:
                meta["design_id"] = design_id
            self._write(scene_id, "meta.json", meta)

    def detections(self, scene_id: str) -> Dict:
        return self._read(scene_id, "detections.json")

    def assets(self, scene_id: str) -> Assets:
        with self._global:
            if scene_id in self._assets:
                self._assets.move_to_end(scene_id)
                return self._assets[scene_id]
        d = self._dir(scene_id)
        original = cv2.imread(os.path.join(d, "original.jpg"), cv2.IMREAD_COLOR)
        instances = cv2.imread(os.path.join(d, "instances.png"), cv2.IMREAD_UNCHANGED)
        if original is None or instances is None:
            raise SceneNotFound(scene_id)
        alphas = {}
        with np.load(os.path.join(d, "alphas.npz")) as z:
            for idx, y0, x0 in z["meta"]:
                alphas[int(idx)] = (int(y0), int(x0), z[f"a{idx}"])
        assets = Assets(original=original, instances=instances, alphas=alphas)
        with self._global:
            self._assets[scene_id] = assets
            while len(self._assets) > ASSET_CACHE:
                self._assets.popitem(last=False)
        return assets

    # ---- history ----
    def state(self, scene_id: str) -> Dict:
        return self._read(scene_id, "state.json")

    def current(self, scene_id: str) -> Tuple[Dict, Dict]:
        st = self.state(scene_id)
        return self._read(scene_id, f"history/{st['stack'][st['position']]}.json"), st

    def commit(self, scene_id: str, base_version: Optional[int], make) -> Tuple[Dict, Dict, List[str]]:
        """make(current_scene, next_version) -> (new_scene, notes). Runs under
        the room's lock; rejects edits made against an older version."""
        with self.lock(scene_id):
            scene, st = self.current(scene_id)
            if base_version is not None and base_version != scene["version"]:
                raise HistoryConflict(scene["version"])
            new, notes = make(scene)
            new["version"] = st["next_version"]
            self._write(scene_id, f"history/{new['version']}.json", new)
            dropped = st["stack"][st["position"] + 1:]
            st["stack"] = st["stack"][:st["position"] + 1] + [new["version"]]
            if len(st["stack"]) > MAX_HISTORY:
                dropped += st["stack"][1:len(st["stack"]) - MAX_HISTORY + 1]
                st["stack"] = st["stack"][:1] + st["stack"][len(st["stack"]) - MAX_HISTORY + 1:]
            st["position"] = len(st["stack"]) - 1
            st["next_version"] += 1
            st["ops"] = (st["ops"] + [{"version": new["version"], "at": time.time(),
                                       "operation": new.get("last_operation")}])[-500:]
            self._drop(scene_id, dropped)
            self._write(scene_id, "state.json", st)
            self._touch(scene_id)
            return new, st, notes

    def move(self, scene_id: str, step: int) -> Tuple[Dict, Dict]:
        """Undo (-1) / redo (+1)."""
        with self.lock(scene_id):
            st = self.state(scene_id)
            pos = st["position"] + step
            if not 0 <= pos < len(st["stack"]):
                raise HistoryConflict("nothing to undo" if step < 0 else "nothing to redo")
            st["position"] = pos
            self._write(scene_id, "state.json", st)
            self._touch(scene_id)
            return self._read(scene_id, f"history/{st['stack'][pos]}.json"), st

    def reset(self, scene_id: str) -> Tuple[Dict, Dict]:
        """Back to the analysed room, as a new step (so it can be undone)."""
        def to_initial(_):
            initial = self._read(scene_id, f"history/{self.state(scene_id)['stack'][0]}.json")
            initial = dict(initial, last_operation={"operation": "reset_scene"})
            return initial, []
        new, st, _ = self.commit(scene_id, None, to_initial)
        return new, st

    def load_history(self, scene_id: str, scenes: List[Dict], position: int, ops: List[Dict]) -> None:
        """Replaces the history (used when a saved design is reopened elsewhere)."""
        with self.lock(scene_id):
            for s in scenes:
                self._write(scene_id, f"history/{s['version']}.json", s)
            self._write(scene_id, "state.json", {"stack": [s["version"] for s in scenes], "position": position,
                                                  "next_version": max(s["version"] for s in scenes) + 1,
                                                  "ops": ops})

    def _drop(self, scene_id: str, versions: List[int]) -> None:
        for v in versions:
            try:
                os.remove(os.path.join(self._dir(scene_id), "history", f"{v}.json"))
            except OSError:
                pass

    def _touch(self, scene_id: str) -> None:
        meta = self.meta(scene_id)
        meta["updated_at"] = time.time()
        self._write(scene_id, "meta.json", meta)

    # ---- files ----
    def put_file(self, scene_id: str, name: str, data: bytes) -> None:
        if not re.match(r"^final_[a-z0-9_]+\.(png|jpg)$", name):
            raise ValueError(name)
        with open(os.path.join(self._dir(scene_id), name), "wb") as f:
            f.write(data)

    def get_file(self, scene_id: str, name: str) -> Optional[bytes]:
        if not re.match(r"^(original\.jpg|final_[a-z0-9_]+\.(png|jpg))$", name):
            return None
        path = os.path.join(self._dir(scene_id), name)
        if not os.path.isfile(path):
            return None
        with open(path, "rb") as f:
            return f.read()

    # ---- housekeeping ----
    def delete(self, scene_id: str) -> None:
        with self._global:
            self._assets.pop(scene_id, None)
        shutil.rmtree(self._dir(scene_id), ignore_errors=True)

    def cleanup(self, ttl_hours: float) -> int:
        """Deletes unsaved rooms not touched for ttl_hours. Returns how many."""
        base = os.path.join(self.root, "scenes")
        if not os.path.isdir(base):
            return 0
        cutoff = time.time() - ttl_hours * 3600
        removed = 0
        for sid in os.listdir(base):
            try:
                meta = self.meta(sid)
            except (SceneNotFound, ValueError, OSError):
                continue
            if not meta.get("design_id") and meta.get("updated_at", 0) < cutoff:
                self.delete(sid)
                removed += 1
        return removed


store = SceneStore(settings.INTERIOR_STORAGE_DIR)
