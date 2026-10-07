"""In-memory response cache for the chatbot: per session, LRU with a TTL."""
import hashlib
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

CACHE_MAX_SIZE = 500
CACHE_TTL_SECONDS = 15 * 60

response_cache: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def cache_key(session_id: str, message: str) -> str:
    raw = f"{session_id}:{message.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def get(key: str) -> Optional[Dict]:
    entry = response_cache.get(key)
    if not entry:
        return None
    if (_now() - entry["_cached_at"]).total_seconds() > CACHE_TTL_SECONDS:
        del response_cache[key]
        return None
    response_cache.move_to_end(key)  # mark as recently used
    return entry


def put(key: str, value: Dict) -> None:
    value = dict(value)
    value["_cached_at"] = _now()
    if key in response_cache:
        response_cache.move_to_end(key)
    response_cache[key] = value
    while len(response_cache) > CACHE_MAX_SIZE:
        response_cache.popitem(last=False)  # evict least-recently-used


def clear() -> None:
    response_cache.clear()
