"""
Saved interior designs: one Firestore document per design in the
`interior_designs` collection (the project's live database), written only by
the backend after it has verified who the user is.

    design_id, user_id, name, scene_id,
    scene_json    the full scene at save time (a JSON string: Firestore does
                  not allow the nested arrays that outlines use)
    history_json  the operation log up to the save
    final_image   file name of the last generated final image, if any
    created_at, updated_at (UTC)

The photo and its analysis stay on the backend (store.py), referenced by
scene_id. Access to Firestore is kept in this repository class.
"""
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.core.firebase import FirebaseUnavailable, get_app

COLLECTION = "interior_designs"


class DesignNotFound(KeyError):
    pass


def now() -> datetime:
    return datetime.now(timezone.utc)


class FirestoreDesigns:
    def _col(self):
        try:
            from firebase_admin import firestore
            return firestore.client(app=get_app()).collection(COLLECTION)
        except FirebaseUnavailable:
            raise
        except Exception as e:
            raise FirebaseUnavailable("The design database is not reachable right now.") from e

    def create(self, record: Dict) -> None:
        self._col().document(record["design_id"]).set(record)

    def get(self, design_id: str) -> Dict:
        snap = self._col().document(design_id).get()
        if not snap.exists:
            raise DesignNotFound(design_id)
        return snap.to_dict()

    def update(self, design_id: str, fields: Dict) -> None:
        self._col().document(design_id).update(fields)

    def delete(self, design_id: str) -> None:
        self._col().document(design_id).delete()

    def list_for(self, user_id: str, limit: int = 50) -> List[Dict]:
        from google.cloud.firestore_v1.base_query import FieldFilter
        docs = self._col().where(filter=FieldFilter("user_id", "==", user_id)).limit(limit).stream()
        rows = [d.to_dict() for d in docs]
        rows.sort(key=lambda r: r.get("updated_at") or now(), reverse=True)
        return rows


class MemoryDesigns:
    """Same interface, in memory. Used by the tests only."""

    def __init__(self):
        self.rows: Dict[str, Dict] = {}
        self.lock = threading.Lock()

    def create(self, record: Dict) -> None:
        with self.lock:
            self.rows[record["design_id"]] = dict(record)

    def get(self, design_id: str) -> Dict:
        with self.lock:
            if design_id not in self.rows:
                raise DesignNotFound(design_id)
            return dict(self.rows[design_id])

    def update(self, design_id: str, fields: Dict) -> None:
        with self.lock:
            if design_id not in self.rows:
                raise DesignNotFound(design_id)
            self.rows[design_id].update(fields)

    def delete(self, design_id: str) -> None:
        with self.lock:
            self.rows.pop(design_id, None)

    def list_for(self, user_id: str, limit: int = 50) -> List[Dict]:
        with self.lock:
            rows = [dict(r) for r in self.rows.values() if r["user_id"] == user_id]
        rows.sort(key=lambda r: r["updated_at"], reverse=True)
        return rows[:limit]


_repo: Optional[object] = None


def get_repository():
    """FastAPI dependency (overridden in tests)."""
    global _repo
    if _repo is None:
        _repo = FirestoreDesigns()
    return _repo


def summary(record: Dict) -> Dict:
    scene = json.loads(record["scene_json"]) if record.get("scene_json") else {}
    ts = record.get("updated_at")
    created = record.get("created_at")
    return {
        "design_id": record["design_id"], "name": record["name"], "scene_id": record["scene_id"],
        "created_at": created.isoformat() if hasattr(created, "isoformat") else created,
        "updated_at": ts.isoformat() if hasattr(ts, "isoformat") else ts,
        "objects": len(scene.get("objects", [])), "version": scene.get("version"),
        "thumbnail_url": f"/api/interior/scenes/{record['scene_id']}/render?v={scene.get('version', 0)}&w=480",
        "final_image": record.get("final_image"),
    }
