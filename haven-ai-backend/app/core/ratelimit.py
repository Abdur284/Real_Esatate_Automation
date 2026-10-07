"""
Per-caller request limits for the expensive endpoints (Gemini calls, CPU
heavy generation). A sliding one-minute window per key, kept in memory: it
protects a single-process deployment (the FYP setup) from one caller using
up the Gemini quota. Behind several workers, move the counters to Redis.

    @router.post("/send", dependencies=[Depends(rate_limit("chat"))])
"""
import threading
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional

from fastapi import Depends, HTTPException, Request

from app.core.auth import optional_user
from app.core.config import settings

WINDOW_SECONDS = 60.0

_lock = threading.Lock()
_hits: Dict[str, Deque[float]] = defaultdict(deque)


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def check(key: str, limit: int, now: Optional[float] = None) -> Optional[int]:
    """Records a hit for `key`. Returns None if allowed, else the seconds
    until the next request would be allowed."""
    now = time.monotonic() if now is None else now
    with _lock:
        hits = _hits[key]
        while hits and now - hits[0] >= WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            return max(1, int(WINDOW_SECONDS - (now - hits[0])) + 1)
        hits.append(now)
        if len(_hits) > 10_000:  # forget idle callers so memory stays bounded
            for k in [k for k, v in _hits.items() if not v or now - v[-1] >= WINDOW_SECONDS]:
                del _hits[k]
    return None


def reset() -> None:
    with _lock:
        _hits.clear()


def rate_limit(scope: str, per_minute: Optional[int] = None):
    """FastAPI dependency limiting each signed-in user (or IP for guests)."""
    async def dependency(request: Request, uid: Optional[str] = Depends(optional_user)) -> None:
        limit = settings.RATE_LIMIT_PER_MINUTE if per_minute is None else per_minute
        if limit <= 0:
            return
        who = f"user:{uid}" if uid else f"ip:{_client_ip(request)}"
        retry_after = check(f"{scope}:{who}", limit)
        if retry_after is not None:
            raise HTTPException(status_code=429,
                                detail="Too many requests. Please wait a moment and try again.",
                                headers={"Retry-After": str(retry_after)})
    return dependency
