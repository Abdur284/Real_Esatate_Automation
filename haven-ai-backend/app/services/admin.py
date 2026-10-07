"""
Data access for the admin dashboard. Every admin action runs here, on the
server, after require_admin has checked the caller's `admin` custom claim;
the browser never writes these collections directly.
"""
from typing import Any, Dict, List, Optional

from app.core.firebase import get_app, get_db

RECENT_LIMIT = 5


def _ts(value: Any) -> Optional[str]:
    """Firestore timestamps / datetimes / strings -> ISO string (or None)."""
    if value is None:
        return None
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else str(value)


def _user_row(doc_id: str, d: Dict) -> Dict:
    return {"id": doc_id, "name": d.get("name", ""), "email": d.get("email", ""),
            "role": d.get("role", "buyer"), "created_at": _ts(d.get("createdAt"))}


def _property_row(doc_id: str, d: Dict) -> Dict:
    return {"id": doc_id, "title": d.get("title", "Untitled"), "location": d.get("location", ""),
            "dealer_id": d.get("dealerId"), "verified": bool(d.get("verified")),
            "views": int(d.get("views") or 0)}


class FirestoreAdmin:
    def _db(self):
        return get_db()

    def stats(self) -> Dict:
        db = self._db()
        buyers = dealers = 0
        for snap in db.collection("users").stream():
            role = (snap.to_dict().get("role") or "").lower()
            if role in ("dealer", "seller"):
                dealers += 1
            else:
                buyers += 1
        properties = views = 0
        for snap in db.collection("properties").stream():
            properties += 1
            views += int(snap.to_dict().get("views") or 0)
        return {"total_users": buyers, "total_dealers": dealers,
                "total_properties": properties, "total_views": views}

    def recent_activity(self) -> List[Dict]:
        from firebase_admin import firestore
        db = self._db()
        out: List[Dict] = []
        q = db.collection("chats").order_by("lastMessageAt", direction=firestore.Query.DESCENDING)
        for snap in q.limit(RECENT_LIMIT).stream():
            d = snap.to_dict()
            out.append({"id": snap.id, "type": "DEALER",
                        "title": f"{d.get('buyerName') or 'User'} ↔ {d.get('dealerName') or 'Dealer'}",
                        "subtitle": d.get("propertyTitle", ""),
                        "message": d.get("lastMessage") or "Started a conversation",
                        "time": _ts(d.get("lastMessageAt"))})
        q = db.collection("chat_sessions").order_by("updated_at", direction=firestore.Query.DESCENDING)
        for snap in q.limit(RECENT_LIMIT).stream():
            d = snap.to_dict()
            out.append({"id": snap.id, "type": "AI",
                        "title": "AI chat: " + ("signed-in user" if d.get("user_id") else "guest"),
                        "subtitle": f"ArchiBot · {d.get('last_module') or 'general'}",
                        "message": d.get("last_message") or "Active session",
                        "time": _ts(d.get("updated_at"))})
        out.sort(key=lambda r: r["time"] or "", reverse=True)
        return out[:2 * RECENT_LIMIT]

    def list_users(self) -> List[Dict]:
        return [_user_row(s.id, s.to_dict()) for s in self._db().collection("users").stream()]

    def delete_user(self, uid: str) -> None:
        """Removes the profile and the sign-in account."""
        from firebase_admin import auth
        self._db().collection("users").document(uid).delete()
        try:
            auth.delete_user(uid, app=get_app())
        except auth.UserNotFoundError:
            pass

    def list_properties(self, verified: Optional[bool] = None) -> List[Dict]:
        rows = [_property_row(s.id, s.to_dict()) for s in self._db().collection("properties").stream()]
        return rows if verified is None else [r for r in rows if r["verified"] == verified]

    def verify_property(self, property_id: str) -> bool:
        ref = self._db().collection("properties").document(property_id)
        if not ref.get().exists:
            return False
        ref.update({"verified": True})
        return True

    def reset_views(self) -> int:
        db = self._db()
        count = 0
        batch = db.batch()
        for snap in db.collection("properties").stream():
            batch.update(snap.reference, {"views": 0})
            count += 1
            if count % 400 == 0:  # Firestore batches hold at most 500 writes
                batch.commit()
                batch = db.batch()
        batch.commit()
        return count


_repo = FirestoreAdmin()


def get_admin_repo() -> FirestoreAdmin:
    return _repo
